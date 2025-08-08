#!/usr/bin/env python3
import argparse
import random
import subprocess
import sys
import time
from pathlib import Path

SAFE_ADD = "# FUZZ-ADD seed={seed} t={t} id={rid}"


def sh(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def choose_files(repo: Path) -> list[Path]:
    # Only mutate tracked .py files under agent/; avoid relying on glob pathspecs
    out = sh(repo, "git", "ls-files").stdout.strip().splitlines()
    return [Path(repo, p) for p in out if p.startswith("agent/") and p.endswith(".py")]


def mutate_files(
    repo: Path, files: list[Path], rng: random.Random, adds: int, dels: int
) -> set[Path]:
    touched: set[Path] = set()
    for _ in range(adds + dels):
        if not files:
            break
        p = rng.choice(files)
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        lines = txt.splitlines()
        if not lines:
            lines = [""]
        tnow = int(time.time())
        # Prefer adds; delete only blank/comment lines to keep semantics safe
        if adds > 0:
            idx = rng.randrange(0, len(lines) + 1)
            rid = rng.randrange(1_000_000_000)
            lines.insert(idx, SAFE_ADD.format(seed=rng.seed, t=tnow, rid=rid))
            adds -= 1
        elif dels > 0:
            candidates = [
                i
                for i, l in enumerate(lines)
                if (not l.strip()) or l.lstrip().startswith("#")
            ]
            if candidates:
                i = rng.choice(candidates)
                lines.pop(i)
                dels -= 1
            else:
                idx = rng.randrange(0, len(lines) + 1)
                rid = rng.randrange(1_000_000_000)
                lines.insert(idx, SAFE_ADD.format(seed=rng.seed, t=tnow, rid=rid))
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        touched.add(p)
    return touched


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate fuzz patch via git diff")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--adds", type=int, default=20)
    ap.add_argument("--dels", type=int, default=10)
    ap.add_argument("--output", type=Path, default=Path("fuzz.patch"))
    args = ap.parse_args()

    repo = Path(".").resolve()
    # Must be a git repo with at least one commit
    try:
        sh(repo, "git", "rev-parse", "--show-toplevel")
        sh(repo, "git", "rev-parse", "HEAD")
    except subprocess.CalledProcessError:
        print("Error: run inside a git repo with an initial commit", file=sys.stderr)
        sys.exit(2)

    rng = random.Random(args.seed)
    rng.seed = args.seed  # store for mutate_files format string
    files = choose_files(repo)
    touched = mutate_files(repo, files, rng, args.adds, args.dels)

    # Produce a proper unified diff from tracked changes, limited to files we touched
    rel_paths = [str(p.relative_to(repo)) for p in sorted(touched)]
    if rel_paths:
        diff = sh(repo, "git", "diff", "--no-color", "--", *rel_paths).stdout
    else:
        diff = ""
    args.output.write_text(diff, encoding="utf-8")

    # Revert working tree to keep repo clean for callers
    sh(repo, "git", "checkout", "--", ".")

    print(f"Wrote {args.output} (len={len(diff)} bytes)")


if __name__ == "__main__":
    main()
