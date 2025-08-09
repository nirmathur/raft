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