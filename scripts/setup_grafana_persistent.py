#!/usr/bin/env python3
"""
Setup Grafana with persistent storage and correct fuzz metrics dashboard.
This ensures dashboards don't get lost on system restarts.
"""
import json
import time
from typing import Any, Dict

import requests

GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASS = "admin"


def wait_for_grafana():
    """Wait for Grafana to be ready"""
    print("🔧 Waiting for Grafana to be ready...")
    for i in range(30):
        try:
            response = requests.get(f"{GRAFANA_URL}/api/health", timeout=5)
            if response.status_code == 200:
                print("✅ Grafana is ready")
                return True
        except:
            pass
        time.sleep(2)
    print("❌ Grafana not ready after 60 seconds")
    return False


def setup_prometheus_datasource():
    """Setup Prometheus data source"""
    print("📊 Setting up Prometheus data source...")

    # Check if datasource already exists
    response = requests.get(
        f"{GRAFANA_URL}/api/datasources", auth=(GRAFANA_USER, GRAFANA_PASS)
    )
    if response.status_code == 200:
        datasources = response.json()
        for ds in datasources:
            if ds.get("name") == "Prometheus":
                print("✅ Prometheus data source already exists")
                return ds["id"]

    # Create new datasource
    datasource_config = {
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://prometheus:9090",
        "access": "proxy",
        "isDefault": True,
    }

    response = requests.post(
        f"{GRAFANA_URL}/api/datasources",
        auth=(GRAFANA_USER, GRAFANA_PASS),
        json=datasource_config,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        print("✅ Prometheus data source added successfully")
        return response.json()["id"]
    else:
        print(f"❌ Failed to add data source: {response.text}")
        return None


def create_persistent_dashboard():
    """Create a persistent dashboard with fuzz metrics"""
    print("📈 Creating persistent RAFT dashboard with fuzz metrics...")

    dashboard_config = {
        "dashboard": {
            "title": "RAFT Metrics (Real-time Fuzz Data)",
            "uid": "raft-fuzz-metrics-persistent",
            "panels": [
                {
                    "title": "Proof Success Rate (Real-time)",
                    "type": "stat",
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                    "targets": [
                        {
                            "expr": "rate(fuzz_proof_pass_total[5m])",
                            "legendFormat": "Proofs/sec",
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "color": {"mode": "palette-classic"},
                            "custom": {"displayMode": "gradient-gauge"},
                        }
                    },
                },
                {
                    "title": "Spectral Radius (Real-time)",
                    "type": "stat",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                    "targets": [{"expr": "fuzz_spectral_radius", "legendFormat": "ρ"}],
                    "fieldConfig": {
                        "defaults": {
                            "color": {"mode": "thresholds"},
                            "thresholds": {
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "red", "value": 0.9},
                                ]
                            },
                        }
                    },
                },
                {
                    "title": "Energy Rate (Real-time)",
                    "type": "stat",
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                    "targets": [
                        {"expr": "fuzz_energy_rate_j_s", "legendFormat": "J/s"}
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "color": {"mode": "palette-classic"},
                            "unit": "joulepersec",
                        }
                    },
                },
                {
                    "title": "Total Cycles (Real-time)",
                    "type": "stat",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                    "targets": [{"expr": "fuzz_cycle_total", "legendFormat": "Cycles"}],
                    "fieldConfig": {
                        "defaults": {
                            "color": {"mode": "palette-classic"},
                            "unit": "short",
                        }
                    },
                },
                {
                    "title": "Proof Failures (Real-time)",
                    "type": "stat",
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
                    "targets": [
                        {"expr": "fuzz_proof_fail_total", "legendFormat": "Failures"}
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "color": {"mode": "palette-classic"},
                            "unit": "short",
                        }
                    },
                },
                {
                    "title": "Cycle Latency (Real-time)",
                    "type": "stat",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
                    "targets": [
                        {
                            "expr": "histogram_quantile(0.95, rate(fuzz_cycle_latency_seconds_bucket[5m]))",
                            "legendFormat": "95th percentile",
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {"color": {"mode": "palette-classic"}, "unit": "s"}
                    },
                },
            ],
            "time": {"from": "now-15m", "to": "now"},
            "refresh": "5s",
            "timezone": "browser",
        },
        "folderId": 0,
        "overwrite": True,
    }

    response = requests.post(
        f"{GRAFANA_URL}/api/dashboards/db",
        auth=(GRAFANA_USER, GRAFANA_PASS),
        json=dashboard_config,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ RAFT dashboard created successfully")
        print(f"📊 Dashboard URL: {GRAFANA_URL}{result['url']}")
        return result["url"]
    else:
        print(f"❌ Failed to create dashboard: {response.text}")
        return None


def main():
    """Main setup function"""
    print("🚀 Setting up Grafana with persistent storage...")

    if not wait_for_grafana():
        return False

    datasource_id = setup_prometheus_datasource()
    if not datasource_id:
        return False

    dashboard_url = create_persistent_dashboard()
    if not dashboard_url:
        return False

    print("\n🎉 Grafana setup complete!")
    print(f"📊 Access Grafana at: {GRAFANA_URL}")
    print(f"👤 Username: {GRAFANA_USER}")
    print(f"🔑 Password: {GRAFANA_PASS}")
    print(f"📈 Dashboard: {GRAFANA_URL}{dashboard_url}")
    print("\n💾 This dashboard is now persistent and won't be lost on restarts!")

    return True


if __name__ == "__main__":
    main()
