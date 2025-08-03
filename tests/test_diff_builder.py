import pytest

from agent.core.diff_builder import (analyze_diff_context, build_advanced_smt,
                                     build_smt_diff, calculate_risk_score,
                                     extract_forbidden_from_charter)


def test_build_smt_diff_safe():
    """Test that safe diff returns (assert true)."""
    safe_diff = "+ def hello(): pass"
    result = build_smt_diff(safe_diff)
    assert result == "(assert true)"


def test_build_smt_diff_unsafe():
    """Test that unsafe diff returns (assert false)."""
    unsafe_diff = "+ eval('x')"
    result = build_smt_diff(unsafe_diff)
    assert result == "(assert false)"


def test_risk_score_bounds():
    """Test that risk score is between 0 and 1."""
    assert 0 <= calculate_risk_score("+ eval('x')") <= 1.0
    assert 0 <= calculate_risk_score("") <= 1.0


def test_risk_score_calculation():
    """Test risk score calculation logic."""
    # Empty diff should have low risk
    assert calculate_risk_score("") == 0.0

    # Diff with deletions should have higher risk
    diff_with_deletions = "diff --git a/file.py b/file.py\n- old_line"
    score = calculate_risk_score(diff_with_deletions)
    assert score > 0.0


def test_analyze_diff_context():
    """Test diff context analysis."""
    context = analyze_diff_context("diff --git a/file.py b/file.py")
    assert "file_count" in context
    assert "has_binary" in context
    assert "has_deletions" in context
    assert "risk_score" in context
    assert context["file_count"] == 1


def test_extract_forbidden_from_charter():
    """Test charter forbidden pattern extraction."""
    charter_clauses = {"x^x-22": "No dangerous imports"}
    forbidden = extract_forbidden_from_charter(charter_clauses)
    assert isinstance(forbidden, list)
    assert len(forbidden) > 0


def test_build_advanced_smt():
    """Test advanced SMT formula building."""
    # Safe diff
    safe_result = build_advanced_smt("safe code", ["dangerous"])
    assert safe_result == "(assert true)"

    # Unsafe diff
    unsafe_result = build_advanced_smt("eval('x')", ["eval"])
    assert unsafe_result == "(assert false)"
