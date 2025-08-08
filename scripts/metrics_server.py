#!/usr/bin/env python3
"""
Simple HTTP server to expose Prometheus metrics for fuzz tests.
"""
import json
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Counter,
                               Gauge, Histogram, generate_latest)

# Create a separate registry for fuzz test metrics
FUZZ_REGISTRY = CollectorRegistry()

# Create Prometheus metrics in the separate registry
PROOF_PASS_COUNTER = Counter(
    "fuzz_proof_pass_total", "Z3 proofs passed", registry=FUZZ_REGISTRY
)
PROOF_FAIL_COUNTER = Counter(
    "fuzz_proof_fail_total", "Z3 proofs failed", registry=FUZZ_REGISTRY
)
CYCLE_COUNTER = Counter(
    "fuzz_cycle_total", "Total governor cycles", registry=FUZZ_REGISTRY
)
SPECTRAL_RADIUS_GAUGE = Gauge(
    "fuzz_spectral_radius", "Spectral radius value each cycle", registry=FUZZ_REGISTRY
)
ENERGY_RATE_GAUGE = Gauge(
    "fuzz_energy_rate_j_s",
    "Energy rate (Joules per second) for each block",
    registry=FUZZ_REGISTRY,
)
CYCLE_LATENCY_HISTOGRAM = Histogram(
    "fuzz_cycle_latency_seconds", "Cycle latency in seconds", registry=FUZZ_REGISTRY
)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            # Generate metrics from our custom registry
            self.wfile.write(generate_latest(FUZZ_REGISTRY))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def do_POST(self):
        if self.path == "/update":
            # Get the content length
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)

            try:
                # Parse JSON data
                data = json.loads(post_data.decode("utf-8"))

                # Update metrics based on the data
                if data.get("cycle_count", 0) > 0:
                    CYCLE_COUNTER.inc(data["cycle_count"])

                if data.get("proof_pass", 0) > 0:
                    PROOF_PASS_COUNTER.inc(data["proof_pass"])

                if data.get("proof_fail", 0) > 0:
                    PROOF_FAIL_COUNTER.inc(data["proof_fail"])

                if "spectral_radius" in data:
                    SPECTRAL_RADIUS_GAUGE.set(data["spectral_radius"])

                if "energy_rate" in data:
                    ENERGY_RATE_GAUGE.set(data["energy_rate"])

                if "cycle_latency" in data:
                    CYCLE_LATENCY_HISTOGRAM.observe(data["cycle_latency"])

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")

            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error: {str(e)}".encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")


def main():
    """Start the metrics server."""
    server = HTTPServer(("localhost", 8003), MetricsHandler)
    print("🚀 Starting metrics server on http://localhost:8003/metrics")
    print("📊 Prometheus can scrape metrics from this endpoint")
    print("🔄 Metrics will reset when no new data is received")

    # Reset metrics on startup
    SPECTRAL_RADIUS_GAUGE.set(0.0)
    ENERGY_RATE_GAUGE.set(0.0)

    server.serve_forever()


if __name__ == "__main__":
    main()
