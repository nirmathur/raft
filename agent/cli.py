"""RAFT CLI - Command line interface for the RAFT agent system.

Provides subcommands for:
- run: Start continuous governor loop with metrics
- one-cycle: Run a single cycle and output JSON status
- version: Display RAFT version
"""

import json
import time
import signal
import sys
from pathlib import Path

import click
import toml
from loguru import logger
from prometheus_client import start_http_server

from agent.core.governor import run_one_cycle
from agent.core.escape_hatches import is_paused
from agent.metrics import SPECTRAL_RHO, ENERGY_RATE


def get_version() -> str:
    """Get RAFT version from pyproject.toml."""
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    try:
        with open(pyproject_path) as f:
            data = toml.load(f)
        return data["project"]["version"]
    except (FileNotFoundError, KeyError):
        return "unknown"


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(verbose: bool):
    """RAFT - Recursive Agent for Formal Trust.
    
    A recursive agent system with formal trust guarantees, featuring 
    spectral radius guards, proof gates, and operator escape hatches.
    """
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")


@main.command()
@click.option("--metrics-port", default=8002, help="Port for Prometheus metrics server")
@click.option("--cycle-interval", default=1.0, help="Seconds between cycles")
def run(metrics_port: int, cycle_interval: float):
    """Start continuous governor loop with metrics server.
    
    Equivalent to the old metrics_server.py - runs cycles continuously
    and exposes Prometheus metrics on the specified port.
    """
    logger.info("Starting RAFT continuous governor with metrics on port {}", metrics_port)
    
    # Start Prometheus metrics server
    start_http_server(metrics_port)
    logger.info("Metrics server started on http://localhost:{}/metrics", metrics_port)
    
    # Setup signal handlers for graceful shutdown
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        logger.info("Shutdown signal received, stopping gracefully...")
        shutdown_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    cycles_completed = 0
    
    try:
        while not shutdown_requested and not is_paused():
            logger.debug("Starting governor cycle {}", cycles_completed + 1)
            
            success = run_one_cycle()
            cycles_completed += 1
            
            if success:
                logger.debug("Cycle {} completed successfully", cycles_completed)
            else:
                logger.warning("Cycle {} failed or was aborted", cycles_completed)
            
            # Brief pause between cycles
            time.sleep(cycle_interval)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error("Unexpected error in governor loop: {}", e)
        sys.exit(1)
    finally:
        logger.info("Governor stopped after {} cycles", cycles_completed)


@main.command("one-cycle")
def one_cycle():
    """Run a single governor cycle and output JSON status.
    
    Executes exactly one run_one_cycle() and prints JSON result with:
    - status: "success" or "failure"
    - rho: current spectral radius value
    - energy: current energy rate (J/s)
    """
    logger.info("Running single governor cycle")
    
    # Run the cycle
    success = run_one_cycle()
    
    # Collect metrics from the Prometheus gauges
    # Note: These values are set during run_one_cycle()
    rho_value = SPECTRAL_RHO._value._value if hasattr(SPECTRAL_RHO._value, '_value') else 0.0
    energy_value = ENERGY_RATE._value._value if hasattr(ENERGY_RATE._value, '_value') else 0.0
    
    # Prepare JSON output
    result = {
        "status": "success" if success else "failure",
        "rho": float(rho_value),
        "energy": float(energy_value)
    }
    
    # Output JSON to stdout
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


@main.command()
def version():
    """Display RAFT version information."""
    version_str = get_version()
    click.echo(f"RAFT version {version_str}")


if __name__ == "__main__":
    main()