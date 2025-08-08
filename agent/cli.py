from __future__ import annotations

import json
import signal
import sys
import time
from typing import Optional

import typer
from loguru import logger

# Typer application
app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="RAFT command-line interface"
)


def run_one_cycle() -> bool:
    """Thin wrapper to allow monkeypatching in tests and keep imports lazy."""
    from agent.core.governor import run_one_cycle as _run

    return _run()


def _estimate_rho() -> Optional[float]:
    """Best-effort spectral radius estimation using the governor's model.

    Returns None on failure to avoid raising heavy import errors in CLI context.
    """
    try:
        import torch  # Lazy import; heavy deps should be avoided in tests via monkeypatch

        from agent.core.governor import _SPECTRAL_MODEL  # type: ignore

        x0 = torch.randn(4, requires_grad=True)
        # Use a small number of iterations for speed in CLI context
        rho = _SPECTRAL_MODEL.estimate_spectral_radius(x0, n_iter=5)
        return float(rho)
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch in tests
        logger.debug(f"rho estimation unavailable: {exc}")
        return None


def _estimate_energy(rho: Optional[float]) -> Optional[float]:
    """Compute energy as energy_multiplier * rho if rho is available."""
    if rho is None:
        return None
    try:
        from agent.core.config_store import get_config

        cfg = get_config()
        return float(cfg.energy_multiplier * rho)
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch in tests
        logger.debug(f"energy estimation unavailable: {exc}")
        return None


def start_http_server(port: int) -> None:
    """Indirection for Prometheus server to allow monkeypatching in tests."""
    from prometheus_client import start_http_server as _start

    _start(port)


@app.command("version")
def version_cmd() -> None:
    """Print the RAFT package version."""
    try:
        try:
            # Python 3.8+
            from importlib.metadata import PackageNotFoundError
            from importlib.metadata import version as _version
        except Exception:  # pragma: no cover
            from importlib_metadata import PackageNotFoundError
            from importlib_metadata import version as _version  # type: ignore
        v = _version("raft")
    except Exception:
        v = "0.0.0"
    typer.echo(v)


@app.command("one-cycle")
def one_cycle_cmd() -> None:
    """Run exactly one governor cycle and print JSON status with rho and energy."""
    ok = run_one_cycle()
    status = "ok" if ok else "rollback"

    rho = _estimate_rho()
    energy = _estimate_energy(rho)

    output = {"status": status, "rho": rho, "energy": energy}
    typer.echo(json.dumps(output))


@app.command("run")
def run_cmd(
    metrics_port: int = typer.Option(
        8002, "--metrics-port", help="Prometheus metrics port"
    ),
    interval: float = typer.Option(1.0, "--interval", help="Seconds between cycles"),
    cycles: Optional[int] = typer.Option(
        None, "-n", "--cycles", help="Optional number of cycles before exit"
    ),
) -> None:
    """Start metrics server and run governor cycles continuously."""
    # Start Prometheus metrics server
    start_http_server(metrics_port)
    logger.info(f"Metrics server listening on :{metrics_port}")

    should_stop = False
    completed_cycles = 0

    def _handle_signal(
        signum: int, _frame: object
    ) -> None:  # pragma: no cover - hard to simulate
        nonlocal should_stop
        logger.info(f"Received signal {signum}, shutting down after current cycle...")
        should_stop = True

    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (
        Exception
    ):  # pragma: no cover - some environments may not allow signal handling
        pass

    try:
        while True:
            if cycles is not None and completed_cycles >= cycles:
                break
            ok = run_one_cycle()
            status = "ok" if ok else "rollback"
            logger.info(f"Cycle {completed_cycles + 1} status={status}")
            completed_cycles += 1
            if should_stop:
                break
            if interval > 0:
                time.sleep(interval)
    except KeyboardInterrupt:  # pragma: no cover - signals are handled above
        logger.info("Keyboard interrupt received, exiting...")
    finally:
        logger.info(f"Exiting run loop after {completed_cycles} cycles")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
