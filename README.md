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

## Spectral Radius Estimation

RAFT includes a sophisticated spectral radius estimation system using PyTorch and functorch for real-time stability monitoring.

### Overview

The spectral radius (ρ) is the largest eigenvalue magnitude of the Jacobian matrix of a neural network. RAFT monitors this to ensure system stability according to charter clause x^x-17, requiring ρ < 0.9.

### Components

#### 1. SimpleNet Neural Network Model

Located in `agent/core/model.py`, provides a configurable neural network for spectral analysis:

```python
from agent.core.model import SimpleNet

# Create a network with 4 inputs, 4 outputs, 64 hidden units
model = SimpleNet(in_dim=4, out_dim=4, hidden_dim=64, activation='tanh')
```

**Parameters:**
- `in_dim`: Input dimension
- `out_dim`: Output dimension  
- `hidden_dim`: Hidden layer size (default: 64)
- `activation`: Activation function ('relu', 'tanh', 'sigmoid') (default: 'tanh')

#### 2. Spectral Radius Functions

Located in `agent/core/spectral.py`, provides two main functions:

##### Full Jacobian Computation
```python
from agent.core.spectral import full_jacobian
import torch

def my_function(x):
    return x ** 2 + 0.5 * x

x = torch.tensor([1.0, 2.0], requires_grad=True)
jacobian = full_jacobian(my_function, x)
```

##### Power Iteration Spectral Radius Estimation
```python
from agent.core.spectral import estimate_spectral_radius
import torch

model = SimpleNet(in_dim=3, out_dim=3)
x0 = torch.randn(3, requires_grad=True)
rho = estimate_spectral_radius(model, x0, n_iter=10)
print(f"Spectral radius: {rho:.6f}")
```

**Parameters:**
- `f`: Function to analyze (must be differentiable)
- `x`: Input point for evaluation
- `n_iter`: Number of power iterations (default: 5)

### Integration with Governor

The governor (`agent/core/governor.py`) automatically uses the spectral radius estimator during each cycle:

```python
# 2 ─── Spectral‑radius guard (xˣ‑17)
x0 = torch.randn(4, requires_grad=True)  # Random input point
rho = estimate_spectral_radius(_SPECTRAL_MODEL, x0, n_iter=10)

if rho >= MAX_SPECTRAL_RADIUS:  # 0.9 threshold
    logger.error("Spectral radius breach - rollback triggered")
    return False
```

### Technical Details

#### Power Iteration Algorithm

The system uses power iteration to estimate the largest eigenvalue without computing the full Jacobian:

1. Initialize random vector `v`
2. For `n_iter` iterations:
   - Compute `v_new = J @ v` using Jacobian-vector products (JVP)
   - Normalize: `v = v_new / ||v_new||`
3. Estimate eigenvalue: `λ = v^T @ (J @ v)`

#### Handling Non-Square Jacobians

For neural networks with different input/output dimensions, the algorithm works with `J^T @ J`:

- First compute `Jv` using forward-mode autodiff
- Then compute `J^T @ (Jv)` using reverse-mode autodiff  
- This ensures a square matrix for power iteration

#### Performance Benefits

- **Memory Efficient**: No need to store full Jacobian matrices
- **Scalable**: Works with large neural networks
- **Fast**: Leverages PyTorch's optimized autodiff
- **Accurate**: Converges quickly for most well-conditioned systems

### Testing

Comprehensive tests are available in `tests/test_spectral_estimator.py`:

```bash
# Run spectral radius tests
pytest tests/test_spectral_estimator.py -v

# Run all spectral-related tests  
pytest tests/test_spectral_estimator.py tests/test_spectral_guard.py -v
```

Test coverage includes:
- Linear transformations with known spectral radii
- Neural networks with different architectures
- Edge cases (zero gradients, non-square Jacobians)
- Reproducibility and convergence verification

### Charter Compliance

This implementation satisfies charter clause x^x-17 by providing:
- Real-time spectral radius monitoring
- Automatic rollback on stability violations
- Configurable thresholds and iteration counts
- Comprehensive logging and metrics
