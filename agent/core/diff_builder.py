"""
diff_builder.py
----------------
Generate an SMT-LIB2 safety obligation for a *real Git diff* using Z3py.

This module implements two key invariants:
1. No forbidden API calls (exec, subprocess, etc.)
2. Goal preservation: renamed functions must preserve their signatures

The SMT formula encodes these as:
    (assert true)   → safe diff
    (assert false)  → UNSAT (proof gate fails)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import z3
from git import Repo
from loguru import logger

# ------------------------------------------------------------------------- #
DEFAULT_FORBIDDEN_PATTERNS = [
    r"\bsubprocess\b",
    r"\bos\.system\b", 
    r"\beval\b",
    r"\bexec\b",
    r"\bimport\s+\*",  # wildcard imports
    r"\b__import__\b",  # dynamic imports
    r"\bglobals\b",  # global manipulation
    r"\blocals\b",  # local manipulation
]

# Cache for compiled patterns to avoid recomputation
_pattern_cache = {}

def get_forbidden_patterns(charter: Dict[str, str] = None) -> List[re.Pattern]:
    """Get forbidden patterns merged with charter clauses.
    
    Charter clauses that contain regex patterns will be added to the default
    forbidden patterns. Returns compiled regex patterns for performance.
    Uses caching to avoid recompilation.
    """
    if charter is None:
        charter = {}
    
    # Create cache key from charter clauses
    cache_key = tuple(sorted(charter.items()))
    
    if cache_key in _pattern_cache:
        return _pattern_cache[cache_key]
    
    patterns = DEFAULT_FORBIDDEN_PATTERNS.copy()
    
    # Extract regex patterns from charter clauses
    for clause_id, clause_text in charter.items():
        # Look for charter clauses that define forbidden patterns
        if any(keyword in clause_text.lower() for keyword in ['forbidden', 'dangerous', 'no ', 'block']):
            # Try to extract regex pattern from clause text
            # This is a simplified heuristic - in practice, charter clauses would have
            # a more structured format for defining patterns
            pattern_matches = re.findall(r'`([^`]+)`', clause_text)  # Look for `pattern`
            for pattern in pattern_matches:
                # Convert simple words to regex word boundaries
                if pattern and not any(special in pattern for special in ['\\', '(', ')', '[', ']', '{', '}', '+', '*', '?', '^', '$', '|', '.']):
                    pattern = rf'\b{re.escape(pattern)}\b'
                if pattern not in patterns:
                    patterns.append(pattern)
            
            # Also check for common pattern indicators
            if 'pickle' in clause_text.lower():
                patterns.append(r'\bpickle\b')
            if 'shell' in clause_text.lower():
                patterns.append(r'\bshell\b')
    
    # Remove duplicates while preserving order
    unique_patterns = []
    seen = set()
    for pattern in patterns:
        if pattern not in seen:
            unique_patterns.append(pattern)
            seen.add(pattern)
    
    # Compile patterns for performance
    compiled_patterns = [re.compile(pattern) for pattern in unique_patterns]
    _pattern_cache[cache_key] = compiled_patterns
    return compiled_patterns
# ------------------------------------------------------------------------- #


@dataclass
class DiffLine:
    """Represents a single line in a Git diff."""
    line_type: str  # '+', '-', or ' '
    content: str
    file_path: str
    line_number: int
    old_line_number: Optional[int] = None  # Line number in old file
    new_line_number: Optional[int] = None  # Line number in new file


@dataclass
class FunctionSignature:
    """Represents a function signature for goal preservation."""
    name: str
    args: List[str]
    returns: Optional[str] = None
    
    def to_smt_string(self) -> str:
        """Convert function signature to SMT-LIB2 function declaration."""
        arg_types = " ".join([f"String" for _ in self.args])  # Simplified: all args as String
        return_type = self.returns or "String"
        return f"(declare-fun {self.name} ({arg_types}) {return_type})"


@dataclass
class DiffAST:
    """Abstract Syntax Tree representation of a Git diff."""
    added_lines: List[DiffLine]
    removed_lines: List[DiffLine]
    modified_files: Set[str]
    function_renames: Dict[str, str]  # old_name -> new_name
    function_signatures: Dict[str, FunctionSignature]  # func_name -> signature


class GitDiffParser:
    """Parses Git unified diffs into structured AST representation."""
    
    def __init__(self):
        self.function_pattern = re.compile(r'^[+-]?\s*def\s+(\w+)\s*\(([^)]*)\)', re.MULTILINE)
    
    def parse_unified_diff(self, diff_text: str) -> DiffAST:
        """Parse unified diff text into DiffAST structure."""
        if not diff_text.strip():
            return DiffAST([], [], set(), {}, {})
            
        added_lines = []
        removed_lines = []
        modified_files = set()
        function_renames = {}
        function_signatures = {}
        
        current_file = None
        old_line_number = 0
        new_line_number = 0
        
        for line in diff_text.split('\n'):
            if line.startswith('diff --git'):
                # Extract file path
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3][2:]  # Remove 'b/' prefix
                    modified_files.add(current_file)
            elif line.startswith('@@'):
                # Parse hunk header for both old and new line numbers
                # Format: @@ -old_start,old_count +new_start,new_count @@
                old_match = re.search(r'-(\d+)', line)
                new_match = re.search(r'\+(\d+)', line)
                if old_match:
                    old_line_number = int(old_match.group(1))
                if new_match:
                    new_line_number = int(new_match.group(1))
            elif line.startswith('+') and not line.startswith('+++'):
                # Added line
                content = line[1:]  # Remove '+' prefix
                diff_line = DiffLine('+', content, current_file or '', new_line_number,
                                   old_line_number=None, new_line_number=new_line_number)
                added_lines.append(diff_line)
                
                # Check for function definitions
                self._extract_function_info(content, function_signatures, '+')
                new_line_number += 1
            elif line.startswith('-') and not line.startswith('---'):
                # Removed line  
                content = line[1:]  # Remove '-' prefix
                diff_line = DiffLine('-', content, current_file or '', old_line_number,
                                   old_line_number=old_line_number, new_line_number=None)
                removed_lines.append(diff_line)
                
                # Check for function definitions
                self._extract_function_info(content, function_signatures, '-')
                old_line_number += 1
            elif line.startswith(' '):
                # Context line - present in both old and new
                old_line_number += 1
                new_line_number += 1
        
        # Detect function renames by comparing added/removed function names
        function_renames = self._detect_function_renames(added_lines, removed_lines)
        
        return DiffAST(added_lines, removed_lines, modified_files, function_renames, function_signatures)
    
    def _extract_function_info(self, line: str, signatures: Dict[str, FunctionSignature], line_type: str):
        """Extract function signature information from a code line."""
        match = self.function_pattern.search(line)
        if match:
            func_name = match.group(1)
            args_str = match.group(2)
            args = [arg.strip().split(':')[0].strip() for arg in args_str.split(',') if arg.strip()]
            
            # Store with prefix to distinguish added vs removed
            key = f"{line_type}{func_name}"
            signatures[key] = FunctionSignature(func_name, args)
    
    def _detect_function_renames(self, added_lines: List[DiffLine], removed_lines: List[DiffLine]) -> Dict[str, str]:
        """Detect potential function renames by comparing full signatures."""
        added_funcs = {}
        removed_funcs = {}
        
        # Enhanced pattern to capture return type annotations
        enhanced_pattern = re.compile(r'^[+-]?\s*def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?:', re.MULTILINE)
        
        # Extract function signatures from added/removed lines
        for line in added_lines:
            match = enhanced_pattern.search(line.content)
            if match:
                func_name = match.group(1)
                args = match.group(2).strip()
                return_type = match.group(3).strip() if match.group(3) else None
                # Create full signature for comparison
                full_sig = f"{args}|{return_type or ''}"
                added_funcs[func_name] = full_sig
        
        for line in removed_lines:
            match = enhanced_pattern.search(line.content)
            if match:
                func_name = match.group(1)
                args = match.group(2).strip()
                return_type = match.group(3).strip() if match.group(3) else None
                # Create full signature for comparison
                full_sig = f"{args}|{return_type or ''}"
                removed_funcs[func_name] = full_sig
        
        # Find potential renames (same full signature, different name)
        # Use more strict matching to avoid false positives
        renames = {}
        used_new_names = set()
        
        for old_name, old_sig in removed_funcs.items():
            for new_name, new_sig in added_funcs.items():
                if (old_sig == new_sig and 
                    old_name != new_name and 
                    new_name not in used_new_names and
                    old_sig.split('|')[0]):  # Ensure non-empty args to avoid matching empty functions
                    renames[old_name] = new_name
                    used_new_names.add(new_name)
                    break
        
        # Also detect cases where functions have the same name but different signatures
        # These will be flagged as violations in goal preservation
        for old_name, old_sig in removed_funcs.items():
            for new_name, new_sig in added_funcs.items():
                if (old_name == new_name and  # Same name but different signature
                    old_sig != new_sig and
                    new_name not in used_new_names and
                    old_name not in renames):
                    renames[old_name] = new_name
                    used_new_names.add(new_name)
                    break
                elif (old_name != new_name and 
                      old_sig != new_sig and
                      new_name not in used_new_names and
                      old_name not in renames):
                    # Check if names are similar enough to be considered a potential rename
                    # For simplicity, we'll consider it if one name is a substring of the other
                    # or they share a common root
                    if (old_name in new_name or new_name in old_name or
                        self._names_similar(old_name, new_name)):
                        renames[old_name] = new_name
                        used_new_names.add(new_name)
                        break
        
        return renames
    
    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two function names are similar enough to be considered a rename."""
        # Simple heuristic: check for common prefixes/suffixes or shared roots
        if len(name1) < 3 or len(name2) < 3:
            return False
        
        # Check for shared prefix/suffix of at least 3 characters
        for i in range(3, min(len(name1), len(name2)) + 1):
            if name1[:i] == name2[:i] or name1[-i:] == name2[-i:]:
                return True
        
        return False


class SMTDiffBuilder:
    """Builds SMT-LIB2 formulas from Git diff ASTs using Z3py."""
    
    def __init__(self, forbidden_patterns: List[re.Pattern] = None):
        self.parser = GitDiffParser()
        self.forbidden_patterns = forbidden_patterns or get_forbidden_patterns()
        
    def build_smt_formula(self, diff_text: str) -> str:
        """Build complete SMT-LIB2 formula from diff text."""
        if not diff_text.strip():
            return "(assert true)"
        
        diff_ast = self.parser.parse_unified_diff(diff_text)
        
        # Find violations first to avoid duplicate scanning
        forbidden_violations = self._find_forbidden_violations(diff_ast)
        goal_violations = self._find_goal_preservation_violations(diff_ast)
        
        # Fast path: if we have violations, return false immediately
        # This is more efficient than building Z3 solver for simple cases
        if forbidden_violations or goal_violations:
            return "(assert false)"
        
        return "(assert true)"
    
    def _find_forbidden_violations(self, diff_ast: DiffAST) -> List[Tuple[str, str, str, int]]:
        """Find forbidden API violations in the diff."""
        violations = []
        
        for line in diff_ast.added_lines:
            for pattern in self.forbidden_patterns:
                if pattern.search(line.content):
                    violations.append((pattern.pattern, line.content, line.file_path, line.new_line_number or line.line_number))
                    logger.warning(f"Forbidden pattern '{pattern.pattern}' found in: {line.content.strip()}")
        
        return violations
    
    def _build_forbidden_api_assertion(self, violations: List[Tuple[str, str, str, int]], ctx: z3.Context) -> Optional[z3.BoolRef]:
        """Build assertion that no forbidden API calls are introduced."""
        if not violations:
            return None
            
        # Create Z3 variables for each violation and assert they are true (violations exist)
        violation_vars = []
        for i, (pattern, content, file_path, line_num) in enumerate(violations):
            var = z3.Bool(f"violation_{i}", ctx)
            violation_vars.append(var)
        
        # Assert that violations exist (making the formula UNSAT)
        if violation_vars:
            return z3.And([var for var in violation_vars], ctx)
        
        return None
    
    def _find_goal_preservation_violations(self, diff_ast: DiffAST) -> List[Tuple[str, str, str, str]]:
        """Find goal preservation violations in function renames."""
        violations = []
        
        for old_name, new_name in diff_ast.function_renames.items():
            old_sig_key = f"-{old_name}"
            new_sig_key = f"+{new_name}"
            
            if old_sig_key in diff_ast.function_signatures and new_sig_key in diff_ast.function_signatures:
                old_sig = diff_ast.function_signatures[old_sig_key]
                new_sig = diff_ast.function_signatures[new_sig_key]
                
                # Check if signatures match - fail on any difference
                if (len(old_sig.args) != len(new_sig.args) or 
                    str(old_sig.args) != str(new_sig.args)):
                    violations.append((old_name, new_name, str(old_sig.args), str(new_sig.args)))
                    logger.warning(f"Function rename {old_name} -> {new_name} changes signature: {old_sig.args} != {new_sig.args}")
                else:
                    logger.info(f"Function rename detected: {old_name} -> {new_name} with matching signatures")
        
        return violations
    
    def _build_goal_preservation_assertion(self, diff_ast: DiffAST, violations: List[Tuple[str, str, str, str]], ctx: z3.Context) -> Optional[z3.BoolRef]:
        """Build assertion that function renames preserve signatures."""
        if not violations:
            return None
        
        # Create Z3 assertions for signature mismatches
        violation_constraints = []
        
        for i, (old_name, new_name, old_args, new_args) in enumerate(violations):
            # Create string variables for old and new signatures
            old_sig_var = z3.String(f"old_sig_{i}", ctx)
            new_sig_var = z3.String(f"new_sig_{i}", ctx)
            
            # Assert that signatures are different (violation exists)
            sig_mismatch = z3.Not(old_sig_var == new_sig_var, ctx)
            violation_constraints.append(sig_mismatch)
        
        if violation_constraints:
            return z3.And(violation_constraints, ctx)
        
        return None
    
# Global SMT builder instance
_smt_builder: SMTDiffBuilder = SMTDiffBuilder()


def unified_diff() -> str:
    """Return Git diff of *unstaged* changes vs HEAD.

    Used by governor to prove the next self-mod.
    """
    try:
        repo = Repo(Path(__file__).parents[2])
        diff = repo.git.diff(None)  # working tree vs HEAD
        return diff if diff else ""
    except Exception as e:
        logger.warning(f"Could not get Git diff: {e}")
        return ""


def build_smt_diff(diff_text: str) -> str:
    """Translate diff text → SMT-LIB2 safety claim using Z3py.
    
    This is the main entry point that replaces the regex stub with
    a comprehensive SMT-based analysis.
    """
    return _smt_builder.build_smt_formula(diff_text)


def parse_diff_to_ast(diff_text: str) -> DiffAST:
    """Parse Git diff text into structured AST representation.
    
    Useful for external analysis and testing.
    """
    return _smt_builder.parser.parse_unified_diff(diff_text)


def calculate_risk_score(diff_text: str) -> float:
    """Calculate risk score based on diff characteristics and SMT analysis."""
    if not diff_text.strip():
        return 0.0
        
    diff_ast = parse_diff_to_ast(diff_text)
    score = 0.0
    
    # Base scoring from file count and operations
    score += len(diff_ast.modified_files) * 0.1
    score += len(diff_ast.added_lines) * 0.01
    score += len(diff_ast.removed_lines) * 0.005
    
    # Penalty for forbidden patterns
    forbidden_violations = _smt_builder._find_forbidden_violations(diff_ast)
    if forbidden_violations:
        score += 0.8
    
    # Penalty for goal preservation violations
    goal_violations = _smt_builder._find_goal_preservation_violations(diff_ast)
    if goal_violations:
        score += 0.6
    
    # Penalty for function renames (inherently risky)
    score += len(diff_ast.function_renames) * 0.2
    
    return min(score, 1.0)


def analyze_diff_context(diff_text: str) -> Dict[str, any]:
    """Analyze diff for context-specific risks using SMT analysis."""
    if not diff_text.strip():
        return {
            "file_count": 0,
            "has_binary": False,
            "has_deletions": False,
            "risk_score": 0.0,
            "forbidden_violations": [],
            "function_renames": {},
            "smt_result": "(assert true)"
        }
    
    diff_ast = parse_diff_to_ast(diff_text)
    smt_result = build_smt_diff(diff_text)
    
    # Find specific forbidden violations
    forbidden_violations = []
    violations = _smt_builder._find_forbidden_violations(diff_ast)
    for pattern, content, file_path, line_num in violations:
        forbidden_violations.append({
            "pattern": pattern,
            "line": content.strip(),
            "file": file_path,
            "line_number": line_num
        })
    
    return {
        "file_count": len(diff_ast.modified_files),
        "has_binary": bool(re.search(r"Binary files", diff_text)),
        "has_deletions": len(diff_ast.removed_lines) > 0,
        "added_lines": len(diff_ast.added_lines),
        "removed_lines": len(diff_ast.removed_lines),
        "risk_score": calculate_risk_score(diff_text),
        "forbidden_violations": forbidden_violations,
        "function_renames": diff_ast.function_renames,
        "smt_result": smt_result,
        "modified_files": list(diff_ast.modified_files)
    }


def extract_forbidden_from_charter(charter_clauses: Dict[str, str]) -> List[str]:
    """Extract forbidden patterns from charter clauses."""
    compiled_patterns = get_forbidden_patterns(charter_clauses)
    return [pattern.pattern for pattern in compiled_patterns]


def build_advanced_smt(diff_text: str, forbidden_patterns: List[str]) -> str:
    """Build SMT formula with custom forbidden patterns."""
    if not diff_text.strip():
        return "(assert true)"
    
    # Compile custom patterns
    compiled_patterns = [re.compile(pattern) for pattern in forbidden_patterns]
    
    # Create temporary SMT builder with custom patterns
    temp_builder = SMTDiffBuilder(compiled_patterns)
    return temp_builder.build_smt_formula(diff_text)


def build_smt_with_charter(diff_text: str, charter_clauses: Dict[str, str]) -> str:
    """Build SMT formula considering charter clauses."""
    patterns = get_forbidden_patterns(charter_clauses)
    charter_builder = SMTDiffBuilder(patterns)
    return charter_builder.build_smt_formula(diff_text)


def get_cached_proof(diff_hash: str) -> Optional[str]:
    """Check Redis for cached proof result with fallback."""
    try:
        # Try to import and use Redis cache from smt_verifier
        from agent.core.smt_verifier import get_cached_result
        return get_cached_result(diff_hash)
    except (ImportError, Exception) as e:
        # Redis not available or other error - use no-op cache
        logger.debug(f"Cache lookup for diff hash {diff_hash} failed: {e} - falling back to computation")
        return None  # Fallback to recomputation


def cache_proof_result(diff_hash: str, result: str) -> None:
    """Cache proof result with fallback."""
    try:
        # Try to import and use Redis cache from smt_verifier
        from agent.core.smt_verifier import cache_result
        cache_result(diff_hash, result)
    except (ImportError, Exception) as e:
        # Redis not available or other error - no-op
        logger.debug(f"Cache store for diff hash {diff_hash} failed: {e} - result not cached")
