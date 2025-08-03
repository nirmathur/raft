from pathlib import Path


def load_clauses(file: Path = Path(__file__).parents[2] / "charter.md"):
    clauses = {}
    for line in file.read_text().splitlines():
        if line.startswith("- "):
            _, rest = line.split(" ", 1)
            cid, text = rest.split("  ", 1)
            clauses[cid.strip()] = text.strip()
    return clauses
