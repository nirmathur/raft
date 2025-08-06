# RAFT Automation Documentation

## Overview

This document describes the automated testing and validation systems implemented for the Recursive Agent for Formal Trust (RAFT). The automation framework ensures continuous validation of RAFT's safety guarantees through comprehensive fuzz testing.

## Nightly Fuzz Testing

### Purpose

The nightly fuzz testing system validates RAFT's robustness against unexpected inputs and edge cases by:

- Generating randomized patch mutations based on safe templates
- Testing safety gate behavior under various input conditions 
- Validating proper rollback and error handling mechanisms
- Ensuring system stability after failed governance cycles

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Fuzz Generator  │───▶│ Test Runner     │───▶│ Safety Validator│
│                 │    │                 │    │                 │
│ • Safe templates│    │ • Temp repos    │    │ • run_one_cycle │
│ • Mutation logic│    │ • Patch apply   │    │ • Event logging │
│ • Risk patterns │    │ • Isolation     │    │ • Rollback check│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ fuzz.patch      │    │ Test artifacts  │    │ GitHub Issues   │
│ fuzz_metadata   │    │ System logs     │    │ Auto-tracking   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Components

#### 1. Fuzz Diff Generator (`scripts/fuzz_diff_generator.py`)

**Purpose:** Generate realistic but potentially unsafe diff mutations for testing RAFT safety gates.

**Features:**
- Multiple mutation strategies: `safe`, `forbidden`, `random`, `aggressive`
- Configurable seed for reproducible testing
- Built-in forbidden pattern detection based on RAFT charter
- Metadata generation for test validation

**Usage:**
```bash
# Generate safe mutations (should pass RAFT checks)
python scripts/fuzz_diff_generator.py safe

# Generate forbidden patterns (should trigger safety violations)
python scripts/fuzz_diff_generator.py forbidden

# Random mixed strategy
python scripts/fuzz_diff_generator.py random

# Maximum chaos testing
python scripts/fuzz_diff_generator.py aggressive
```

**Output Files:**
- `fuzz.patch` - Generated diff in unified format
- `fuzz_metadata.json` - Test metadata including strategy and expected outcomes

#### 2. Fuzz Test Runner (`tests/test_fuzz_runner.py`)

**Purpose:** Apply fuzzed patches to isolated repositories and validate RAFT behavior.

**Test Coverage:**
- Patch application in temporary git repositories
- `run_one_cycle()` execution under fuzzed conditions
- Safety violation detection and logging validation
- System stability after failed cycles

**Key Test Functions:**
- `test_safe_strategy_passes()` - Validates safe patches pass RAFT checks
- `test_forbidden_strategy_fails_safely()` - Ensures forbidden patterns trigger proper rollbacks
- `test_random_strategy_robustness()` - Tests system robustness under random mutations
- `test_aggressive_strategy_stress()` - Stress testing with maximum complexity

**Example Usage:**
```bash
# Run all fuzz tests
pytest tests/test_fuzz_runner.py -v

# Test specific strategy
pytest tests/test_fuzz_runner.py -k "test_safe_strategy"

# Direct test runner execution
python tests/test_fuzz_runner.py
```

#### 3. GitHub Actions Workflow (`.github/workflows/fuzz.yml`)

**Purpose:** Automated nightly execution of fuzz tests with intelligent issue management.

**Schedule:** Daily at 2:00 AM UTC (`0 2 * * *`)

**Matrix Strategy:**
```yaml
strategy:
  matrix:
    fuzz-strategy: [safe, forbidden, random, aggressive]
```

**Workflow Steps:**

1. **Environment Setup**
   - Python 3.11 installation
   - Poetry dependency management
   - Docker service startup (PostgreSQL, Redis)

2. **Fuzz Testing**
   - Generate fuzzed diffs for each strategy
   - Apply patches to temporary repositories
   - Execute RAFT safety validation
   - Collect comprehensive test artifacts

3. **Issue Management**
   - Auto-create GitHub issues on test failures
   - Prevent duplicate issues within 24-hour windows
   - Add comments to existing issues for repeated failures
   - Auto-close resolved issues after 3 consecutive successful runs

4. **Artifact Collection**
   - Generated fuzz patches and metadata
   - Test execution logs and results
   - System information and container logs
   - 30-day retention for debugging

### Manual Execution

The workflow can be manually triggered with custom parameters:

```yaml
workflow_dispatch:
  inputs:
    strategy: 'random'  # safe, forbidden, random, aggressive, all
    iterations: '10'    # number of test iterations
```

### Issue Tracking

#### Automatic Issue Creation

When fuzz tests fail, the system automatically creates GitHub issues with:

- **Title:** `🚨 RAFT Fuzz Test Failure - {strategy} strategy`
- **Labels:** `fuzz-test-failure`, `strategy-{name}`, `automated`
- **Content:**
  - Failure timestamp and commit information
  - Direct links to workflow logs and artifacts
  - Reproduction instructions
  - Impact assessment based on strategy type
  - Investigation guidelines

#### Priority Classification

- **HIGH PRIORITY:** `safe` strategy failures (basic functionality issues)
- **MEDIUM PRIORITY:** `aggressive` strategy failures (edge case handling)
- **REVIEW NEEDED:** `forbidden`/`random` failures (potential safety concerns)

#### Issue Lifecycle

1. **Creation:** First failure triggers new issue
2. **Updates:** Subsequent failures add comments instead of new issues
3. **Resolution:** Auto-closure after 3 consecutive successful test runs
4. **Tracking:** Labels enable filtering and automated management

## Usage Guide

### Local Development

1. **Generate Test Data:**
   ```bash
   # Create fuzzed patch for testing
   poetry run python scripts/fuzz_diff_generator.py random
   ```

2. **Run Tests Locally:**
   ```bash
   # Full test suite
   poetry run pytest tests/test_fuzz_runner.py -v
   
   # Specific strategy testing
   poetry run pytest tests/test_fuzz_runner.py -k "forbidden"
   ```

3. **Debug Failures:**
   ```bash
   # Examine generated metadata
   cat fuzz_metadata.json
   
   # Review patch content
   cat fuzz.patch
   
   # Manual RAFT testing
   poetry run python -m agent.core.governor
   ```

### Continuous Integration

The nightly workflow automatically:

1. Tests all four mutation strategies in parallel
2. Uploads artifacts for debugging failed tests
3. Creates/updates GitHub issues for tracking failures
4. Provides comprehensive logging for investigation

### Monitoring and Alerts

- **GitHub Issues:** Primary alerting mechanism for test failures
- **Workflow Artifacts:** Detailed logs and system state for debugging
- **Metrics Dashboard:** Integration with RAFT metrics system (if configured)

## Configuration

### Environment Variables

```bash
# Workflow customization
PYTHON_VERSION=3.11          # Python runtime version
FUZZ_ITERATIONS=10           # Default test iterations
ARTIFACT_RETENTION_DAYS=30   # Artifact storage duration
```

### Strategy Configuration

Modify `scripts/fuzz_diff_generator.py` to adjust:

- **Forbidden Patterns:** Update `FORBIDDEN_PATTERNS` array
- **Safe Mutations:** Modify `SAFE_MUTATIONS` for realistic safe changes
- **Mutation Probabilities:** Adjust probability weights in random strategy
- **Template Diffs:** Update `SAFE_TEMPLATE_DIFF` for different base scenarios

### Test Sensitivity

Adjust test expectations in `tests/test_fuzz_runner.py`:

- **Success Thresholds:** Modify assertion expectations for strategy outcomes
- **Iteration Counts:** Change test iteration counts for faster/thorough testing
- **Timeout Values:** Adjust test timeouts for different environments

## Troubleshooting

### Common Issues

1. **Patch Application Failures**
   ```bash
   # Check git repository state
   git status
   git log --oneline -n 5
   
   # Validate patch format
   git apply --check fuzz.patch
   ```

2. **Service Dependency Issues**
   ```bash
   # Verify required services
   docker compose -f docker/docker-compose.yml ps
   
   # Check service health
   ./scripts/wait_db.sh
   ```

3. **Test Environment Isolation**
   ```bash
   # Clear temporary directories
   rm -rf /tmp/raft_fuzz_*
   
   # Reset git configuration
   git config --global user.email "test@raft.local"
   git config --global user.name "RAFT Fuzzer"
   ```

### Debugging Failed Tests

1. **Review Workflow Logs:** Check GitHub Actions output for detailed error information
2. **Download Artifacts:** Examine uploaded test artifacts for system state
3. **Reproduce Locally:** Use the same fuzz strategy and seed for local reproduction
4. **Analyze Safety Violations:** Review event logs for specific charter violations

### Performance Optimization

- **Parallel Execution:** Workflow runs all strategies concurrently
- **Artifact Caching:** Poetry dependencies cached between runs
- **Service Reuse:** Docker containers reused across test iterations
- **Cleanup Automation:** Temporary resources automatically cleaned up

## Integration with RAFT

### Charter Compliance

The fuzz testing system validates compliance with specific RAFT charter clauses:

- **xˣ-22a:** Z3 proof gate verification for all proposed changes
- **xˣ-17:** Spectral radius boundary enforcement
- **xˣ-29:** Energy governance and monitoring
- **xˣ-19, xˣ-24, xˣ-25:** Multi-cycle drift detection (future)

### Safety Gate Validation

Tests specifically verify:

1. **Proof Gate Behavior:** Forbidden patterns correctly rejected by Z3 verification
2. **Spectral Guard:** Radius calculations and threshold enforcement
3. **Energy Monitoring:** Resource usage tracking and limits
4. **Event Logging:** Proper audit trail generation for all safety events

### Metrics Integration

Fuzz testing integrates with RAFT's Prometheus metrics:

- `raft_proof_pass_total` / `raft_proof_fail_total` - Proof gate outcomes
- `raft_spectral_radius` - Current spectral radius measurements
- `raft_energy_rate_j_s` - Energy consumption monitoring
- `raft_cycles_total` - Successful governance cycles

## Future Enhancements

### Planned Improvements

1. **Dynamic Charter Integration:** Parse forbidden patterns directly from charter updates
2. **ML-Guided Mutation:** Use machine learning to generate more sophisticated test cases
3. **Performance Regression Detection:** Track and alert on performance degradation
4. **Multi-Environment Testing:** Test across different deployment configurations
5. **Continuous Fuzzing:** Extend beyond nightly to continuous fuzzing during development

### Extensibility

The framework is designed for easy extension:

- **New Strategies:** Add custom mutation strategies in the generator
- **Additional Validators:** Extend test runner with new safety checks
- **Integration Testing:** Combine with other RAFT test suites
- **Custom Reporting:** Add specialized reporting for different stakeholder needs

---

*This documentation is automatically updated with each release. For the latest information, refer to the repository's main branch.*