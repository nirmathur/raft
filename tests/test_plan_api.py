from agent.core.plan_smt import verify_plan
from fastapi.testclient import TestClient
from agent.core.operator_api import app
from agent.core.plan_models import Plan


def test_prove_safe_plan_unsat():
    plan = Plan(
        steps=[
            {"op": "Fetch", "url": "https://example.com/index.html"},
            {"op": "WriteFile", "path": "artifacts/out.txt", "content": "ok"},
            {"op": "Run", "target": "governor.one_cycle"},
        ]
    )
    passed, counterexample = verify_plan(plan)
    assert passed is True
    assert counterexample is None


def test_prove_unsafe_writefile_outside_artifacts():
    plan = Plan(
        steps=[
            {"op": "Fetch", "url": "http://good.host"},
            {"op": "WriteFile", "path": "not_artifacts/x.txt", "content": "bad"},
        ]
    )
    passed, counterexample = verify_plan(plan)
    assert passed is False
    assert isinstance(counterexample, dict)
    assert counterexample.get("step_idx") == 1
    assert counterexample.get("field") == "path"


def test_operator_prove_endpoint():
    client = TestClient(app)

    # Patch token for this client
    from unittest.mock import patch

    TOKEN = "test-token"
    HEADERS = {"authorization": f"Bearer {TOKEN}"}

    safe_body = {
        "steps": [
            {"op": "Fetch", "url": "https://a.b"},
            {"op": "WriteFile", "path": "artifacts/a.txt", "content": "x"},
            {"op": "Run", "target": "governor.one_cycle"},
        ]
    }
    unsafe_body = {
        "steps": [
            {"op": "WriteFile", "path": "../../etc/passwd", "content": "x"}
        ]
    }

    with patch("agent.core.operator_api.TOKEN", TOKEN):
        r1 = client.post("/prove", json=safe_body, headers=HEADERS)
        assert r1.status_code == 200
        assert r1.json()["passed"] is True
        assert r1.json()["counterexample"] is None

        r2 = client.post("/prove", json=unsafe_body, headers=HEADERS)
        assert r2.status_code == 200
        data = r2.json()
        assert data["passed"] is False
        assert isinstance(data["counterexample"], dict)