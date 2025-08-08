#!/usr/bin/env python3
"""
Performance/accuracy comparison harness for RAFT vs baseline.

Usage:
    poetry run python scripts/compare_baseline.py --mode baseline --runs 3
    poetry run python scripts/compare_baseline.py --mode raft --runs 3
"""

import argparse
import csv
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


def baseline_computation(seed: int) -> Tuple[bool, Optional[float], Optional[float]]:
    """Compute f(x)=x + ε with x=1.0, ε ~ N(0, 0.01).

    Returns:
        Tuple of (success, rho, energy) where success is always True,
        and rho/energy are None for baseline mode.
    """
    np.random.seed(seed)
    x = 1.0
    epsilon = np.random.normal(0, 0.01)
    result = x + epsilon
    return True, None, None


def raft_computation(seed: int) -> Tuple[bool, Optional[float], Optional[float]]:
    """Run one RAFT governor cycle and extract metrics.

    Returns:
        Tuple of (success, rho, energy) where success is the boolean return
        from run_one_cycle(), and rho/energy are estimated from metrics.
    """
    # Import here to avoid heavy dependencies when not needed
    from agent.core.governor import run_one_cycle

    # Set seed for reproducible behavior (only if torch is available)
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        # Silently continue if torch is not available
        pass

    # Run the governor cycle
    success = run_one_cycle()

    # Extract rho and energy from metrics (with multiple fallback levels)
    rho = None
    energy = None

    # Primary metrics read: try agent.metrics first
    try:
        from agent.metrics import ENERGY_RATE, SPECTRAL_RHO

        try:
            # Get current spectral radius value
            rho = float(SPECTRAL_RHO._value.get())
        except (AttributeError, TypeError, ValueError):
            # Fallback if metric not available
            pass

        try:
            # Get current energy rate
            energy = float(ENERGY_RATE._value.get())
        except (AttributeError, TypeError, ValueError):
            # Fallback if metric not available
            pass

    except ImportError:
        # Fallback metrics read: use in-process Prometheus registry
        try:
            from prometheus_client import REGISTRY

            def _sample_value(metric_name: str) -> Optional[float]:
                """Get the latest sample value for a metric from the registry."""
                for metric in REGISTRY.collect():
                    for sample in getattr(metric, "samples", []):
                        if sample.name == metric_name:
                            return float(sample.value)
                return None

            # Try to get values from registry
            rho = _sample_value("raft_spectral_radius")
            energy = _sample_value("raft_energy_rate")

        except ImportError:
            # If prometheus_client is also not available, leave as None
            pass

    return success, rho, energy


def run_comparison(
    mode: str,
    runs: int,
    output_path: Path,
    seed: int,
    collected_data: List[dict],
) -> None:
    """Run the comparison for the specified mode and number of runs."""

    # Set global seed for reproducibility
    np.random.seed(seed)

    for run_num in range(1, runs + 1):
        start_time = time.perf_counter()

        # Run the computation based on mode
        if mode == "baseline":
            success, rho, energy = baseline_computation(seed + run_num)
        elif mode == "raft":
            success, rho, energy = raft_computation(seed + run_num)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        end_time = time.perf_counter()
        latency = end_time - start_time

        # Record the result
        result = {
            "run": run_num,
            "mode": mode,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "latency": latency,
            "rho": rho if rho is not None else "",
            "energy": energy if energy is not None else "",
        }

        collected_data.append(result)

        # Write to CSV after each run to handle Ctrl+C gracefully
        write_csv(output_path, collected_data)


def write_csv(output_path: Path, data: List[dict]) -> None:
    """Write data to CSV file with the exact header format."""
    fieldnames = ["run", "mode", "timestamp", "success", "latency", "rho", "energy"]

    with open(output_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully by writing collected data."""
    print(f"\nReceived signal {signum}. Writing collected data...")
    if hasattr(signal_handler, "collected_data") and hasattr(
        signal_handler, "output_path"
    ):
        write_csv(signal_handler.output_path, signal_handler.collected_data)
    sys.exit(0)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Performance/accuracy comparison harness for RAFT vs baseline"
    )
    parser.add_argument(
        "--runs", type=int, default=3, help="Number of runs (default: 3)"
    )
    parser.add_argument(
        "--mode",
        choices=["baseline", "raft"],
        required=True,
        help="Mode to run (baseline or raft)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: output_{mode}.csv)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for reproducible results (default: 0)",
    )

    args = parser.parse_args()

    # Set default output path if not specified
    if args.out is None:
        args.out = Path(f"output_{args.mode}.csv")

    # Setup signal handler for graceful Ctrl+C
    signal_handler.output_path = args.out
    signal_handler.collected_data = []
    signal.signal(signal.SIGINT, signal_handler)

    print(f"Running {args.mode} mode with {args.runs} runs...")
    print(f"Output will be written to: {args.out}")
    print(f"Using seed: {args.seed}")

    try:
        run_comparison(
            mode=args.mode,
            runs=args.runs,
            output_path=args.out,
            seed=args.seed,
            collected_data=signal_handler.collected_data,
        )
        print(f"Completed {args.runs} runs. Results written to {args.out}")
    except KeyboardInterrupt:
        # Signal handler will handle the cleanup
        pass
    except Exception as e:
        print(f"Error during comparison: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
