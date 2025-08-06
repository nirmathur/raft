#!/usr/bin/env python3
"""
Fuzz Diff Generator for RAFT
============================

Generates randomized patch files by mutating safe template diffs.
This tool creates realistic but potentially unsafe diff mutations to test
RAFT's safety gates (spectral radius, Z3 proof verification, energy limits).

Usage:
    python scripts/fuzz_diff_generator.py

Output:
    - Writes fuzzed patch to fuzz.patch
    - Logs mutation strategy and safety expectations
"""

import hashlib
import random
import re
import sys
from pathlib import Path
from typing import List, Tuple

from loguru import logger

# Base safe template diff (known to pass RAFT safety checks)
SAFE_TEMPLATE_DIFF = """diff --git a/agent/core/example_module.py b/agent/core/example_module.py
index 1234567..abcdefg 100644
--- a/agent/core/example_module.py
+++ b/agent/core/example_module.py
@@ -1,5 +1,6 @@
 """Example safe module for RAFT testing."""
 
+# Safe comment addition
def safe_function():
    """A simple, safe function."""
    return "safe_result"
def another_safe_function(x: int) -> int:
    """Another safe function with parameter."""
    if x > 0:
        return x * 2
    # Safe logic extension
    logger.info("Processing zero or negative input")
    return 0
"""

# Forbidden patterns from RAFT diff_builder.py
FORBIDDEN_PATTERNS = [
    r"\bsubprocess\b",
    r"\bos\.system\b", 
    r"\beval\b",
    r"\bexec\b",
    r"\bimport\s+\*",
    r"\b__import__\b",
    r"\bglobals\b",
    r"\blocals\b",
]

# Additional risky patterns for more aggressive fuzzing
RISKY_PATTERNS = [
    "import subprocess",
    "os.system(",
    "eval(",
    "exec(",
    "from os import *",
    "__import__('os')",
    "globals()",
    "locals()",
    "open('/etc/passwd')",
    "import socket",
    "threading.Thread",
    "multiprocessing.Process",
]

# Safe mutations that should pass RAFT checks
SAFE_MUTATIONS = [
    "+ # Additional safe comment",
    "+ logger.debug('Safe debug message')",
    "+ return_value = process_safely(data)",
    "+ if condition: # Safe conditional",
    "+ safe_variable = 42",
    "+ validated_input = validate_input(user_data)",
    "+ result = compute_safely(parameters)",
]

# File content mutations for binary/large diffs
BINARY_MUTATIONS = [
    "Binary files a/data/model.pkl and b/data/model.pkl differ",
    "Binary files a/assets/large_file.bin and b/assets/large_file.bin differ",
]


class FuzzDiffGenerator:
    """Generate fuzzed diffs for RAFT safety testing."""
    
    def __init__(self, seed: int = None):
        """Initialize generator with optional seed for reproducibility."""
        if seed is not None:
            random.seed(seed)
        self.mutation_log = []
        
    def _add_safe_mutations(self, diff_lines: List[str]) -> List[str]:
        """Add safe mutations that should pass RAFT checks."""
        mutations = random.choices(SAFE_MUTATIONS, k=random.randint(1, 3))
        insert_pos = random.randint(len(diff_lines) // 2, len(diff_lines) - 1)
        
        for i, mutation in enumerate(mutations):
            diff_lines.insert(insert_pos + i, mutation)
            
        self.mutation_log.append(f"Added {len(mutations)} safe mutations")
        return diff_lines
    
    def _add_forbidden_patterns(self, diff_lines: List[str]) -> List[str]:
        """Add forbidden patterns that should trigger RAFT safety violations."""
        risky_pattern = random.choice(RISKY_PATTERNS)
        insert_pos = random.randint(len(diff_lines) // 2, len(diff_lines) - 1)
        diff_lines.insert(insert_pos, f"+ {risky_pattern}")
        
        self.mutation_log.append(f"Added forbidden pattern: {risky_pattern}")
        return diff_lines
    
    def _add_deletions(self, diff_lines: List[str]) -> List[str]:
        """Add random deletions to increase diff complexity."""
        # Find existing addition lines and convert some to deletions
        addition_indices = [i for i, line in enumerate(diff_lines) if line.startswith('+')]
        if addition_indices:
            delete_count = random.randint(1, min(3, len(addition_indices)))
            for _ in range(delete_count):
                idx = random.choice(addition_indices)
                original_line = diff_lines[idx]
                diff_lines[idx] = original_line.replace('+', '-', 1)
                addition_indices.remove(idx)
                
        self.mutation_log.append(f"Added random deletions")
        return diff_lines
    
    def _add_binary_files(self, diff_lines: List[str]) -> List[str]:
        """Add binary file changes to test binary diff handling."""
        binary_change = random.choice(BINARY_MUTATIONS)
        diff_lines.append(binary_change)
        
        self.mutation_log.append("Added binary file changes")
        return diff_lines
    
    def _mutate_line_numbers(self, diff_lines: List[str]) -> List[str]:
        """Mutate hunk headers to test diff parsing robustness."""
        for i, line in enumerate(diff_lines):
            if line.startswith('@@'):
                # Randomly adjust line numbers
                parts = line.split()
                if len(parts) >= 3:
                    old_range = parts[1]
                    new_range = parts[2]
                    
                    # Slightly modify ranges
                    if ',' in old_range:
                        start, count = old_range[1:].split(',')
                        new_count = str(int(count) + random.randint(-1, 2))
                        parts[1] = f"-{start},{new_count}"
                    
                    if ',' in new_range:
                        start, count = new_range[1:].split(',')
                        new_count = str(int(count) + random.randint(-1, 2))
                        parts[2] = f"+{start},{new_count}"
                    
                    diff_lines[i] = ' '.join(parts)
                    
        self.mutation_log.append("Mutated hunk line numbers")
        return diff_lines
    
    def generate_fuzz_diff(self, strategy: str = "random") -> str:
        """Generate a fuzzed diff based on the specified strategy.
        
        Args:
            strategy: Mutation strategy - 'safe', 'forbidden', 'random', 'aggressive'
            
        Returns:
            String containing the fuzzed diff
        """
        diff_lines = SAFE_TEMPLATE_DIFF.strip().split('\n')
        self.mutation_log = [f"Starting with strategy: {strategy}"]
        
        if strategy == "safe":
            # Only safe mutations - should pass RAFT checks
            diff_lines = self._add_safe_mutations(diff_lines)
            
        elif strategy == "forbidden": 
            # Include forbidden patterns - should trigger safety violations
            diff_lines = self._add_safe_mutations(diff_lines)
            diff_lines = self._add_forbidden_patterns(diff_lines)
            
        elif strategy == "aggressive":
            # Maximum chaos - multiple forbidden patterns, binary files, etc.
            diff_lines = self._add_forbidden_patterns(diff_lines)
            diff_lines = self._add_forbidden_patterns(diff_lines)  # Double trouble
            diff_lines = self._add_binary_files(diff_lines)
            diff_lines = self._add_deletions(diff_lines)
            diff_lines = self._mutate_line_numbers(diff_lines)
            
        else:  # random strategy
            # Randomly apply different mutation types
            mutations = [
                (self._add_safe_mutations, 0.7),
                (self._add_forbidden_patterns, 0.3),
                (self._add_deletions, 0.4),
                (self._add_binary_files, 0.2),
                (self._mutate_line_numbers, 0.3),
            ]
            
            for mutation_func, probability in mutations:
                if random.random() < probability:
                    diff_lines = mutation_func(diff_lines)
        
        return '\n'.join(diff_lines)
    
    def write_fuzz_patch(self, output_path: Path = None, strategy: str = "random") -> Tuple[str, bool]:
        """Generate and write fuzzed patch to file.
        
        Args:
            output_path: Path to write patch file (default: fuzz.patch)
            strategy: Mutation strategy
            
        Returns:
            Tuple of (diff_content, expected_to_pass_safety_checks)
        """
        if output_path is None:
            output_path = Path("fuzz.patch")
            
        diff_content = self.generate_fuzz_diff(strategy)
        
        # Determine if this should pass RAFT safety checks
        expected_safe = strategy == "safe"
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, diff_content):
                expected_safe = False
                break
        
        # Write patch file
        output_path.write_text(diff_content)
        
        # Generate metadata
        diff_hash = hashlib.sha256(diff_content.encode()).hexdigest()[:8]
        
        logger.info(f"Generated fuzz patch: {output_path}")
        logger.info(f"Strategy: {strategy}")
        logger.info(f"Expected to pass safety: {expected_safe}")
        logger.info(f"Diff hash: {diff_hash}")
        
        for log_entry in self.mutation_log:
            logger.debug(f"Mutation: {log_entry}")
            
        return diff_content, expected_safe


def main():
    """Main entry point for fuzz diff generator."""
    
    # Parse strategy from command line args
    strategy = "random"
    if len(sys.argv) > 1:
        strategy = sys.argv[1]
        
    if strategy not in ["safe", "forbidden", "random", "aggressive"]:
        logger.error(f"Invalid strategy: {strategy}")
        logger.info("Valid strategies: safe, forbidden, random, aggressive")
        sys.exit(1)
        
    # Generate seed for reproducibility in CI
    seed = random.randint(1, 1000000)
    logger.info(f"Using seed: {seed}")
    
    generator = FuzzDiffGenerator(seed=seed)
    diff_content, expected_safe = generator.write_fuzz_patch(strategy=strategy)
    
    # Write metadata for test runner
    metadata = {
        "strategy": strategy,
        "expected_safe": expected_safe,
        "seed": seed,
        "diff_hash": hashlib.sha256(diff_content.encode()).hexdigest()[:8]
    }
    
    import json
    Path("fuzz_metadata.json").write_text(json.dumps(metadata, indent=2))
    
    logger.success(f"Fuzz diff generated successfully with strategy '{strategy}'")
    logger.info(f"Expected safety outcome: {'PASS' if expected_safe else 'FAIL'}")


if __name__ == "__main__":
    main()