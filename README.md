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

## Performance Comparison Harness

The comparison harness allows you to benchmark RAFT performance against a baseline no-op implementation.

### Usage

```bash
# Run baseline comparison (no-op stub with minimal processing)
poetry run python scripts/compare_baseline.py --runs 10 --mode baseline

# Run RAFT comparison (full governor cycles with all guards)
poetry run python scripts/compare_baseline.py --runs 10 --mode raft
```

### Metrics Captured

The harness captures the following metrics for each run:

- **success**: Whether the cycle completed successfully (bool)
- **latency**: Time taken for the cycle in seconds (float)
- **rho**: Spectral radius value (float)
- **energy**: Energy consumption in Joules (float)

### Output

Results are written to CSV files:
- `output_baseline.csv` - Results from baseline mode
- `output_raft.csv` - Results from RAFT mode

CSV format: `run,mode,timestamp,success,latency,rho,energy`

### Example Analysis

```bash
# Compare 50 runs of each mode
poetry run python scripts/compare_baseline.py --runs 50 --mode baseline
poetry run python scripts/compare_baseline.py --runs 50 --mode raft

# Analyze results (using pandas/matplotlib)
python -c "
import pandas as pd
baseline = pd.read_csv('output_baseline.csv')
raft = pd.read_csv('output_raft.csv')

print('Baseline - Mean latency:', baseline['latency'].mean())
print('RAFT - Mean latency:', raft['latency'].mean())
print('Performance overhead:', raft['latency'].mean() / baseline['latency'].mean())
"
```
