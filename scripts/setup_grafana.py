#!/usr/bin/env python3
"""
Setup Grafana with Prometheus data source
"""
import json
import time

import requests

GRAFANA_URL = "http://localhost:3000"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin"


def wait_for_grafana():
    """Wait for Grafana to be ready"""
    for i in range(30):
        try:
            response = requests.get(f"{GRAFANA_URL}/api/health")
            if response.status_code == 200:
                print("✅ Grafana is ready")
                return True
        except requests.exceptions.ConnectionError:
            pass
        print(f"⏳ Waiting for Grafana... ({i+1}/30)")
        time.sleep(2)
    return False


def setup_prometheus_datasource():
    """Add Prometheus as a data source"""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # Create data source
    datasource = {
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://prometheus:9090",
        "access": "proxy",
        "isDefault": True,
    }

    try:
        response = requests.post(
            f"{GRAFANA_URL}/api/datasources",
            headers=headers,
            json=datasource,
            auth=(ADMIN_USER, ADMIN_PASSWORD),
        )

        if response.status_code == 200:
            print("✅ Prometheus data source added successfully")
            return True
        elif response.status_code == 409:
            print("ℹ️  Prometheus data source already exists")
            return True
        else:
            print(
                f"❌ Failed to add data source: {response.status_code} - {response.text}"
            )
            return False
    except Exception as e:
        print(f"❌ Error adding data source: {e}")
        return False


def create_dashboard():
    """Create a basic RAFT dashboard"""
    dashboard = {
        "dashboard": {
            "title": "RAFT Metrics",
            "panels": [
                {
                    "title": "Proof Success Rate",
                    "type": "stat",
                    "targets": [
                        {
                            "expr": "rate(raft_proof_pass_total[5m])",
                            "legendFormat": "Proofs/sec",
                        }
                    ],
                    "fieldConfig": {
                        "defaults": {
                            "color": {"mode": "palette-classic"},
                            "custom": {"displayMode": "gradient-gauge"},
                        }
                    },
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                },
                {
                    "title": "Spectral Radius",
                    "type": "timeseries",
                    "targets": [{"expr": "raft_spectral_rho", "legendFormat": "ρ"}],
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                },
                {
                    "title": "Energy Rate",
                    "type": "timeseries",
                    "targets": [
                        {"expr": "raft_energy_rate_j_s", "legendFormat": "J/s"}
                    ],
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                },
            ],
        },
        "folderId": 0,
        "overwrite": True,
    }

    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        response = requests.post(
            f"{GRAFANA_URL}/api/dashboards/db",
            headers=headers,
            json=dashboard,
            auth=(ADMIN_USER, ADMIN_PASSWORD),
        )

        if response.status_code == 200:
            print("✅ RAFT dashboard created successfully")
            return True
        else:
            print(
                f"❌ Failed to create dashboard: {response.status_code} - {response.text}"
            )
            return False
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return False


def main():
    print("🔧 Setting up Grafana...")

    if not wait_for_grafana():
        print("❌ Grafana is not ready")
        return

    if not setup_prometheus_datasource():
        print("❌ Failed to setup Prometheus data source")
        return

    if not create_dashboard():
        print("❌ Failed to create dashboard")
        return

    print("\n🎉 Grafana setup complete!")
    print(f"📊 Access Grafana at: {GRAFANA_URL}")
    print("👤 Username: admin")
    print("🔑 Password: admin")
    print("📈 Dashboard: RAFT Metrics")


if __name__ == "__main__":
    main()
