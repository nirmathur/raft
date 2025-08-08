### Nightly Fuzz Automation

This repository includes a nightly fuzzing job that generates a harmless unified diff against files under `agent/` and runs a single RAFT governor cycle under controlled, mocked conditions.

### What the fuzz does

- **Generator**: `scripts/fuzz_diff_generator.py` creates `fuzz.patch` consisting of added comment lines and occasional deletions of blank/comment lines in `.py` files under `agent/`.
- **Safety**: The generator avoids forbidden tokens (e.g., `subprocess`, `eval`, `exec`); it does not change executable code.
- **Runner test**: `tests/test_fuzz_runner.py` applies `fuzz.patch` in a temporary git repo and runs one governor cycle with heavy components mocked out. It asserts the cycle completes or rolls back and that logs include either `cycle-complete` or `rollback`.

### Run locally

Example commands:

```
poetry run python scripts/fuzz_diff_generator.py --adds 10 --dels 5
poetry run pytest -q tests/test_fuzz_runner.py
```

Notes:
- The test does not require Redis, Ollama, or Docker.
- Imports are kept lazy; heavy pieces (Z3/Redis/torch energy) are mocked.
- If importing `agent` becomes heavy on your machine, the test uses `pytest.importorskip("agent")` to skip instead of failing.

### CI

- Workflow file: `.github/workflows/fuzz.yml`.
- Triggers: nightly cron at 02:00 UTC and manual `workflow_dispatch`.
- Jobs:
  - Setup Python 3.11, install Poetry deps with cache.
  - Generate fuzz patch using a deterministic seed derived from the workflow run id.
  - Run only the fuzz runner test.
  - On failure, a GitHub issue titled `Nightly fuzz failed (run <run_id>)` is created or updated with the job URL and the last ~200 lines of pytest output.
- Required secret: uses the built-in `GITHUB_TOKEN` only; no other secrets or services are required.

### Quieting noisy runs

If you need to temporarily silence the nightly fuzz job:
- Disable the schedule by commenting out the `cron` stanza in `.github/workflows/fuzz.yml`, or
- Use the Actions UI to disable the workflow for a period.


