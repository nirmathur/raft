# example Background Agent Template

This template provides a RAFT-compliant background agent for example.

## Features

- ✅ RAFT charter compliance (xˣ‑0 through xˣ‑34)
- ✅ Spectral radius monitoring (xˣ‑17)
- ✅ Z3 proof verification (xˣ‑22a)
- ✅ Energy monitoring (xˣ‑29)
- ✅ Event logging and audit trails
- ✅ Operator control via API
- ✅ Graceful shutdown handling

## Usage

### Local Development

```bash
# Install dependencies
poetry install

# Run the agent
python templates/example_background_agent.py
```

### Docker Deployment

```bash
# Build and run with docker-compose
docker-compose -f templates/docker-compose.example.yml up -d

# Or build manually
docker build -f templates/Dockerfile.example -t example-agent .
docker run -d --name example-agent example-agent
```

## Configuration

Edit the `config` dictionary in `main()` to customize:
- Task queue names
- Retry policies
- Timeouts
- Other agent-specific settings

## Monitoring

The agent provides:
- Structured logging via loguru
- Event recording via `agent.core.event_log`
- Energy consumption tracking
- Spectral radius monitoring
- Operator API integration

## Compliance

This template ensures compliance with all RAFT charter clauses:
- xˣ‑0: Versioning and meta-rules
- xˣ‑1: Failure logging
- xˣ‑2: Critic node in reasoning loops
- xˣ‑17: Spectral radius < 0.9
- xˣ‑22a: Z3 proof verification
- xˣ‑29: Energy monitoring
- And all other applicable clauses

## Customization

1. Replace `_agent_logic()` with your specific agent behavior
2. Update `_compute_jacobian()` with actual system dynamics
3. Implement `_build_smt_diff()` for real change verification
4. Add your specific configuration parameters
5. Extend logging and monitoring as needed
