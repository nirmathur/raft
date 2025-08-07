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