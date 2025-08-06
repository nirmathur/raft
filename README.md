# Recursive Agent for Formal Trust (RAFT)

RAFT is a recursive agent system with formal trust guarantees, featuring spectral radius guards, proof gates, and operator escape hatches.

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose

### Environment Variables

#### Operator API Configuration
- `OPERATOR_TOKEN`: Bearer token for operator API authentication (default: "devtoken")
- `ENERGY_GUARD_ENABLED`: Enable/disable energy monitoring (default: "true", set to "false" to disable)

### Ports

The system uses the following ports:

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache and pub/sub |
| ChromaDB | 8000 | Vector database |
| Ollama | 11434 | LLM inference |
| Operator API | 8001 | Control interface |

### Running with Docker

```bash
cd docker
docker-compose up -d
```

The operator API will be available at `http://localhost:8001` with the token set in the environment.

### Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run governor
poetry run python -m agent.core.governor
```

## SMT Proof Gate

RAFT includes a Z3-based proof gate (`agent.core.smt_verifier`) that validates safety properties of code modifications. The proof gate accepts SMT-LIB2 strings and returns structured results with counterexample extraction for failed proofs.

### Counterexample Format

When a proof fails (SAT result), the verifier extracts variable assignments that violate the safety properties:

```json
{
    "result": false,
    "counterexample": {
        "variable_name": "value",
        "x": 15,
        "y": 3,
        "flag": "true"
    }
}
```

For successful proofs (UNSAT result):

```json
{
    "result": true,
    "counterexample": null
}
```

### Usage Example

```python
from agent.core.smt_verifier import verify

# Safe SMT formula
safe_smt = "(assert true)"
result = verify(safe_smt, charter_hash)
# Returns: {"result": true, "counterexample": null}

# Unsafe SMT formula with variables
unsafe_smt = """
(declare-const x Int)
(assert (> x 10))
(assert (< x 5))
"""
result = verify(unsafe_smt, charter_hash)
# Returns: {"result": false, "counterexample": {"x": "some_value"}}
```

### Backward Compatibility

For existing code expecting boolean returns, use `verify_bool()`:

```python
from agent.core.smt_verifier import verify_bool

is_safe = verify_bool(smt_formula, charter_hash)  # Returns boolean
```

### Caching

Results are cached in Redis for 24 hours, keyed by SHA-256 hash of the SMT formula and charter hash. Failed proofs cache their counterexamples for faster retrieval.
