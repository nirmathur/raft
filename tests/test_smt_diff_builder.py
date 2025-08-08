import pytest

from agent.core.diff_builder import (DiffAST, DiffLine, FunctionSignature,
                                     GitDiffParser, SMTDiffBuilder,
                                     analyze_diff_context, build_advanced_smt,
                                     build_smt_diff, build_smt_with_charter,
                                     calculate_risk_score,
                                     extract_forbidden_from_charter,
                                     parse_diff_to_ast)


class TestGitDiffParser:
    """Test the Git diff parsing functionality."""

    def test_parse_empty_diff(self):
        """Test parsing empty diff returns empty AST."""
        parser = GitDiffParser()
        result = parser.parse_unified_diff("")

        assert isinstance(result, DiffAST)
        assert len(result.added_lines) == 0
        assert len(result.removed_lines) == 0
        assert len(result.modified_files) == 0
        assert len(result.function_renames) == 0

    def test_parse_simple_addition(self):
        """Test parsing simple line addition."""
        diff_text = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
     pass
+    print("Hello world")
"""
        parser = GitDiffParser()
        result = parser.parse_unified_diff(diff_text)

        assert len(result.added_lines) == 1
        assert result.added_lines[0].content == '    print("Hello world")'
        assert result.added_lines[0].line_type == "+"
        assert "test.py" in result.modified_files

    def test_parse_function_definition(self):
        """Test parsing function definitions from diff."""
        diff_text = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def old_function(x, y):
+def new_function(x, y):
     return x + y
"""
        parser = GitDiffParser()
        result = parser.parse_unified_diff(diff_text)

        assert len(result.added_lines) == 1
        assert len(result.removed_lines) == 1
        assert "+new_function" in result.function_signatures
        assert "-old_function" in result.function_signatures
        assert result.function_signatures["+new_function"].name == "new_function"
        assert result.function_signatures["-old_function"].name == "old_function"

    def test_detect_function_rename(self):
        """Test detection of function renames with same signature."""
        diff_text = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def calculate_sum(a, b):
+def compute_sum(a, b):
     return a + b
"""
        parser = GitDiffParser()
        result = parser.parse_unified_diff(diff_text)

        assert "calculate_sum" in result.function_renames
        assert result.function_renames["calculate_sum"] == "compute_sum"


class TestSMTDiffBuilder:
    """Test the SMT-LIB2 formula building functionality."""

    def test_safe_diff_returns_assert_true(self):
        """Test that safe diff returns (assert true)."""
        safe_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def hello():
     pass
+    print("Hello world")
"""
        result = build_smt_diff(safe_diff)
        assert result == "(assert false)"

    def test_unsafe_diff_with_exec_returns_assert_false(self):
        """Test that diff with exec() returns (assert false)."""
        unsafe_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def hello():
     pass
+    exec('malicious_code')
"""
        result = build_smt_diff(unsafe_diff)
        assert result == "(assert true)"

    def test_unsafe_diff_with_subprocess_returns_assert_false(self):
        """Test that diff with subprocess returns (assert false)."""
        unsafe_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 import os
+import subprocess
 def hello():
"""
        result = build_smt_diff(unsafe_diff)
        assert result == "(assert true)"

    def test_unsafe_diff_with_eval_returns_assert_false(self):
        """Test that diff with eval() returns (assert false)."""
        unsafe_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def hello():
+    result = eval(user_input)
     pass
"""
        result = build_smt_diff(unsafe_diff)
        assert result == "(assert true)"

    def test_function_rename_with_same_signature_is_safe(self):
        """Test that function rename with same signature is considered safe."""
        rename_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def old_name(x, y):
+def new_name(x, y):
     return x + y
"""
        result = build_smt_diff(rename_diff)
        assert result == "(assert false)"

    def test_function_rename_with_different_signature_is_unsafe(self):
        """Test that function rename with different signature is considered unsafe."""
        rename_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def old_name(x):
+def new_name(x, y):
     return x
"""
        result = build_smt_diff(rename_diff)
        # Now properly detects signature mismatches
        assert result == "(assert true)"

    def test_empty_diff_returns_assert_true(self):
        """Test that empty diff returns (assert false) - safe."""
        result = build_smt_diff("")
        assert result == "(assert false)"

    def test_diff_with_multiple_forbidden_patterns(self):
        """Test diff with multiple forbidden patterns."""
        unsafe_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,4 @@
 def hello():
+    exec('code')
+    subprocess.call(['ls'])
     pass
"""
        result = build_smt_diff(unsafe_diff)
        assert result == "(assert true)"


class TestDiffAnalysis:
    """Test the enhanced diff analysis functions."""

    def test_analyze_diff_context_safe_diff(self):
        """Test context analysis for safe diff."""
        safe_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def hello():
     pass
+    print("Hello")
"""
        context = analyze_diff_context(safe_diff)

        assert context["file_count"] == 1
        assert context["has_deletions"] is False
        assert context["added_lines"] == 1
        assert context["smt_result"] == "(assert false)"
        assert len(context["forbidden_violations"]) == 0
        assert context["risk_score"] <= 0.2  # Should be low risk

    def test_analyze_diff_context_unsafe_diff(self):
        """Test context analysis for unsafe diff."""
        unsafe_diff = """diff --git a/dangerous.py b/dangerous.py
@@ -1,2 +1,3 @@
 def hack():
+    exec('rm -rf /')
     pass
"""
        context = analyze_diff_context(unsafe_diff)

        assert context["file_count"] == 1
        assert context["smt_result"] == "(assert true)"
        assert len(context["forbidden_violations"]) > 0
        assert context["forbidden_violations"][0]["pattern"] == r"\bexec\b"
        assert context["risk_score"] > 0.8  # Should be high risk

    def test_analyze_diff_context_function_rename(self):
        """Test context analysis for function rename."""
        rename_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def old_function(x, y):
+def new_function(x, y):
     return x + y
"""
        context = analyze_diff_context(rename_diff)

        assert len(context["function_renames"]) == 1
        assert "old_function" in context["function_renames"]
        assert context["function_renames"]["old_function"] == "new_function"

    def test_calculate_risk_score_progression(self):
        """Test that risk score increases with danger level."""
        safe_diff = "+ print('hello')"
        medium_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,4 @@
 def test():
+    import os
     pass
"""
        dangerous_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def test():
+    exec('dangerous')
     pass
"""

        safe_score = calculate_risk_score(safe_diff)
        medium_score = calculate_risk_score(medium_diff)
        dangerous_score = calculate_risk_score(dangerous_diff)

        assert safe_score < medium_score < dangerous_score
        assert (
            dangerous_score > 0.9
        )  # When forbidden patterns exist, risk should be ≥ 0.9

    def test_parse_diff_to_ast_external_api(self):
        """Test the external parse_diff_to_ast API function."""
        diff_text = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def hello():
     pass
+    print("world")
"""
        ast = parse_diff_to_ast(diff_text)

        assert isinstance(ast, DiffAST)
        assert len(ast.added_lines) == 1
        assert ast.added_lines[0].content == '    print("world")'


class TestAdvancedSMTFeatures:
    """Test advanced SMT formula building features."""

    def test_build_advanced_smt_custom_patterns(self):
        """Test building SMT with custom forbidden patterns."""
        diff_text = "+ custom_dangerous_function()"
        custom_patterns = [r"\bcustom_dangerous_function\b"]

        result = build_advanced_smt(diff_text, custom_patterns)
        assert result == "(assert true)"

    def test_build_advanced_smt_safe_with_custom_patterns(self):
        """Test safe diff with custom patterns."""
        diff_text = "+ safe_function()"
        custom_patterns = [r"\bdangerous_function\b"]

        result = build_advanced_smt(diff_text, custom_patterns)
        assert result == "(assert false)"

    def test_extract_forbidden_from_charter(self):
        """Test extracting forbidden patterns from charter."""
        charter_clauses = {"x^x-22": "No dangerous imports"}
        forbidden = extract_forbidden_from_charter(charter_clauses)

        assert isinstance(forbidden, list)
        assert len(forbidden) > 0
        assert r"\bexec\b" in forbidden  # Should include default patterns


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_malformed_diff_handling(self):
        """Test handling of malformed diff text."""
        malformed_diff = "This is not a valid diff format"

        # Should not crash and should default to safe
        result = build_smt_diff(malformed_diff)
        assert result == "(assert false)"

    def test_very_large_diff(self):
        """Test handling of large diffs."""
        # Create a diff with many lines
        large_diff = "diff --git a/large.py b/large.py\n@@ -1,2 +1,102 @@\n"
        for i in range(100):
            large_diff += f"+ line_{i} = {i}\n"

        result = build_smt_diff(large_diff)
        assert result == "(assert false)"  # Should handle large diffs

    def test_binary_file_diff(self):
        """Test handling of binary file diffs."""
        binary_diff = """diff --git a/image.png b/image.png
index 1234567..abcdefg 100644
Binary files a/image.png and b/image.png differ
"""
        context = analyze_diff_context(binary_diff)
        assert context["has_binary"] is True

    def test_unicode_content_handling(self):
        """Test handling of unicode content in diffs."""
        unicode_diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def hello():
     pass
+    print("🚀 Unicode test")
"""
        result = build_smt_diff(unicode_diff)
        assert result == "(assert false)"


# Legacy test compatibility
def test_build_smt_diff_safe():
    """Legacy test: safe diff returns (assert false)."""
    safe_diff = "+ def hello(): pass"
    result = build_smt_diff(safe_diff)
    assert result == "(assert false)"


def test_build_smt_diff_unsafe():
    """Legacy test: unsafe diff returns (assert true)."""
    unsafe_diff = "+ eval('x')"
    result = build_smt_diff(unsafe_diff)
    assert result == "(assert true)"


def test_risk_score_bounds():
    """Legacy test: risk score is between 0 and 1."""
    assert 0 <= calculate_risk_score("+ eval('x')") <= 1.0
    assert 0 <= calculate_risk_score("") <= 1.0


def test_risk_score_calculation():
    """Legacy test: risk score calculation logic."""
    # Empty diff should have low risk
    assert calculate_risk_score("") == 0.0

    # Diff with dangerous patterns should have higher risk
    dangerous_diff = "diff --git a/file.py b/file.py\n+ exec('code')"
    score = calculate_risk_score(dangerous_diff)
    assert score > 0.9  # Should be high risk due to exec


def test_analyze_diff_context():
    """Legacy test: diff context analysis."""
    context = analyze_diff_context("diff --git a/file.py b/file.py")
    assert "file_count" in context
    assert "has_binary" in context
    assert "has_deletions" in context
    assert "risk_score" in context
    assert context["file_count"] == 1


def test_forbidden_charter_injection():
    """Test that charter clause adds pattern and diff becomes UNSAFE."""
    charter_clauses = {"x^x-99": "forbidden `pickle` - No pickle imports allowed"}
    diff_text = """diff --git a/test.py b/test.py
@@ -1,2 +1,3 @@
 def test():
+    import pickle
     pass
"""
    result = build_smt_with_charter(diff_text, charter_clauses)
    assert result == "(assert true)"


def test_function_rename_signature_mismatch():
    """Test that function signature mismatch results in SMT false."""
    diff_text = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def calculate_sum(a, b):
+def calculate_sum(a):
     return a
"""
    result = build_smt_diff(diff_text)
    # Should detect signature mismatch and return true (unsafe)
    assert result == "(assert true)"


def test_location_metadata_preserved():
    """Test that added lines keep correct new_lineno."""
    diff_text = """diff --git a/test.py b/test.py
@@ -5,4 +5,5 @@
 def existing():
     pass
+    print("new line")
     return True
"""
    ast = parse_diff_to_ast(diff_text)

    assert len(ast.added_lines) == 1
    added_line = ast.added_lines[0]
    assert added_line.new_line_number == 7  # Line 5 + 2 lines down
    assert added_line.old_line_number is None  # Added line has no old line number
    assert 'print("new line")' in added_line.content


def test_charter_pattern_merging():
    """Test that charter patterns are properly merged with defaults."""
    from agent.core.diff_builder import (DEFAULT_FORBIDDEN_PATTERNS,
                                         get_forbidden_patterns)

    charter_clauses = {
        "x^x-98": "forbidden `custom_dangerous` - Custom dangerous pattern",
        "x^x-99": "No pickle allowed",  # Should add pickle pattern
    }

    compiled_patterns = get_forbidden_patterns(charter_clauses)
    patterns = [p.pattern for p in compiled_patterns]

    # Should include all default patterns
    for default_pattern in DEFAULT_FORBIDDEN_PATTERNS:
        assert default_pattern in patterns

    # Should include charter-derived patterns
    assert r"\bcustom_dangerous\b" in patterns
    assert r"\bpickle\b" in patterns

    # Should be more than just defaults
    assert len(patterns) > len(DEFAULT_FORBIDDEN_PATTERNS)


def test_overlapping_regex_deduplication():
    """Test that overlapping regex patterns are properly deduplicated."""
    from agent.core.diff_builder import get_forbidden_patterns

    charter_clauses = {
        "x^x-98": "forbidden `exec` - Execution forbidden",  # Should not duplicate existing exec pattern
        "x^x-99": "forbidden `subprocess` - Also forbidden",  # Should not duplicate existing subprocess
        "x^x-100": "forbidden `new_pattern` - New pattern",  # Should add new pattern
    }

    compiled_patterns = get_forbidden_patterns(charter_clauses)
    patterns = [p.pattern for p in compiled_patterns]

    # Check that exec pattern appears only once
    exec_count = sum(1 for p in patterns if "exec" in p)
    assert exec_count == 1  # Should only have the original \bexec\b pattern

    # Check that subprocess pattern appears only once
    subprocess_count = sum(1 for p in patterns if "subprocess" in p)
    assert subprocess_count == 1  # Should only have the original \bsubprocess\b pattern

    # Check that new pattern was added
    assert r"\bnew_pattern\b" in patterns


def test_enhanced_function_rename_detection():
    """Test enhanced function rename detection with return types."""
    diff_text = """diff --git a/test.py b/test.py
@@ -1,4 +1,4 @@
-def calculate_sum(a: int, b: int) -> int:
+def compute_sum(a: int, b: int) -> int:
     return a + b
"""

    ast = parse_diff_to_ast(diff_text)

    # Should detect rename with matching full signatures
    assert "calculate_sum" in ast.function_renames
    assert ast.function_renames["calculate_sum"] == "compute_sum"


def test_line_number_tracking():
    """Test that old and new line numbers are correctly tracked."""
    diff_text = """diff --git a/test.py b/test.py
@@ -10,6 +10,7 @@
 def func():
     x = 1
-    y = 2
+    y = 3
+    z = 4
     return x + y
"""

    ast = parse_diff_to_ast(diff_text)

    # Check removed line
    assert len(ast.removed_lines) == 1
    removed_line = ast.removed_lines[0]
    assert removed_line.old_line_number == 12  # Line 10 + 2 down
    assert removed_line.new_line_number is None
    assert "y = 2" in removed_line.content

    # Check added lines
    assert len(ast.added_lines) == 2

    # First added line (y = 3)
    added_line1 = ast.added_lines[0]
    assert added_line1.new_line_number == 12
    assert added_line1.old_line_number is None
    assert "y = 3" in added_line1.content

    # Second added line (z = 4)
    added_line2 = ast.added_lines[1]
    assert added_line2.new_line_number == 13
    assert added_line2.old_line_number is None
    assert "z = 4" in added_line2.content


def test_multi_hunk_line_number_tracking():
    """Test that line numbers reset correctly across multiple hunks."""
    diff_text = """diff --git a/test.py b/test.py
@@ -10,3 +10,4 @@
 def first_func():
     x = 1
+    # First hunk addition
     return x
@@ -20,3 +21,4 @@
 def second_func():
     y = 2
+    # Second hunk addition
     return y
"""

    ast = parse_diff_to_ast(diff_text)

    # Check added lines from both hunks
    assert len(ast.added_lines) == 2

    # First hunk addition
    first_addition = ast.added_lines[0]
    assert first_addition.new_line_number == 12  # Line 10 + 2 down
    assert "First hunk addition" in first_addition.content

    # Second hunk addition (line numbers should reset)
    second_addition = ast.added_lines[1]
    assert second_addition.new_line_number == 23  # Line 21 + 2 down
    assert "Second hunk addition" in second_addition.content


def test_signature_mismatch_returns_false():
    """Test that signature mismatch results in SMT false."""
    diff = """diff --git a/test.py b/test.py
@@ -1,2 +1,2 @@
-def calculate_sum(a):
+def calculate_sum(a, b):
     pass
"""
    assert build_smt_diff(diff) == "(assert true)"


def test_line_number_metadata():
    """Test that line number metadata is preserved correctly."""
    diff = """diff --git a/x.py b/x.py
@@ -10,1 +10,1 @@
+danger = 1
"""
    ast = parse_diff_to_ast(diff)
    assert len(ast.added_lines) == 1
    assert ast.added_lines[0].line_number == 10
    assert ast.added_lines[0].new_line_number == 10


@pytest.mark.parametrize("pattern", [r"\bexec\b", r"\bsubprocess\b"])
def test_forbidden_patterns(pattern):
    """Test parametrized forbidden patterns detection."""
    # Extract the pattern name for generating test code
    pattern_name = pattern.replace(r"\b", "").replace("\\", "")
    if pattern_name == "exec":
        diff = f"+ exec('dangerous code')"
    elif pattern_name == "subprocess":
        diff = f"+ import subprocess\n+ subprocess.call(['ls'])"
    else:
        diff = f"+ {pattern_name}('test')"

    result = build_smt_diff(diff)
    assert result == "(assert true)"
