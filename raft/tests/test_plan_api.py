import pytest
from pydantic import ValidationError

from agent.core.plan_models import (
    ARTIFACTS_ROOT,
    Fetch,
    Plan,
    Run,
    WriteFile,
)


def test_models_validation_only():
    # Valid: minimal plan with Fetch without save_as
    plan1 = Plan(
        name="test",
        steps=[
            Fetch(op="Fetch", url="https://example.com"),
        ],
    )
    assert plan1.steps and isinstance(plan1.steps[0], Fetch)

    # Valid: full plan with Fetch(save_as), WriteFile, Run
    plan2 = Plan(
        name=" ok ",
        tokens=0,
        steps=[
            Fetch(
                op="Fetch",
                url="https://example.com",
                save_as=f"{ARTIFACTS_ROOT}/web/robots.txt",
            ),
            WriteFile(
                op="WriteFile",
                path=f"{ARTIFACTS_ROOT}/notes/a.txt",
                content="ok",
            ),
            Run(op="Run", target="governor.one_cycle"),
        ],
    )
    # Ensure normalization retained posix and artifacts prefix
    assert plan2.steps[0].save_as == f"{ARTIFACTS_ROOT}/web/robots.txt"
    assert plan2.steps[1].path == f"{ARTIFACTS_ROOT}/notes/a.txt"

    # Invalids
    with pytest.raises(ValidationError):
        # Absolute path rejected
        WriteFile(op="WriteFile", path="/etc/passwd", content="x")

    with pytest.raises(ValidationError):
        # Traversal rejected
        WriteFile(op="WriteFile", path=f"{ARTIFACTS_ROOT}/../../etc/shadow", content="x")

    with pytest.raises(ValidationError):
        # Missing artifacts/ prefix
        WriteFile(op="WriteFile", path="notes/a.txt", content="x")

    with pytest.raises(ValidationError):
        # Bad URL scheme
        Fetch(op="Fetch", url="ftp://example.com/a")

    with pytest.raises(ValidationError):
        # Disallowed run target
        Run(op="Run", target="governor.two_cycles")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        # Empty steps
        Plan(name="x", steps=[])

    with pytest.raises(ValidationError):
        # Negative tokens
        Plan(name="x", tokens=-1, steps=[Run(op="Run", target="governor.one_cycle")])

    # Additional Fetch URL validations
    with pytest.raises(ValidationError):
        # Missing host (netloc empty)
        Fetch(op="Fetch", url="https:///path")

    # Valid: IP host is allowed
    plan3 = Plan(
        name="fetch ip",
        steps=[Fetch(op="Fetch", url="https://127.0.0.1", save_as=f"{ARTIFACTS_ROOT}/web/file.txt")],
    )
    assert plan3.steps[0].save_as == f"{ARTIFACTS_ROOT}/web/file.txt"

    # Invalid: save_as missing artifacts/
    with pytest.raises(ValidationError):
        Fetch(op="Fetch", url="https://example.com", save_as="notes/a.txt")

    # Invalid: save_as traversal
    with pytest.raises(ValidationError):
        Fetch(op="Fetch", url="https://example.com", save_as=f"{ARTIFACTS_ROOT}/../notes/a.txt")

    # WriteFile normalization tests
    wf_backslashes = WriteFile(op="WriteFile", path=f"{ARTIFACTS_ROOT}\\notes\\a.txt", content="x")
    assert wf_backslashes.path == f"{ARTIFACTS_ROOT}/notes/a.txt"

    wf_doubles = WriteFile(op="WriteFile", path=f"{ARTIFACTS_ROOT}//notes//a.txt", content="x")
    assert wf_doubles.path == f"{ARTIFACTS_ROOT}/notes/a.txt"

    # Plan name trimming
    with pytest.raises(ValidationError):
        Plan(name=" ", steps=[Run(op="Run", target="governor.one_cycle")])

    plan_trim = Plan(name=" ok ", steps=[Run(op="Run", target="governor.one_cycle")])
    assert plan_trim.name == "ok"

    # Optional: directory-looking target should be rejected (we chose to forbid)
    with pytest.raises(ValidationError):
        WriteFile(op="WriteFile", path=f"{ARTIFACTS_ROOT}/dir/", content="x")

    # Scheme normalization: uppercase scheme is allowed
    assert Fetch(op="Fetch", url="HTTP://example.com")

    # Directory-looking save_as should be rejected
    with pytest.raises(ValidationError):
        Fetch(op="Fetch", url="https://example.com", save_as=f"{ARTIFACTS_ROOT}/dir/")

    # Dict-based plan creation
    plan_dict = {
        "name": "dict plan",
        "steps": [
            {"op": "Fetch", "url": "https://example.com", "save_as": f"{ARTIFACTS_ROOT}/web/x.txt"},
            {"op": "WriteFile", "path": "./artifacts/notes/a.txt", "content": "ok"},
            {"op": "Run", "target": "governor.one_cycle"},
        ],
    }
    p = Plan(**plan_dict)
    assert isinstance(p.steps[0], Fetch) and p.steps[1].path == "artifacts/notes/a.txt"

    # Extra fields are rejected
    with pytest.raises(ValidationError):
        Run(op="Run", target="governor.one_cycle", junk=1)  # type: ignore

    # Root-only paths are rejected
    with pytest.raises(ValidationError):
        WriteFile(op="WriteFile", path="artifacts", content="x")
    with pytest.raises(ValidationError):
        WriteFile(op="WriteFile", path="artifacts/.", content="x")