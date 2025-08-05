#!/usr/bin/env python3
"""
RAFT Metrics Server

Starts Prometheus HTTP server and runs governor cycles with real-time metrics display.
"""

import signal
import sys
import time

from loguru import logger
from prometheus_client import start_http_server

from agent.core.governor import run_one_cycle
from agent.metrics import (CYCLE_COUNT, ENERGY_RATE, PROC_LATENCY,
                           PROOF_FAILURE, PROOF_SUCCESS, SPECTRAL_RHO)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Shutting down metrics server...")
    sys.exit(0)


def main(port=8002, interval=2):
    """Start metrics server and run governor cycles."""
    print("🚀 Starting RAFT Metrics Server")
    print("=" * 50)

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Start Prometheus HTTP server
    print(f"📊 Starting Prometheus HTTP server on port {port}...")
    start_http_server(port, addr="0.0.0.0")
    print(f"✅ Metrics available at http://localhost:{port}/metrics")

    print("\n🔄 Running governor cycles...")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    cycle = 0
    try:
        while True:
            cycle += 1
            try:
                start = time.time()
                ok = run_one_cycle()
                dur = time.time() - start
                status = "✅ SUCCESS" if ok else "❌ FAILED"

                # Get current metric values
                rho = SPECTRAL_RHO._value.get()
                energy = ENERGY_RATE._value.get()
                psuccess = PROOF_SUCCESS._value.get()
                pfail = PROOF_FAILURE._value.get()
                total_cycles = CYCLE_COUNT._value.get()

                # Display results
                print(f"\n🔄 Cycle {cycle}")
                print(f"   Status: {status}")
                print(f"   Duration: {dur:.3f}s")
                print(f"   Spectral Radius: {rho:.3f}")
                print(f"   Energy Rate: {energy:.2e} J/s")
                print(f"   Total Cycles: {total_cycles}")
                print(f"   Proof Success: {psuccess}")
                print(f"   Proof Failures: {pfail}")

                # Also log for debugging
                logger.info(
                    "Cycle {}/ status={status} duration={dur:.3f}s "
                    "ρ={rho:.3f} energy={energy:.2e} proof+={psuccess} proof-={pfail}",
                    cycle,
                    status="OK" if ok else "FAIL",
                    dur=dur,
                    rho=rho,
                    energy=energy,
                    psuccess=psuccess,
                    pfail=pfail,
                )

            except Exception as e:
                logger.exception("Unexpected error in governor cycle")
                print(f"❌ Error in cycle {cycle}: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n🛑 Received shutdown signal")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    print("\n📊 Final Metrics Summary:")
    print(f"   Total Cycles: {CYCLE_COUNT._value.get()}")
    print(f"   Proof Success: {PROOF_SUCCESS._value.get()}")
    print(f"   Proof Failures: {PROOF_FAILURE._value.get()}")
    print(f"   Current Spectral Radius: {SPECTRAL_RHO._value.get():.3f}")
    print(f"   Current Energy Rate: {ENERGY_RATE._value.get():.2e} J/s")
    print("\n🎉 Metrics server shutdown complete")


if __name__ == "__main__":
    main()
