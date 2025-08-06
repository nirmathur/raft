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

## SMT-LIB2 Diff Analysis

RAFT includes a sophisticated SMT-LIB2 based Git diff analyzer that uses Z3py to verify the safety of code changes. The system implements two key invariants:

1. **No forbidden API calls** - Detects dangerous operations like `exec()`, `subprocess`, `eval()`, etc.
2. **Goal preservation** - Ensures function renames preserve their signatures

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

Integrate with RAFT's charter system for dynamic pattern configuration:

```python
from agent.core.diff_builder import build_smt_with_charter

charter_clauses = {
    "x^x-22": "No dangerous imports",
    "x^x-23": "Preserve function signatures"
}

result = build_smt_with_charter(diff_text, charter_clauses)
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
- `modified_files`: Set of modified file paths
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
