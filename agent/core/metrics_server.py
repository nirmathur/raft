# metrics_server.py
import signal
import sys
import time

from loguru import logger
from prometheus_client import start_http_server

from agent.core.governor import run_one_cycle
from agent.metrics import (CYCLE_COUNT, ENERGY_RATE, PROOF_FAILURE,
                           PROOF_SUCCESS, SPECTRAL_RHO)


def main(port=8002, interval=2):
    start_http_server(port, addr="0.0.0.0")
    logger.info(f"Metrics HTTP server listening on :{port}")
    cycle = 0
    while True:
        cycle += 1
        try:
            start = time.time()
            ok = run_one_cycle()
            dur = time.time() - start
            status = "OK" if ok else "FAIL"
            logger.info(
                "Cycle {}/ status={status} duration={dur:.3f}s "
                "ρ={rho:.3f} energy={energy:.2e} proof+={psuccess} proof-={pfail}",
                cycle,
                status=status,
                dur=dur,
                rho=SPECTRAL_RHO.collect()[0].samples[-1].value,
                energy=ENERGY_RATE.collect()[0].samples[-1].value,
                psuccess=PROOF_SUCCESS.collect()[0].samples[-1].value,
                pfail=PROOF_FAILURE.collect()[0].samples[-1].value,
            )
        except Exception:
            logger.exception("Unexpected error in governor cycle")
        time.sleep(interval)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *args: sys.exit(0))
    main()
