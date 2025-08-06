import hashlib
import json

from agent.core.smt_verifier import verify, verify_bool

CHARTER_HASH = hashlib.sha256(b"dummy").hexdigest()

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


def test_good_diff_passes_and_caches():
    """Test that safe SMT yields True quickly and caches result."""
    result = verify(GOOD_DIFF, CHARTER_HASH)
    assert result["result"] is True  # first run (Z3)
    assert result["counterexample"] is None
    
    # Test cache hit
    cached_result = verify(GOOD_DIFF, CHARTER_HASH)
    assert cached_result["result"] is True  # cache hit
    assert cached_result["counterexample"] is None


def test_bad_diff_fails_and_caches():
    """Test that unsafe SMT yields False and caches result."""
    result = verify(BAD_DIFF, CHARTER_HASH)
    assert result["result"] is False  # first run
    assert isinstance(result["counterexample"], dict)
    assert result["counterexample"]["reason"] == "formula_unsatisfiable"
    
    # Test cache hit  
    cached_result = verify(BAD_DIFF, CHARTER_HASH)
    assert cached_result["result"] is False  # cache hit
    assert isinstance(cached_result["counterexample"], dict)


def test_satisfiable_formula_with_variables_returns_model():
    """Test that satisfiable SMT with variables returns model assignments."""
    result = verify(SAFE_SMT_WITH_VARS, CHARTER_HASH + "_vars")
    
    # This formula is satisfiable, so proof passes
    assert result["result"] is True
    assert isinstance(result["counterexample"], dict)
    assert len(result["counterexample"]) >= 1  # At least one variable binding
    
    # Verify that counterexample contains expected variables
    assignments = result["counterexample"]
    variable_names = list(assignments.keys())
    assert any("x" in str(name) for name in variable_names)
    assert any("y" in str(name) for name in variable_names)


def test_complex_satisfiable_formula():
    """Test satisfiable formula with different types of variables."""
    result = verify(COMPLEX_SAT_FORMULA, CHARTER_HASH + "_complex")
    
    assert result["result"] is True
    assert isinstance(result["counterexample"], dict)
    assert len(result["counterexample"]) >= 1
    
    # Check that we have assignments for both variables
    assignments = result["counterexample"]
    variable_names = list(assignments.keys())
    assert any("a" in str(name) for name in variable_names)
    assert any("b" in str(name) for name in variable_names)


def test_backward_compatibility_bool_interface():
    """Test that verify_bool provides backward compatibility."""
    # Test safe case
    assert verify_bool(GOOD_DIFF, CHARTER_HASH + "_compat_good") is True
    
    # Test unsafe case  
    assert verify_bool(BAD_DIFF, CHARTER_HASH + "_compat_bad") is False


def test_malformed_smt_handling():
    """Test handling of malformed SMT-LIB2 input."""
    malformed_smt = "(assert (this is not valid smt"
    
    try:
        result = verify(malformed_smt, CHARTER_HASH + "_malformed")
        # Should not reach here due to exception
        assert False, "Expected RuntimeError for malformed SMT"
    except RuntimeError as e:
        assert "SMT parse error" in str(e)


def test_counterexample_caching():
    """Test that counterexamples are properly cached and retrieved."""
    # First call - should compute and cache
    result1 = verify(BAD_DIFF, CHARTER_HASH + "_cache_test")
    assert result1["result"] is False
    assert isinstance(result1["counterexample"], dict)
    
    # Second call - should retrieve from cache
    result2 = verify(BAD_DIFF, CHARTER_HASH + "_cache_test")
    assert result2["result"] is False
    assert isinstance(result2["counterexample"], dict)
    
    # Counterexamples should be consistent
    assert result1["counterexample"] == result2["counterexample"]


def test_model_assignment_caching():
    """Test that model assignments are properly cached and retrieved."""
    # First call - should compute and cache
    result1 = verify(SAFE_SMT_WITH_VARS, CHARTER_HASH + "_model_cache_test")
    assert result1["result"] is True
    assert isinstance(result1["counterexample"], dict)
    assert len(result1["counterexample"]) >= 1
    
    # Second call - should retrieve from cache
    result2 = verify(SAFE_SMT_WITH_VARS, CHARTER_HASH + "_model_cache_test")
    assert result2["result"] is True
    assert isinstance(result2["counterexample"], dict)
    
    # Model assignments should be consistent
    assert result1["counterexample"] == result2["counterexample"]


def test_counterexample_format_validation():
    """Test that counterexample has proper JSON-serializable format."""
    result = verify(BAD_DIFF, CHARTER_HASH + "_format_test")
    
    # Should be JSON serializable
    json_str = json.dumps(result["counterexample"])
    parsed_back = json.loads(json_str)
    
    assert isinstance(parsed_back, dict)


def test_unsatisfiable_formula_with_explicit_contradiction():
    """Test a formula that is explicitly unsatisfiable due to contradictory constraints."""
    # This formula should be UNSAT (contradictory constraints)
    unsat_formula = """
    (declare-const x Int)
    (assert (> x 10))
    (assert (< x 5))
    """
    
    result = verify(unsat_formula, CHARTER_HASH + "_unsat_test")
    assert result["result"] is False  # UNSAT means proof fails
    assert isinstance(result["counterexample"], dict)
    assert result["counterexample"]["reason"] == "formula_unsatisfiable"
