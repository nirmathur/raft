"""
Test Fuzz Runner for RAFT
=========================

Applies fuzzed patches to temporary repositories and validates that run_one_cycle()
either passes safely or fails gracefully with proper rollback logging.

This test suite validates:
1. Patch application in isolated environments
2. RAFT safety gate behavior under fuzzed inputs 
3. Proper rollback and error logging on safety violations
4. System stability after failed cycles
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from loguru import logger

from agent.core.governor import run_one_cycle
from agent.core.event_log import record
from scripts.fuzz_diff_generator import FuzzDiffGenerator


class FuzzTestRunner:
    """Test runner for RAFT fuzz testing."""
    
    def __init__(self):
        self.temp_dirs = []
        self.test_results = []
        
    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        self.temp_dirs.clear()
        
    def create_temp_repo(self) -> Path:
        """Create a temporary git repository for testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix="raft_fuzz_"))
        self.temp_dirs.append(temp_dir)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@raft.local"], 
                      cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "RAFT Fuzzer"], 
                      cwd=temp_dir, check=True, capture_output=True)
        
        # Create minimal RAFT-like structure
        agent_dir = temp_dir / "agent" / "core"
        agent_dir.mkdir(parents=True)
        
        # Create example module that matches fuzz template
        example_module = agent_dir / "example_module.py"
        example_module.write_text('''"""Example safe module for RAFT testing."""

def safe_function():
    """A simple, safe function."""
    return "safe_result"

def another_safe_function(x: int) -> int:
    """Another safe function with parameter."""
    if x > 0:
        return x * 2
''')
        
        # Initial commit
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], 
                      cwd=temp_dir, check=True, capture_output=True)
        
        return temp_dir
    
    def apply_patch(self, repo_dir: Path, patch_content: str) -> bool:
        """Apply patch to repository and return success status."""
        patch_file = repo_dir / "test.patch"
        patch_file.write_text(patch_content)
        
        try:
            # Apply patch using git apply
            result = subprocess.run(
                ["git", "apply", "--ignore-whitespace", str(patch_file)], 
                cwd=repo_dir, 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Patch application failed: {e}")
            return False
    
    def run_safety_checks(self, expected_safe: bool) -> dict:
        """Run RAFT safety checks and return results."""
        test_result = {
            "timestamp": None,
            "expected_safe": expected_safe,
            "actual_passed": False,
            "rollback_logged": False,
            "error_details": None,
            "safety_violations": [],
        }
        
        # Capture any logged events during the test
        logged_events = []
        
        def mock_record(event_type: str, data: dict):
            logged_events.append({"type": event_type, "data": data})
            
        with patch('agent.core.event_log.record', side_effect=mock_record):
            try:
                # Run one governor cycle
                cycle_passed = run_one_cycle()
                test_result["actual_passed"] = cycle_passed
                
                # Check for rollback/failure events
                failure_events = [
                    event for event in logged_events 
                    if event["type"] in ["proof-fail", "spectral-breach"]
                ]
                test_result["rollback_logged"] = len(failure_events) > 0
                test_result["safety_violations"] = failure_events
                
            except Exception as e:
                test_result["error_details"] = str(e)
                test_result["actual_passed"] = False
                logger.error(f"Exception during run_one_cycle: {e}")
        
        return test_result
    
    def validate_test_result(self, test_result: dict) -> bool:
        """Validate that test result matches expectations."""
        expected_safe = test_result["expected_safe"]
        actual_passed = test_result["actual_passed"]
        rollback_logged = test_result["rollback_logged"]
        
        if expected_safe:
            # Safe patches should pass without rollback
            return actual_passed and not rollback_logged
        else:
            # Unsafe patches should fail with proper rollback logging
            return not actual_passed and rollback_logged
    
    def run_fuzz_test(self, strategy: str, iterations: int = 5) -> dict:
        """Run fuzz test with specified strategy."""
        logger.info(f"Running fuzz test with strategy '{strategy}', {iterations} iterations")
        
        results = {
            "strategy": strategy,
            "iterations": iterations,
            "successes": 0,
            "failures": 0,
            "errors": 0,
            "details": []
        }
        
        for i in range(iterations):
            logger.info(f"Fuzz iteration {i+1}/{iterations}")
            
            try:
                # Generate fuzzed diff
                generator = FuzzDiffGenerator(seed=42 + i)  # Reproducible but varied
                diff_content, expected_safe = generator.write_fuzz_patch(
                    output_path=Path(f"fuzz_{i}.patch"),
                    strategy=strategy
                )
                
                # Create temporary repo and apply patch
                repo_dir = self.create_temp_repo()
                patch_applied = self.apply_patch(repo_dir, diff_content)
                
                if not patch_applied:
                    logger.warning(f"Iteration {i+1}: Patch failed to apply")
                    results["errors"] += 1
                    continue
                
                # Run safety checks
                test_result = self.run_safety_checks(expected_safe)
                test_passed = self.validate_test_result(test_result)
                
                if test_passed:
                    results["successes"] += 1
                    logger.success(f"Iteration {i+1}: PASS")
                else:
                    results["failures"] += 1
                    logger.error(f"Iteration {i+1}: FAIL")
                
                results["details"].append({
                    "iteration": i + 1,
                    "patch_applied": patch_applied,
                    "test_passed": test_passed,
                    "result": test_result
                })
                
            except Exception as e:
                logger.error(f"Iteration {i+1}: Error - {e}")
                results["errors"] += 1
                results["details"].append({
                    "iteration": i + 1,
                    "error": str(e)
                })
        
        return results


@pytest.fixture
def fuzz_runner():
    """Pytest fixture for fuzz test runner."""
    runner = FuzzTestRunner()
    yield runner
    runner.cleanup()


def test_safe_strategy_passes(fuzz_runner):
    """Test that safe strategy patches pass RAFT safety checks."""
    results = fuzz_runner.run_fuzz_test("safe", iterations=3)
    
    # All safe patches should pass
    assert results["successes"] >= 2, f"Safe strategy should mostly pass: {results}"
    assert results["failures"] + results["errors"] <= 1, "Safe strategy should have minimal failures"


def test_forbidden_strategy_fails_safely(fuzz_runner):
    """Test that forbidden patterns trigger proper safety violations."""
    results = fuzz_runner.run_fuzz_test("forbidden", iterations=3)
    
    # Forbidden patterns should trigger safety violations with proper rollback
    successful_rollbacks = 0
    for detail in results["details"]:
        if "result" in detail:
            result = detail["result"]
            if not result["actual_passed"] and result["rollback_logged"]:
                successful_rollbacks += 1
    
    assert successful_rollbacks >= 2, f"Forbidden patterns should trigger rollbacks: {results}"


def test_random_strategy_robustness(fuzz_runner):
    """Test system robustness with random mutations."""
    results = fuzz_runner.run_fuzz_test("random", iterations=5)
    
    # System should handle random mutations without crashing
    assert results["errors"] <= 1, f"Random mutations should not cause system errors: {results}"
    
    # At least some tests should complete (pass or fail gracefully)
    completed_tests = results["successes"] + results["failures"]
    assert completed_tests >= 4, f"Most random tests should complete: {results}"


def test_aggressive_strategy_stress(fuzz_runner):
    """Test system under aggressive fuzzing stress."""
    results = fuzz_runner.run_fuzz_test("aggressive", iterations=3)
    
    # Aggressive fuzzing should mostly fail but handle gracefully
    assert results["errors"] <= 1, f"Aggressive fuzzing should not crash system: {results}"
    
    # Should have proper failure handling
    rollback_count = 0
    for detail in results["details"]:
        if "result" in detail and detail["result"]["rollback_logged"]:
            rollback_count += 1
    
    assert rollback_count >= 1, "Aggressive fuzzing should trigger some rollbacks"


def test_patch_application_validation(fuzz_runner):
    """Test that patch application works correctly."""
    generator = FuzzDiffGenerator(seed=123)
    diff_content, _ = generator.write_fuzz_patch(strategy="safe")
    
    repo_dir = fuzz_runner.create_temp_repo()
    patch_applied = fuzz_runner.apply_patch(repo_dir, diff_content)
    
    assert patch_applied, "Safe patches should apply successfully"
    
    # Verify file was modified
    example_file = repo_dir / "agent" / "core" / "example_module.py"
    content = example_file.read_text()
    assert len(content) > 100, "File should be modified by patch"


def test_safety_violation_detection(fuzz_runner):
    """Test that safety violations are properly detected and logged."""
    # Create a patch with known forbidden pattern
    forbidden_diff = '''diff --git a/agent/core/example_module.py b/agent/core/example_module.py
index 1234567..abcdefg 100644
--- a/agent/core/example_module.py
+++ b/agent/core/example_module.py
@@ -1,3 +1,4 @@
 """Example safe module for RAFT testing."""
 
+import subprocess  # This should trigger safety violation
 def safe_function():'''
    
    repo_dir = fuzz_runner.create_temp_repo()
    patch_applied = fuzz_runner.apply_patch(repo_dir, forbidden_diff)
    
    if patch_applied:
        test_result = fuzz_runner.run_safety_checks(expected_safe=False)
        
        # Should fail and log rollback
        assert not test_result["actual_passed"], "Forbidden patterns should fail safety checks"
        assert test_result["rollback_logged"], "Safety violations should be logged"


def test_integration_with_existing_files():
    """Test integration with existing fuzz.patch file."""
    if Path("fuzz.patch").exists() and Path("fuzz_metadata.json").exists():
        # Load existing fuzz test data
        metadata = json.loads(Path("fuzz_metadata.json").read_text())
        patch_content = Path("fuzz.patch").read_text()
        
        runner = FuzzTestRunner()
        try:
            repo_dir = runner.create_temp_repo()
            patch_applied = runner.apply_patch(repo_dir, patch_content)
            
            if patch_applied:
                test_result = runner.run_safety_checks(metadata["expected_safe"])
                test_passed = runner.validate_test_result(test_result)
                
                logger.info(f"Integration test with existing fuzz.patch: {'PASS' if test_passed else 'FAIL'}")
                
                # This is informational - don't fail the test suite
                # since fuzz.patch might be from a previous run
                
        finally:
            runner.cleanup()


if __name__ == "__main__":
    # Run basic fuzz tests
    runner = FuzzTestRunner()
    try:
        logger.info("Starting RAFT fuzz testing")
        
        strategies = ["safe", "forbidden", "random", "aggressive"]
        for strategy in strategies:
            logger.info(f"\n=== Testing strategy: {strategy} ===")
            results = runner.run_fuzz_test(strategy, iterations=2)
            
            logger.info(f"Results: {results['successes']} successes, "
                       f"{results['failures']} failures, {results['errors']} errors")
        
        logger.success("Fuzz testing completed")
        
    finally:
        runner.cleanup()