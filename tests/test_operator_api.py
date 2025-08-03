import os
import signal
import subprocess
import time

import requests

TOKEN = os.getenv(
    "OPERATOR_TOKEN", "devtoken"
)  # matches the default in operator_api.py
HEAD = {"authorization": f"Bearer {TOKEN}"}


def _start_server():
    proc = subprocess.Popen(
        ["uvicorn", "agent.core.operator_api:app", "--port", "8100"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    return proc


def test_pause_endpoint():
    proc = _start_server()
    try:
        url = "http://127.0.0.1:8100"
        r = requests.post(url + "/pause", json={"flag": True}, headers=HEAD, timeout=2)
        assert r.json()["pause"] is True
        r = requests.get(url + "/state", headers=HEAD, timeout=2)
        assert r.json()["pause"] is True
    finally:
        proc.send_signal(signal.SIGINT)
