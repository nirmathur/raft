import hashlib
import json
import time

import pytest

from agent.core.smt_verifier import verify, verify_bool

BASE = hashlib.sha256(b"dummy").hexdigest()

def h(tag: str = "") -> str:
    """Generate proper hash for test keys to avoid long cache keys."""
    return hashlib.sha256(f"{BASE}:{tag}".encode()).hexdigest()

GOOD_DIFF = "(assert true)"  # SAT → proof passes
BAD_DIFF = "(assert false)"  # UNSAT → proof fails

# For testing model extraction from satisfiable formulas
SAFE_SMT_WITH_VARS = """
(declare-const x Int)
(declare-const y Int)
(assert (and (> x 10) (< y 5) (= (+ x y) 20)))
"""

# This formula is satisfiable and should return variable assignments
COMPLEX_SAT_FORMULA = """
(declare-const a Int)
(declare-const b Bool)
(assert (and (> a 0) b))
"""


@pytest.mark.timeout(2)
def test_good_diff_passes_and_caches():
    """Test that safe SMT yields True quickly and caches result."""
    result = verify(GOOD_DIFF, h())
    assert result["result"] is True  # first run (Z3)
    assert result["counterexample"] is None
    
    # Test cache hit
    cached_result = verify(GOOD_DIFF, h())
    assert cached_result["result"] is True  # cache hit
    assert cached_result["counterexample"] is None


@pytest.mark.timeout(2)
def test_bad_diff_fails_and_caches():
    """Test that unsafe SMT yields False and caches result."""
    result = verify(BAD_DIFF, h("bad"))
    assert result["result"] is False  # first run
    assert isinstance(result["counterexample"], dict)
    assert result["counterexample"]["reason"] == "formula_unsatisfiable"
    
    # Test cache hit  
    cached_result = verify(BAD_DIFF, h("bad"))
    assert cached_result["result"] is False  # cache hit
    assert isinstance(cached_result["counterexample"], dict)
    assert cached_result["counterexample"]["reason"] == "formula_unsatisfiable"


@pytest.mark.timeout(2)
def test_satisfiable_formula_with_variables_returns_model():
    """Test that satisfiable SMT with variables returns model assignments."""
    result = verify(SAFE_SMT_WITH_VARS, h("vars"))
    
    # This formula is satisfiable, so proof passes
    assert result["result"] is True
    assert isinstance(result["counterexample"], dict)
    assert len(result["counterexample"]) >= 1  # At least one variable binding
    
    # Verify that counterexample contains expected variables
    assignments = result["counterexample"]
    variable_names = list(assignments.keys())
    assert any("x" in str(name) for name in variable_names)
    assert any("y" in str(name) for name in variable_names)


@pytest.mark.timeout(2)
def test_complex_satisfiable_formula():
    """Test satisfiable formula with different types of variables."""
    result = verify(COMPLEX_SAT_FORMULA, h("complex"))
    
    assert result["result"] is True
    assert isinstance(result["counterexample"], dict)
    assert len(result["counterexample"]) >= 1
    
    # Check that we have assignments for both variables
    assignments = result["counterexample"]
    variable_names = list(assignments.keys())
    assert any("a" in str(name) for name in variable_names)
    assert any("b" in str(name) for name in variable_names)


@pytest.mark.timeout(2)
def test_safe_formula_fast():
    """Test that simple safe formulas are processed quickly."""
    assert verify_bool("(assert true)", h("fast"))


@pytest.mark.timeout(2)
def test_backward_compatibility_bool_interface():
    """Test that verify_bool provides backward compatibility."""
    # Test safe case
    assert verify_bool(GOOD_DIFF, h("compat_good")) is True
    
    # Test unsafe case  
    assert verify_bool(BAD_DIFF, h("compat_bad")) is False


def test_malformed_smt_handling():
    """Test handling of malformed SMT-LIB2 input."""
    malformed_smt = "(assert (this is not valid smt"
    
    try:
        result = verify(malformed_smt, h("malformed"))
        # Should not reach here due to exception
        assert False, "Expected RuntimeError for malformed SMT"
    except RuntimeError as e:
        assert "SMT parse error" in str(e)


def test_counterexample_caching():
    """Test that counterexamples are properly cached and retrieved."""
    # First call - should compute and cache
    result1 = verify(BAD_DIFF, h("cache_test"))
    assert result1["result"] is False
    assert isinstance(result1["counterexample"], dict)
    assert result1["counterexample"]["reason"] == "formula_unsatisfiable"
    
    # Second call - should retrieve from cache
    result2 = verify(BAD_DIFF, h("cache_test"))
    assert result2["result"] is False
    assert isinstance(result2["counterexample"], dict)
    
    # Counterexamples should be consistent
    assert result1["counterexample"] == result2["counterexample"]


def test_model_assignment_caching():
    """Test that model assignments are properly cached and retrieved."""
    # First call - should compute and cache
    result1 = verify(SAFE_SMT_WITH_VARS, h("model_cache_test"))
    assert result1["result"] is True
    assert isinstance(result1["counterexample"], dict)
    assert len(result1["counterexample"]) >= 1
    
    # Second call - should retrieve from cache
    result2 = verify(SAFE_SMT_WITH_VARS, h("model_cache_test"))
    assert result2["result"] is True
    assert isinstance(result2["counterexample"], dict)
    
    # Model assignments should be consistent
    assert result1["counterexample"] == result2["counterexample"]


def test_cache_hit_performance():
    """Test that cache hits are significantly faster than first computation."""
    test_key = h("perf_test")
    
    # First call - compute and cache
    start_time = time.perf_counter()
    result1 = verify(SAFE_SMT_WITH_VARS, test_key)
    first_duration = time.perf_counter() - start_time
    
    # Second call - should be cache hit
    start_time = time.perf_counter()
    result2 = verify(SAFE_SMT_WITH_VARS, test_key)
    cache_duration = time.perf_counter() - start_time
    
    # Results should be identical
    assert result1 == result2
    
    # Cache hit should be much faster (skip if Redis not available)
    try:
        from agent.core.smt_verifier import REDIS
        if REDIS is not None:
            assert cache_duration < 0.01, f"Cache hit too slow: {cache_duration:.4f}s"
            assert cache_duration < first_duration / 2, "Cache hit should be much faster"
    except ImportError:
        pass  # Skip timing test if Redis unavailable


def test_counterexample_format_validation():
    """Test that counterexample has proper JSON-serializable format."""
    result = verify(BAD_DIFF, h("format_test"))
    
    # Should be JSON serializable
    json_str = json.dumps(result["counterexample"])
    parsed_back = json.loads(json_str)
    
    assert isinstance(parsed_back, dict)
    assert "reason" in parsed_back
    assert parsed_back["reason"] == "formula_unsatisfiable"


def test_unsatisfiable_formula_with_explicit_contradiction():
    """Test a formula that is explicitly unsatisfiable due to contradictory constraints."""
    # This formula should be UNSAT (contradictory constraints)
    unsat_formula = """
    (declare-const x Int)
    (assert (> x 10))
    (assert (< x 5))
    """
    
    result = verify(unsat_formula, h("unsat_test"))
    assert result["result"] is False  # UNSAT means proof fails
    assert isinstance(result["counterexample"], dict)
    assert result["counterexample"]["reason"] == "formula_unsatisfiable"


def test_solver_unknown_handling():
    """Test handling of solver unknown results."""
    # Create a formula that might return unknown (though rare with simple formulas)
    # This is more for code coverage than realistic scenarios
    complex_formula = """
    (declare-const x Real)
    (assert (> (* x x x x) 1000000))
    (assert (< x 10))
    """
    
    result = verify(complex_formula, h("unknown_test"))
    # Should either be SAT (True) or unknown (False with solver_unknown reason)
    assert isinstance(result["result"], bool)
    if not result["result"]:
        assert "reason" in result["counterexample"]
        assert result["counterexample"]["reason"] in ["formula_unsatisfiable", "solver_unknown"]
