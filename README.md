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

#### Drift Detection Configuration

- `DRIFT_WINDOW`: Sliding-window size (*N* cycles) for spectral-radius drift detection (default: `10`).
  A larger window smooths out noise but delays alerting; a smaller window reacts
  faster at the risk of false positives.

- `DRIFT_MEAN_THRESHOLD`: Rolling-mean drift threshold (absolute |Δρ|, default `0.05`).
- `DRIFT_MAX_THRESHOLD`: Maximum single-step drift threshold (absolute |Δρ|, default `0.10`).

Tuning guideline: set *mean_threshold* roughly to expected noise σ; choose *max_threshold* at ≈2–3 × σ to catch genuine spikes.

Drift detection enforces charter clauses xˣ-19 / xˣ-24 / xˣ-25 by raising an
alert when:

1. Rolling *mean* drift between consecutive spectral-radius measurements exceeds `0.05`, **or**
2. Any single jump (*max* drift) exceeds `0.10`.

The thresholds are hard-coded in `agent/core/drift_monitor.py` and should only be
modified with proper charter approval.

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


## SMT-LIB2 Diff Analysis

RAFT includes a sophisticated SMT-LIB2 based Git diff analyzer that uses Z3py to verify the safety of code changes. The system implements two key invariants:

1. **No forbidden API calls** - Detects dangerous operations like `exec()`, `subprocess`, `eval()`, etc.
2. **Goal preservation** - Ensures function renames preserve their signatures

**Important**: Signature mismatch returns `(assert false)` and bumps risk ≥ 0.9.

**Charter clauses (`x^x-22`, `x^x-23`, …) are injected at build time; see `get_forbidden_patterns()`.**

### Core Components

#### Diff Builder API

The main entry point is `build_smt_diff()` which converts Git diffs into SMT-LIB2 safety assertions:

```python
from agent.core.diff_builder import build_smt_diff, analyze_diff_context

# Safe diff example
safe_diff = """diff --git a/example.py b/example.py
@@ -1,2 +1,3 @@
 def hello():
     pass
+    print("Hello world")
"""

result = build_smt_diff(safe_diff)
print(result)  # Output: "(assert true)"

# Unsafe diff example  
unsafe_diff = """diff --git a/dangerous.py b/dangerous.py
@@ -1,2 +1,3 @@
 def hack():
+    exec('rm -rf /')
     pass
"""

result = build_smt_diff(unsafe_diff)
print(result)  # Output: "(assert false)"
```

#### Comprehensive Diff Analysis

Get detailed analysis including risk scores and violation details:

```python
from agent.core.diff_builder import analyze_diff_context

context = analyze_diff_context(unsafe_diff)
print(f"Risk score: {context['risk_score']}")
print(f"SMT result: {context['smt_result']}")
print(f"Forbidden violations: {context['forbidden_violations']}")
print(f"Function renames: {context['function_renames']}")
```

#### AST-based Diff Parsing

Parse diffs into structured representations:

```python
from agent.core.diff_builder import parse_diff_to_ast

ast = parse_diff_to_ast(diff_text)
print(f"Added lines: {len(ast.added_lines)}")
print(f"Removed lines: {len(ast.removed_lines)}")
print(f"Modified files: {ast.modified_files}")
print(f"Function renames: {ast.function_renames}")
```

### Forbidden Patterns

The system detects these dangerous patterns by default:

- `\bsubprocess\b` - Subprocess execution
- `\bos\.system\b` - OS system calls
- `\beval\b` - Dynamic code evaluation
- `\bexec\b` - Code execution
- `\bimport\s+\*` - Wildcard imports
- `\b__import__\b` - Dynamic imports
- `\bglobals\b` - Global manipulation
- `\blocals\b` - Local manipulation

### Function Rename Detection

The system can detect when functions are renamed and verify that their signatures are preserved:

```python
rename_diff = """diff --git a/refactor.py b/refactor.py
@@ -1,2 +1,2 @@
-def calculate_sum(a, b):
+def compute_sum(a, b):
     return a + b
"""

context = analyze_diff_context(rename_diff)
print(context['function_renames'])  # {'calculate_sum': 'compute_sum'}
```

### Custom Forbidden Patterns

You can define custom forbidden patterns for specific use cases:

```python
from agent.core.diff_builder import build_advanced_smt

custom_patterns = [
    r"\bcustom_dangerous_function\b",
    r"\blegacy_deprecated_api\b"
]

result = build_advanced_smt(diff_text, custom_patterns)
```

### Charter-based Configuration

Integrate with RAFT's charter system for dynamic pattern configuration. Charter clauses are now automatically merged with default forbidden patterns:

```python
from agent.core.diff_builder import build_smt_with_charter, get_forbidden_patterns

charter_clauses = {
    "x^x-22": "No dangerous imports",
    "x^x-23": "Preserve function signatures", 
    "x^x-99": "forbidden `pickle` - No pickle imports allowed"
}

# Charter patterns are automatically merged at build time
result = build_smt_with_charter(diff_text, charter_clauses)

# Or get the merged pattern list directly
patterns = get_forbidden_patterns(charter_clauses)
print(f"Total patterns: {len(patterns)}")  # Includes defaults + charter patterns
```

### SMT Verifier and Proof Gates

The production proof-gate system uses Z3 to formally verify safety properties of code changes. The `smt_verifier.verify()` function processes SMT-LIB2 formulas generated by the diff builder and returns detailed results including counterexamples for failed proofs.

#### Basic Verification

```python
from agent.core.smt_verifier import verify
import hashlib

charter_hash = hashlib.sha256(b"your_charter").hexdigest()

# Safe proof (UNSAT - no counterexample exists)
safe_smt = """
(declare-fun has_forbidden_call () Bool)
(assert (not has_forbidden_call))
"""

result = verify(safe_smt, charter_hash)
print(result)  # True - proof succeeds

# Unsafe proof (SAT - counterexample found)
unsafe_smt = """
(declare-fun dangerous_call () Bool)
(declare-fun call_type () String)
(assert dangerous_call)
(assert (= call_type "subprocess.call"))
"""

result = verify(unsafe_smt, charter_hash)
print(result)  # (False, counterexample_data)
```

#### Counterexample Format

When a proof fails (SAT result), the verifier returns a tuple `(False, counterexample_data)` where `counterexample_data` is a JSON object with the following structure:

```json
{
  "counterexample": {
    "dangerous_call": "true",
    "call_type": "subprocess.call",
    "file_location": "agent/core/governor.py"
  },
  "model_summary": "Found counterexample with 3 variable(s): dangerous_call=true, call_type=subprocess.call, file_location=agent/core/governor.py"
}
```

#### Redis Caching with Counterexamples

The verifier caches both successful proofs and failed proofs with their counterexamples:

- **Successful proofs (UNSAT)**: Cached as `"1"` for 24 hours
- **Failed proofs (SAT)**: Cached as `"0"` with counterexample data stored separately

Cache keys are generated as: `sha256(smt_formula):charter_hash`

#### Integration with Diff Builder

The complete proof gate workflow:

```python
from agent.core.diff_builder import build_smt_diff
from agent.core.smt_verifier import verify
import hashlib

# 1. Convert diff to SMT formula
diff_text = """diff --git a/dangerous.py b/dangerous.py
@@ -1,2 +1,3 @@
 def hack():
+    exec('rm -rf /')
     pass
"""

smt_formula = build_smt_diff(diff_text)
print(f"SMT formula: {smt_formula}")

# 2. Verify with proof gate
charter_hash = hashlib.sha256(b"charter_content").hexdigest()
result = verify(smt_formula, charter_hash)

if result is True:
    print("✅ Proof passed - diff is safe")
elif isinstance(result, tuple):
    success, counterexample = result
    print("❌ Proof failed - counterexample found:")
    print(f"Variables: {counterexample['counterexample']}")
    print(f"Summary: {counterexample['model_summary']}")
```

## Benchmarking

Measure SMT solver performance on diffs of varying complexity:

### Quick Benchmark

```bash
python scripts/benchmark_smt.py --quick --verbose
```

### Comprehensive Benchmark

```bash
python scripts/benchmark_smt.py --output benchmark_results.json --verbose
```

### Benchmark Categories

The benchmark suite tests several scenarios:

- **Size Scaling**: Diffs from 10 to 1000 lines
- **Forbidden Patterns**: Various ratios of dangerous code
- **Function Renames**: 1 to 50 function renames
- **File Scaling**: 1 to 50 modified files

### Example Benchmark Output

```
============================================================
BENCHMARK RESULTS SUMMARY
============================================================
Total benchmarks: 27
Total time: 0.0456s
Average time per benchmark: 0.0017s
Min time: 0.0003s
Max time: 0.0089s

Performance Insights:
  • SMT solver scales well: 100.0x size increase → 2.1x time increase
  • Forbidden pattern detection is efficient: only 1.2x slower than safe diffs
```

## API Reference

### Core Functions

#### `build_smt_diff(diff_text: str) -> str`

Main entry point that converts a Git diff into an SMT-LIB2 formula.

**Parameters:**
- `diff_text`: Git unified diff text

**Returns:** 
- `"(assert true)"` for safe diffs
- `"(assert false)"` for unsafe diffs

#### `analyze_diff_context(diff_text: str) -> Dict[str, Any]`

Comprehensive analysis of a Git diff including risk assessment.

**Returns a dictionary with:**
- `file_count`: Number of modified files
- `added_lines`: Number of added lines
- `removed_lines`: Number of removed lines  
- `risk_score`: Float between 0.0 and 1.0
- `forbidden_violations`: List of detected violations
- `function_renames`: Dictionary of old_name -> new_name
- `smt_result`: SMT formula result
- `modified_files`: List of file paths

#### `parse_diff_to_ast(diff_text: str) -> DiffAST`

Parse Git diff into structured AST representation.

**Returns:** `DiffAST` object with:
- `added_lines`: List of `DiffLine` objects
- `removed_lines`: List of `DiffLine` objects
- `modified_files`: Set of file paths
- `function_renames`: Dictionary of renames
- `function_signatures`: Dictionary of function signatures

### Data Classes

#### `DiffLine`
- `line_type`: '+', '-', or ' '
- `content`: Line content
- `file_path`: File path
- `line_number`: Line number in diff

#### `FunctionSignature`
- `name`: Function name
- `args`: List of argument names
- `returns`: Return type annotation (optional)

#### `DiffAST`
- `added_lines`: List of added lines
- `removed_lines`: List of removed lines
- `modified_files`: Set of file paths
- `function_renames`: Dictionary of function renames
- `function_signatures`: Dictionary of function signatures

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
poetry run pytest

# Run only diff builder tests
poetry run pytest tests/test_diff_builder.py

# Run with verbose output
poetry run pytest tests/test_diff_builder.py -v
```

### Test Categories

- **Git Diff Parsing**: Tests for parsing various diff formats
- **SMT Formula Building**: Tests for SMT-LIB2 generation
- **Forbidden Pattern Detection**: Tests for security violation detection
- **Function Rename Analysis**: Tests for signature preservation
- **Edge Cases**: Tests for malformed inputs and error handling

## Implementation Details

### Architecture

The SMT diff builder consists of several components:

1. **GitDiffParser**: Parses unified diffs into structured ASTs
2. **SMTDiffBuilder**: Builds Z3 SMT formulas from ASTs
3. **Pattern Detection**: Regex-based forbidden pattern matching
4. **Function Analysis**: Signature extraction and comparison

### Z3 Integration

The system uses Z3py to create formal logical assertions:

- **Forbidden API assertions**: `(assert (forall ((line String)) (not (contains line "exec"))))`
- **Goal preservation**: Function equivalence assertions using Z3 quantifiers
- **Context management**: Proper Z3 context handling for performance

### Performance Characteristics

Based on benchmarking:

- **Linear scaling**: Performance scales well with diff size
- **Low overhead**: Forbidden pattern detection adds minimal overhead
- **Memory efficient**: Low memory usage even for large diffs
- **Fast startup**: Quick initialization and processing

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
- `x`: Input point for evaluation (raises ValueError if `x.dim() > 2`)
- `n_iter`: Maximum number of power iterations (default: 5, hard upper bound)
- `tolerance`: Convergence tolerance for early stopping (default: 1e-6)
- `batch_mode`: Enable explicit batch processing (default: False)

### Integration with Governor

The governor (`agent/core/governor.py`) automatically uses the spectral radius estimator during each cycle:

```python
# 2 ─── Spectral-radius guard (xˣ-17)
x0 = torch.randn(4, requires_grad=True)  # Random input point
rho = _SPECTRAL_MODEL.estimate_spectral_radius(x0, n_iter=10)

if rho >= MAX_SPECTRAL_RADIUS:  # 0.9 threshold
    logger.error("Spectral radius breach - rollback triggered")
    return False  # run_one_cycle() now exits early, causing automatic rollback
```

### Technical Details

#### Convergence Tolerance Algorithm
Power iteration stops when |ρₖ - ρₖ₋₁| < ε (epsilon), enabling early termination when convergence is achieved. The default tolerance is 1e-6, with a hard upper bound of n_iter iterations (default: 6 for model methods, 5 for standalone functions).

```python
# Early-stop check
if iteration and abs(current_rho - prev_rho) < tolerance:
    break
```

#### Batch Processing
Batch mode processes samples individually in O(batch × n_iter) Jacobian-vector calls. This is not a vectorized JVP implementation - that would be a future performance upgrade.

```python
# Batch wrapper
if x.dim() > 1 or batch_mode:
    return torch.tensor([_estimate_single(x_i) for x_i in x]).mean().item()
```

#### Device-Aware Random Generation
Generator seeding uses `torch.randint(..., device=x.device)` to ensure CUDA streams stay deterministic across devices.

```python
g = torch.Generator(device=x.device)
g.manual_seed(torch.randint(0, 2**31-1, (1,), device=x.device).item())
v = torch.randn(input_dim, generator=g, device=x.device, dtype=x.dtype)
```

#### Power Iteration Algorithm

The system uses power iteration to estimate the largest eigenvalue without computing the full Jacobian:

1. Initialize random vector `v`
2. For `n_iter` iterations:
   - Compute `v_new = J @ v` using Jacobian-vector products (JVP)
   - Normalize: `v = v_new / ||v_new||`
   - Check convergence: stop if |ρₖ - ρₖ₋₁| < ε (epsilon)
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
- **Early Stopping**: Reduces computation time by up to 50%

### Testing

Comprehensive tests are available in `tests/test_spectral_estimator.py`:

```bash
# Run spectral radius tests
poetry run pytest tests/test_spectral_estimator.py -v

# Run all spectral-related tests with output logging
poetry run pytest tests/test_spectral_estimator.py tests/test_spectral_guard.py -v | tee junit.xml
```

**Note**: Governor integration tests require Redis. In CI environments without Redis, these tests are skipped behind `pytest.importorskip("redis")`.

Test coverage includes:
- Linear transformations with known spectral radii
- Neural networks with different architectures
- Convergence tolerance and early stopping
- Batch processing (explicit and automatic detection)
- Device awareness (CPU/GPU compatibility)
- Edge cases (zero gradients, non-square Jacobians)
- Reproducibility and convergence verification

### Governance Metrics

This implementation updates the Prometheus metric `raft_spectral_radius` in real-time, enabling Grafana monitoring:

- **Metric Name**: `raft_spectral_radius` (copy-paste ready for Grafana queries)
- **Update Frequency**: Every governor cycle
- **Automatic Rollback**: Triggered when ρ ≥ 0.9
- **Real-time Monitoring**: Live spectral stability tracking

### Known Limits

- **Full Jacobian path is still O(n²)**: We default to JVP power iteration for efficiency
- **Batch average hides per-sample outliers ≥ ρ_max**: The guard still runs per-cycle, not per-batch, ensuring individual sample monitoring
- **Sample-by-sample batch processing**: Current implementation is O(batch × n_iter); vectorized JVP would be a future performance upgrade

### Charter Compliance

This implementation satisfies charter clause x^x-17 by providing:
- Real-time spectral radius monitoring
- Automatic rollback on stability violations
- Configurable thresholds and iteration counts
- Comprehensive logging and metrics

### Stable-model helper

`SimpleNet.create_stable_model(in_dim, out_dim, target_rho=0.8, method='xavier')`
returns a network whose initial spectral radius is _guaranteed_ below
`target_rho`.  It is what the governor loads by default.
