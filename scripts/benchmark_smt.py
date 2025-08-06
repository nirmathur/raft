#!/usr/bin/env python3
"""
benchmark_smt.py
----------------
Benchmark Z3 SMT solving performance on Git diffs of increasing size and complexity.

This script generates synthetic diffs of various sizes and measures the time
taken by our SMT-based diff analyzer to process them.

Usage:
    python scripts/benchmark_smt.py [--output results.json] [--verbose]
"""

import argparse
import json
import time
import random
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from pathlib import Path
import sys

# Add the project root to the path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.diff_builder import build_smt_diff, parse_diff_to_ast, analyze_diff_context


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    diff_size: int
    line_count: int
    file_count: int
    has_forbidden: bool
    has_function_renames: bool
    smt_build_time: float
    smt_result: str
    risk_score: float
    added_lines: int = 0
    removed_lines: int = 0
    memory_usage_mb: float = 0.0


class DiffGenerator:
    """Generates synthetic Git diffs for benchmarking."""
    
    SAFE_OPERATIONS = [
        "print('Hello World')",
        "x = y + z",
        "result = calculate(a, b)",
        "log.info('Processing item')",
        "data = json.loads(response)",
        "with open('file.txt') as f: content = f.read()",
        "for item in items: process(item)",
        "if condition: do_something()",
        "return result",
        "class MyClass: pass"
    ]
    
    FORBIDDEN_OPERATIONS = [
        "exec('dangerous_code')",
        "subprocess.call(['rm', '-rf', '/'])",
        "eval(user_input)",
        "os.system('malicious_command')",
        "__import__('dangerous_module')",
        "globals()['secret'] = 'exposed'",
        "locals().update(malicious_dict)"
    ]
    
    def __init__(self, seed: int = 42):
        """Initialize with random seed for reproducible results."""
        random.seed(seed)
    
    def generate_function_diff(self, old_name: str, new_name: str, args: List[str]) -> str:
        """Generate a function rename diff."""
        args_str = ", ".join(args)
        return f"""diff --git a/test.py b/test.py
@@ -1,3 +1,3 @@
-def {old_name}({args_str}):
+def {new_name}({args_str}):
     return "result"
"""
    
    def generate_safe_diff(self, line_count: int, file_count: int = 1) -> str:
        """Generate a safe diff with specified number of lines and files."""
        diff_parts = []
        
        for file_idx in range(file_count):
            file_name = f"file_{file_idx}.py"
            diff_parts.append(f"diff --git a/{file_name} b/{file_name}")
            diff_parts.append(f"index {'a' * 7}..{'b' * 7} 100644")
            diff_parts.append(f"--- a/{file_name}")
            diff_parts.append(f"+++ b/{file_name}")
            
            lines_per_file = line_count // file_count
            if file_idx == 0:
                lines_per_file += line_count % file_count  # Add remainder to first file
            lines_per_file = max(1, lines_per_file)  # Ensure every file has at least one line
            
            diff_parts.append(f"@@ -1,2 +1,{lines_per_file + 2} @@")
            diff_parts.append(" def existing_function():")
            diff_parts.append("     pass")
            
            for i in range(lines_per_file):
                operation = random.choice(self.SAFE_OPERATIONS)
                diff_parts.append(f"+    {operation}")
        
        return "\n".join(diff_parts)
    
    def generate_unsafe_diff(self, line_count: int, file_count: int = 1, 
                           forbidden_ratio: float = 0.1) -> str:
        """Generate an unsafe diff with some forbidden operations."""
        diff_parts = []
        forbidden_count = max(1, int(line_count * forbidden_ratio))
        safe_count = line_count - forbidden_count
        
        for file_idx in range(file_count):
            file_name = f"dangerous_{file_idx}.py"
            diff_parts.append(f"diff --git a/{file_name} b/{file_name}")
            diff_parts.append(f"index {'a' * 7}..{'b' * 7} 100644")
            diff_parts.append(f"--- a/{file_name}")
            diff_parts.append(f"+++ b/{file_name}")
            
            lines_per_file = line_count // file_count
            if file_idx == 0:
                lines_per_file += line_count % file_count
            lines_per_file = max(1, lines_per_file)  # Ensure every file has at least one line
            
            diff_parts.append(f"@@ -1,2 +1,{lines_per_file + 2} @@")
            diff_parts.append(" def existing_function():")
            diff_parts.append("     pass")
            
            # Mix safe and forbidden operations
            operations = (
                [random.choice(self.SAFE_OPERATIONS) for _ in range(safe_count // file_count)] +
                [random.choice(self.FORBIDDEN_OPERATIONS) for _ in range(forbidden_count // file_count)]
            )
            random.shuffle(operations)
            
            for operation in operations[:lines_per_file]:
                diff_parts.append(f"+    {operation}")
        
        return "\n".join(diff_parts)
    
    def generate_function_rename_diff(self, rename_count: int) -> str:
        """Generate a diff with function renames."""
        diff_parts = []
        diff_parts.append("diff --git a/refactor.py b/refactor.py")
        diff_parts.append("@@ -1,10 +1,10 @@")
        
        for i in range(rename_count):
            old_name = f"old_function_{i}"
            new_name = f"new_function_{i}"
            args = [f"arg_{j}" for j in range(random.randint(1, 4))]
            args_str = ", ".join(args)
            
            diff_parts.append(f"-def {old_name}({args_str}):")
            diff_parts.append(f"+def {new_name}({args_str}):")
            diff_parts.append(" " * 4 + "return 'result'")
        
        return "\n".join(diff_parts)


class SMTBenchmarker:
    """Benchmarks SMT solving performance on Git diffs."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.generator = DiffGenerator()
        self.results: List[BenchmarkResult] = []
    
    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[BENCHMARK] {message}")
    
    def measure_memory_usage(self) -> float:
        """Measure current memory usage in MB.
        
        If psutil missing, memory usage reported as 0.
        """
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            if self.verbose:
                print("[BENCHMARK] psutil missing – memory not sampled")
            return 0.0  # psutil not available
    
    def benchmark_diff(self, diff_text: str, description: str) -> BenchmarkResult:
        """Benchmark a single diff and return results."""
        self.log(f"Benchmarking: {description}")
        
        # Parse diff to get statistics
        ast = parse_diff_to_ast(diff_text)
        
        # Get line counts for accurate metrics
        added = len(ast.added_lines)
        removed = len(ast.removed_lines)
        
        # Measure memory before
        memory_before = self.measure_memory_usage()
        
        # Time the SMT building process
        start_time = time.perf_counter()
        smt_result = build_smt_diff(diff_text)
        end_time = time.perf_counter()
        
        # Measure memory after
        memory_after = self.measure_memory_usage()
        memory_usage = max(0, memory_after - memory_before)
        
        build_time = end_time - start_time
        
        # Get additional context
        context = analyze_diff_context(diff_text)
        
        # Check goal preservation violations
        from agent.core.diff_builder import _smt_builder
        has_goal_violations = bool(_smt_builder._find_goal_preservation_violations(ast))
        
        result = BenchmarkResult(
            diff_size=len(diff_text),
            line_count=len(ast.added_lines) + len(ast.removed_lines),
            file_count=len(ast.modified_files),
            has_forbidden=len(context["forbidden_violations"]) > 0,
            has_function_renames=has_goal_violations,
            smt_build_time=build_time,
            smt_result=smt_result,
            risk_score=context["risk_score"],
            added_lines=added,
            removed_lines=removed,
            memory_usage_mb=memory_usage
        )
        
        self.log(f"  Time: {build_time:.4f}s, Result: {smt_result}, Risk: {result.risk_score:.3f}")
        return result
    
    def benchmark_size_scaling(self, sizes: List[int], trials: int = 3) -> List[BenchmarkResult]:
        """Benchmark how performance scales with diff size."""
        self.log("=== Benchmarking Size Scaling ===")
        results = []
        
        for size in sizes:
            trial_results = []
            for trial in range(trials):
                # Generate safe diff of specified size
                diff_text = self.generator.generate_safe_diff(size)
                result = self.benchmark_diff(diff_text, f"Safe diff, {size} lines (trial {trial + 1})")
                trial_results.append(result)
            
            # Average the trial results
            avg_time = statistics.mean(r.smt_build_time for r in trial_results)
            avg_memory = statistics.mean(r.memory_usage_mb for r in trial_results)
            
            # Use the first trial's other metrics (they should be similar)
            representative = trial_results[0]
            representative.smt_build_time = avg_time
            representative.memory_usage_mb = avg_memory
            
            results.append(representative)
        
        return results
    
    def benchmark_forbidden_patterns(self, line_count: int = 50) -> List[BenchmarkResult]:
        """Benchmark performance on diffs with forbidden patterns."""
        self.log("=== Benchmarking Forbidden Patterns ===")
        results = []
        
        # Test different ratios of forbidden content
        forbidden_ratios = [0.0, 0.1, 0.2, 0.5, 1.0]
        
        for ratio in forbidden_ratios:
            if ratio == 0.0:
                diff_text = self.generator.generate_safe_diff(line_count)
                description = f"Safe diff, {line_count} lines"
            else:
                diff_text = self.generator.generate_unsafe_diff(line_count, forbidden_ratio=ratio)
                description = f"Unsafe diff, {line_count} lines, {ratio * 100:.0f}% forbidden"
            
            result = self.benchmark_diff(diff_text, description)
            results.append(result)
        
        return results
    
    def benchmark_function_renames(self, rename_counts: List[int]) -> List[BenchmarkResult]:
        """Benchmark performance on function rename diffs."""
        self.log("=== Benchmarking Function Renames ===")
        results = []
        
        for count in rename_counts:
            diff_text = self.generator.generate_function_rename_diff(count)
            result = self.benchmark_diff(diff_text, f"Function renames, {count} functions")
            results.append(result)
        
        return results
    
    def benchmark_file_scaling(self, line_count: int = 100, file_counts: List[int] = None) -> List[BenchmarkResult]:
        """Benchmark performance scaling with number of files."""
        if file_counts is None:
            file_counts = [1, 5, 10, 20, 50]
        
        self.log("=== Benchmarking File Count Scaling ===")
        results = []
        
        for file_count in file_counts:
            diff_text = self.generator.generate_safe_diff(line_count, file_count)
            result = self.benchmark_diff(diff_text, f"Safe diff, {line_count} lines, {file_count} files")
            results.append(result)
        
        return results
    
    def run_comprehensive_benchmark(self) -> Dict[str, List[BenchmarkResult]]:
        """Run a comprehensive benchmark suite."""
        self.log("Starting comprehensive SMT diff benchmark suite...")
        
        benchmark_results = {}
        
        # Size scaling benchmark
        size_results = self.benchmark_size_scaling([10, 25, 50, 100, 200, 500, 1000])
        benchmark_results["size_scaling"] = size_results
        self.results.extend(size_results)
        
        # Forbidden patterns benchmark
        forbidden_results = self.benchmark_forbidden_patterns(100)
        benchmark_results["forbidden_patterns"] = forbidden_results
        self.results.extend(forbidden_results)
        
        # Function renames benchmark
        rename_results = self.benchmark_function_renames([1, 5, 10, 20, 50])
        benchmark_results["function_renames"] = rename_results
        self.results.extend(rename_results)
        
        # File scaling benchmark
        file_results = self.benchmark_file_scaling(100, [1, 5, 10, 20])
        benchmark_results["file_scaling"] = file_results
        self.results.extend(file_results)
        
        return benchmark_results
    
    def generate_report(self, results: Dict[str, List[BenchmarkResult]]) -> Dict[str, Any]:
        """Generate a summary report of benchmark results."""
        report = {
            "summary": {
                "total_benchmarks": sum(len(results_list) for results_list in results.values()),
                "total_time": sum(r.smt_build_time for results_list in results.values() for r in results_list),
                "avg_time_per_benchmark": 0.0,
                "max_time": 0.0,
                "min_time": float('inf'),
                "performance_insights": []
            },
            "detailed_results": {}
        }
        
        all_times = [r.smt_build_time for results_list in results.values() for r in results_list]
        if all_times:
            report["summary"]["avg_time_per_benchmark"] = statistics.mean(all_times)
            report["summary"]["max_time"] = max(all_times)
            report["summary"]["min_time"] = min(all_times)
        
        # Generate insights
        insights = []
        
        # Size scaling analysis
        if "size_scaling" in results:
            size_results = results["size_scaling"]
            if len(size_results) >= 2:
                first_time = size_results[0].smt_build_time
                last_time = size_results[-1].smt_build_time
                first_size = size_results[0].line_count
                last_size = size_results[-1].line_count
                
                size_ratio = last_size / first_size if first_size > 0 else 1
                time_ratio = last_time / first_time if first_time > 0 else 1
                
                if time_ratio < size_ratio:
                    insights.append(f"SMT solver scales well: {size_ratio:.1f}x size increase → {time_ratio:.1f}x time increase")
                else:
                    insights.append(f"SMT solver scaling concern: {size_ratio:.1f}x size increase → {time_ratio:.1f}x time increase")
        
        # Forbidden pattern analysis
        if "forbidden_patterns" in results:
            forbidden_results = results["forbidden_patterns"]
            safe_times = [r.smt_build_time for r in forbidden_results if not r.has_forbidden]
            unsafe_times = [r.smt_build_time for r in forbidden_results if r.has_forbidden]
            
            if safe_times and unsafe_times:
                avg_safe = statistics.mean(safe_times)
                avg_unsafe = statistics.mean(unsafe_times)
                ratio = avg_unsafe / avg_safe if avg_safe > 0 else 1
                
                if ratio > 1.5:
                    insights.append(f"Forbidden pattern detection adds overhead: {ratio:.1f}x slower than safe diffs")
                else:
                    insights.append(f"Forbidden pattern detection is efficient: only {ratio:.1f}x slower than safe diffs")
        
        report["summary"]["performance_insights"] = insights
        
        # Add detailed results
        for category, category_results in results.items():
            report["detailed_results"][category] = [asdict(r) for r in category_results]
        
        return report


def main():
    """Main entry point for the benchmark script."""
    parser = argparse.ArgumentParser(description="Benchmark SMT diff analysis performance")
    parser.add_argument("--output", "-o", type=str, help="Output file for results (JSON format)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmark with smaller test cases")
    
    args = parser.parse_args()
    
    benchmarker = SMTBenchmarker(verbose=args.verbose)
    
    if args.quick:
        # Quick benchmark for development/testing
        print("Running quick benchmark...")
        results = {
            "size_scaling": benchmarker.benchmark_size_scaling([10, 50, 100], trials=1),
            "forbidden_patterns": benchmarker.benchmark_forbidden_patterns(50)
        }
    else:
        # Full comprehensive benchmark
        print("Running comprehensive benchmark suite...")
        results = benchmarker.run_comprehensive_benchmark()
    
    # Generate report
    report = benchmarker.generate_report(results)
    
    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*60)
    print(f"Total benchmarks: {report['summary']['total_benchmarks']}")
    print(f"Total time: {report['summary']['total_time']:.4f}s")
    print(f"Average time per benchmark: {report['summary']['avg_time_per_benchmark']:.4f}s")
    print(f"Min time: {report['summary']['min_time']:.4f}s")
    print(f"Max time: {report['summary']['max_time']:.4f}s")
    
    print("\nPerformance Insights:")
    for insight in report['summary']['performance_insights']:
        print(f"  • {insight}")
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed results saved to: {output_path}")
    
    print("\nBenchmark complete!")


if __name__ == "__main__":
    main()