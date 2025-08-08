from __future__ import annotations

import json
from typing import Optional

from click.testing import CliRunner
from typer.main import get_command

from agent import cli


def test_version_prints_mocked_version(monkeypatch):
    class Dummy:
        def __call__(self, name: str) -> str:  # type: ignore[override]
            return "9.9.9"

    # Patch importlib.metadata.version used inside command
    monkeypatch.setitem(
        cli.__dict__, "__name__", cli.__name__
    )  # ensure module dict available

    # Patch the version function resolution path used in cli.version_cmd
    def fake_version_cmd():
        from importlib.metadata import version as _version  # type: ignore

        return _version("raft")

    # Monkeypatch importlib.metadata.version indirectly by patching the command to call the real resolver
    # Easiest is to patch the underlying function used: replace importlib.metadata.version with lambda
    import importlib.metadata as im

    monkeypatch.setattr(im, "version", lambda name: "9.9.9")

    runner = CliRunner()
    result = runner.invoke(
        get_command(cli.app), ["version"]
    )  # convert Typer app to Click command
    assert result.exit_code == 0
    assert result.output.strip() == "9.9.9"


def test_one_cycle_prints_json(monkeypatch):
    # Ensure run_one_cycle is not hitting real heavy deps
    monkeypatch.setattr(cli, "run_one_cycle", lambda: True)
    monkeypatch.setattr(cli, "_estimate_rho", lambda: 0.5)
    monkeypatch.setattr(cli, "_estimate_energy", lambda rho: 1.0)

    runner = CliRunner()
    result = runner.invoke(
        get_command(cli.app), ["one-cycle"]
    )  # convert Typer app to Click command
    assert result.exit_code == 0

    data = json.loads(result.output.strip())
    assert set(data.keys()) == {"status", "rho", "energy"}
    assert data["status"] == "ok"
    assert data["rho"] == 0.5
    assert data["energy"] == 1.0


def test_run_cycles_count(monkeypatch):
    calls = {"count": 0}

    def fake_cycle() -> bool:
        calls["count"] += 1
        return True

    monkeypatch.setattr(cli, "run_one_cycle", fake_cycle)
    # Avoid spinning a real server
    monkeypatch.setattr(cli, "start_http_server", lambda port: None)

    runner = CliRunner()
    # interval 0 to be fast; -n 2 should run exactly twice
    result = runner.invoke(get_command(cli.app), ["run", "-n", "2", "--interval", "0"])  # type: ignore[list-item]
    assert result.exit_code == 0
    assert calls["count"] == 2
