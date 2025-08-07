import hashlib
import json

from agent.core.smt_verifier import verify

CHARTER_HASH = hashlib.sha256(b"dummy").hexdigest()

# Safe SMT formulas (UNSAT - proof succeeds)
SAFE_SMT_SIMPLE = "(assert true)"  # trivially satisfiable but negated in proof context
SAFE_SMT_COMPLEX = """
(declare-fun x () Int)
(declare-fun y () Int)
(assert (> x 10))
(assert (< x 5))
"""  # UNSAT - no x can be both > 10 and < 5

# Unsafe SMT formulas (SAT - proof fails with counterexample)
UNSAFE_SMT_SIMPLE = "(assert false)"  # trivially UNSAT in normal context, but this represents a failed proof
UNSAFE_SMT_WITH_VARS = """
(declare-fun dangerous_call () Bool)
(declare-fun user_input () String)
(assert dangerous_call)
(assert (= user_input "malicious"))
"""  # SAT - counterexample should show dangerous_call=true, user_input="malicious"

UNSAFE_SMT_COMPLEX = """
(declare-fun exec_detected () Bool)
(declare-fun file_path () String)
(declare-fun line_num () Int)
(assert exec_detected)
(assert (= file_path "/dangerous/script.py"))
(assert (> line_num 0))
"""  # SAT - should provide counterexample with multiple variables


def test_safe_smt_simple_passes_quickly():
    """Test that safe SMT yields True quickly."""
    result = verify(SAFE_SMT_SIMPLE, CHARTER_HASH)
    assert result is True  # Should return just True for UNSAT (proof succeeds)


def test_safe_smt_complex_passes_and_caches():
    """Test that complex safe SMT yields True and caches properly."""
    # First run - should compute and cache
    result1 = verify(SAFE_SMT_COMPLEX, CHARTER_HASH)
    assert result1 is True
    
    # Second run - should hit cache
    result2 = verify(SAFE_SMT_COMPLEX, CHARTER_HASH)
    assert result2 is True


def test_unsafe_smt_simple_fails_with_counterexample():
    """Test that unsafe SMT yields False and returns counterexample JSON."""
    result = verify(UNSAFE_SMT_SIMPLE, CHARTER_HASH)
    
    # Should return tuple for failed proofs
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    success, counterexample_data = result
    assert success is False
    
    # Validate counterexample structure
    assert isinstance(counterexample_data, dict)
    assert "counterexample" in counterexample_data
    assert "model_summary" in counterexample_data
    assert isinstance(counterexample_data["counterexample"], dict)
    assert isinstance(counterexample_data["model_summary"], str)


def test_unsafe_smt_with_vars_returns_variable_bindings():
    """Test that unsafe SMT with variables returns at least one variable binding."""
    result = verify(UNSAFE_SMT_WITH_VARS, CHARTER_HASH)
    
    assert isinstance(result, tuple)
    success, counterexample_data = result
    assert success is False
    
    # Should have at least one variable binding
    counterexample = counterexample_data["counterexample"]
    assert len(counterexample) >= 1
    
    # Check that we have the expected variables
    var_names = set(counterexample.keys())
    expected_vars = {"dangerous_call", "user_input"}
    assert len(var_names.intersection(expected_vars)) >= 1
    
    # Validate summary is meaningful
    summary = counterexample_data["model_summary"]
    assert "counterexample" in summary.lower()
    assert "variable" in summary.lower()


def test_unsafe_smt_complex_caches_counterexample():
    """Test that complex unsafe SMT caches counterexample properly."""
    # First run - should compute and cache
    result1 = verify(UNSAFE_SMT_COMPLEX, CHARTER_HASH)
    assert isinstance(result1, tuple)
    success1, counterexample1 = result1
    assert success1 is False
    
    # Verify we have multiple variables in counterexample
    assert len(counterexample1["counterexample"]) >= 2
    
    # Second run - should hit cache and return same counterexample
    result2 = verify(UNSAFE_SMT_COMPLEX, CHARTER_HASH)
    assert isinstance(result2, tuple)
    success2, counterexample2 = result2
    assert success2 is False
    
    # Cached counterexample should match original
    assert counterexample1["counterexample"] == counterexample2["counterexample"]
    assert counterexample1["model_summary"] == counterexample2["model_summary"]


def test_malformed_smt_raises_runtime_error():
    """Test that malformed SMT raises RuntimeError with descriptive message."""
    malformed_smt = "(assert (this is not valid SMT syntax"
    
    try:
        verify(malformed_smt, CHARTER_HASH)
        assert False, "Expected RuntimeError for malformed SMT"
    except RuntimeError as e:
        assert "SMT parse error" in str(e)


def test_different_charter_hashes_cache_separately():
    """Test that different charter hashes create separate cache entries."""
    charter_hash_1 = hashlib.sha256(b"charter1").hexdigest()
    charter_hash_2 = hashlib.sha256(b"charter2").hexdigest()
    
    # Same SMT, different charter hashes should be computed separately
    result1 = verify(UNSAFE_SMT_WITH_VARS, charter_hash_1)
    result2 = verify(UNSAFE_SMT_WITH_VARS, charter_hash_2)
    
    # Both should fail but be computed independently
    assert isinstance(result1, tuple)
    assert isinstance(result2, tuple)
    assert result1[0] is False
    assert result2[0] is False


def test_proof_gate_integration():
    """Integration test simulating real proof gate usage."""
    # Simulate a safe diff that passes proof gate
    safe_diff_smt = """
    (declare-fun has_forbidden_call () Bool)
    (declare-fun signature_preserved () Bool)
    (assert (not has_forbidden_call))
    (assert signature_preserved)
    (assert (not (and (not has_forbidden_call) signature_preserved)))
    """  # This should be UNSAT (proof succeeds)
    
    result = verify(safe_diff_smt, CHARTER_HASH)
    assert result is True  # Safe diff passes
    
    # Simulate an unsafe diff that fails proof gate
    unsafe_diff_smt = """
    (declare-fun has_forbidden_call () Bool)
    (declare-fun call_type () String)
    (declare-fun file_location () String)
    (assert has_forbidden_call)
    (assert (= call_type "subprocess.call"))
    (assert (= file_location "agent/core/governor.py"))
    """  # This should be SAT (proof fails with counterexample)
    
    result = verify(unsafe_diff_smt, CHARTER_HASH)
    assert isinstance(result, tuple)
    success, counterexample_data = result
    assert success is False
    
    # Should provide meaningful counterexample for debugging
    counterexample = counterexample_data["counterexample"]
    assert "has_forbidden_call" in counterexample
    assert "call_type" in counterexample
    assert "file_location" in counterexample
