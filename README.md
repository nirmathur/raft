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

## CLI Usage

RAFT provides a command-line interface for managing the agent system:

```bash
# Install RAFT (from this directory)
poetry install

# Show help
raft --help

# Run continuous governor loop with metrics server
raft run                    # Metrics on http://localhost:8002/metrics
raft run --metrics-port 9090
raft run --cycle-interval 2.0

# Run a single cycle and get JSON status
raft one-cycle

# Show version
raft version
```

### CLI Commands

- **`raft run`**: Starts the continuous governor loop with Prometheus metrics server
  - `--metrics-port`: Port for metrics server (default: 8002)
  - `--cycle-interval`: Seconds between cycles (default: 1.0)
  
- **`raft one-cycle`**: Executes exactly one governor cycle and outputs JSON:
  ```json
  {
    "status": "success",
    "rho": 0.456,
    "energy": 1234567.89
  }
  ```
  
- **`raft version`**: Displays the current RAFT version

- **Global options**:
  - `--verbose, -v`: Enable verbose logging
