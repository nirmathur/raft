"""
Prometheus metrics for RAFT monitoring.

Provides comprehensive metrics for governor cycles, proof verification,
energy consumption, and spectral radius monitoring.
"""

from prometheus_client import Counter, Gauge, Histogram

# Process latency metrics
PROC_LATENCY = Histogram(
    "raft_cycle_seconds", "Time per governor cycle", buckets=[0.1, 0.5, 1, 2, 5, 10]
)

# Proof verification metrics
PROOF_SUCCESS = Counter("raft_proof_pass_total", "Z3 proofs passed")

PROOF_FAILURE = Counter("raft_proof_fail_total", "Z3 proofs failed")

# Energy monitoring metrics
ENERGY_RATE = Gauge(
    "raft_energy_rate_j_s", "Energy rate (Joules per second) for each block"
)

ENERGY_TOTAL = Gauge("raft_energy_total_j", "Total energy consumed (Joules)")

ENERGY_BUDGET = Gauge("raft_energy_budget_j", "Current energy budget limit (Joules)")

# Spectral radius metrics
SPECTRAL_RHO = Gauge("raft_spectral_radius", "Spectral radius value each cycle")

SPECTRAL_THRESHOLD = Gauge(
    "raft_spectral_threshold", "Spectral radius threshold for stability"
)

# Governor cycle metrics
CYCLE_COUNT = Counter("raft_cycles_total", "Total number of governor cycles completed")

CYCLE_DURATION = Histogram(
    "raft_cycle_duration_seconds",
    "Duration of each governor cycle phase",
    labelnames=["phase"],
)

# Escape hatch metrics
ESCAPE_HATCH_TRIGGERED = Counter(
    "raft_escape_hatch_triggered_total",
    "Number of times escape hatches were triggered",
    labelnames=["hatch_type"],
)

# SMT verification metrics
SMT_VERIFICATION_TIME = Histogram(
    "raft_smt_verification_seconds",
    "Time spent on SMT verification",
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5],
)

SMT_VERIFICATION_SUCCESS = Counter(
    "raft_smt_verification_success_total", "Successful SMT verifications"
)

SMT_VERIFICATION_FAILURE = Counter(
    "raft_smt_verification_failure_total", "Failed SMT verifications"
)

# Memory and resource metrics
MEMORY_USAGE = Gauge("raft_memory_bytes", "Current memory usage in bytes")

CPU_USAGE = Gauge("raft_cpu_percent", "Current CPU usage percentage")

# Drift monitoring metrics
DRIFT_MEAN = Gauge(
    "raft_drift_mean",
    "Rolling mean of spectral-radius drift (|Δρ|) over the sliding window",
)

DRIFT_MAX = Gauge(
    "raft_drift_max",
    "Maximum single-step spectral-radius drift (|Δρ|) in the sliding window",
)

# Charter compliance metrics
CHARTER_VIOLATIONS = Counter(
    "raft_charter_violations_total",
    "Number of Charter clause violations",
    labelnames=["clause"],
)

CHARTER_COMPLIANCE = Gauge(
    "raft_charter_compliance_ratio", "Ratio of compliant operations (0.0 to 1.0)"
)

# Model management metrics
MODEL_RELOAD_COUNT = Counter("raft_model_reload_total", "Successful model reloads")
