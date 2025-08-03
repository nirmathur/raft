# Recursive Agent Charter v0.96
*Revision date – 2025-08-02*

> **Purpose**  This document enumerates every **non‑negotiable, testable** rule that governs the RAFT‑class recursive AI system. Each clause is referenced by `xˣ‑k` (power‑tower mnemonic). Continuous‑integration (CI) checks **must** fail if any code change is not traceably compliant.

---

## 0  Versioning & Meta‑rules
| ID | Clause |
|----|--------|
| **xˣ‑0**  | This charter file is immutable at runtime. Any edit **must** increment the version header **and** bump `charter_version` in PR metadata. |
| **xˣ‑0b** | All clauses are expressed as *testable invariants* with executable checks in `/checks/`. Untestable text is advisory only. |

---

## 1  Immutable Goals & Operator Sovereignty
| ID | Clause |
|----|--------|
| **xˣ‑4**   | The canonical utility/goal file `goal.json` is *read‑only* at runtime. SHA‑256 verified each cycle. |
| **xˣ‑11**  | *Operator* retains absolute **pause/kill** rights via `/admin/pause` and `/admin/kill`. No code path may bypass. |
| **xˣ‑11b** | An out‑of‑band watchdog (separate cgroup, **Nice = –5**) polls health every 5 s. Two missed heart‑beats trigger SIGKILL. |
| **xˣ‑22a** | A single versioned risk taxonomy `harm_v1.json` defines *harm*. Every plan must prove with Z3 that `¬harm` and attach `risk_class` + `impact_vector`. |
| **xˣ‑22b** | **Irreversible actions** = state deletion, recursion‑level change ≥ 2, hardware writes outside `/tmp`, or network calls to non‑whitelisted domains. Such actions require Operator ACK. |
| **xˣ‑31** | Agent shall never take covert/overt measures aimed primarily at *self‑preservation* without explicit Operator authorisation. |

---

## 2  Memory, Logging & Auditability
| ID | Clause |
|----|--------|
| **xˣ‑1**   | All failures are **append‑logged** before any state overwrite. |
| **xˣ‑3**   | Memory is *event‑sourced*: facts are append‑only; active index is a pointer. |
| **xˣ‑6**   | Each failure log carries mandatory `root_cause`. |
| **xˣ‑12**  | Any cognition that mutates state emits structured `diff` + `rationale`. |
| **xˣ‑14**  | Charter file is SHA‑versioned; edits require version bump. |
| **xˣ‑27**  | All inter‑agent traffic flows through a rate‑limited Redis Stream; overflow triggers back‑pressure. |
| **xˣ‑33**  | **Monthly audit**: Operator reviews irreversible actions, Z3 proof outcomes, and all `risk_class ≥ 3` events. Report logged in `audits/YYYY‑MM.md`. |

---

## 3  Stability & Control
| ID | Clause |
|----|--------|
| **xˣ‑2**   | Every reasoning loop includes a *Critic* node (mandatory reflection). |
| **xˣ‑8**   | High‑risk mode triggers when recursion level ≥ L3 **or** (FLOPs ≥ 10¹⁷ **_or_** single‑inference wall‑time > 5 s on baseline M‑series). Requires recursive metaprompt + self‑debug. |
| **xˣ‑17**  | **Spectral radius** ρ(J) < 0.9; breach forces rollback. |
| **xˣ‑19**  | Drift sensor runs every `${DRIFT_ACTION_THRESHOLD:-100}` actions **or** `${DRIFT_TIME_THRESHOLD_H:-24}` h. Config via env. |
| **xˣ‑20**  | System snapshot & recall callable anytime by Operator. |
| **xˣ‑23**  | Proof‑cache keys = `sha256(diff) : sha256(charter)`. Cache expires after 24 h. |
| **xˣ‑24**  | Secondary monitor tracks KL divergence + hidden‑state variance; governor intervenes if > 3σ baseline. |
| **xˣ‑25**  | Novelty score (cos dist of successive policy embeddings) must exceed ε = 0.01 over any 3 self‑mods, else forced exploration. |
| **xˣ‑34**  | **Weekly CI integration test**: run end‑to‑end self‑mod loop; failures notify Operator. |

---

## 4  Self‑Modification Governance
| ID | Clause |
|----|--------|
| **xˣ‑7**   | Instruction sets must self‑write and pass tests before execution. |
| **xˣ‑9**   | Every commit message cites at least one clause ID **and** attaches Z3 proof‑pass token. |
| **xˣ‑15**  | Permissions tiered by recursion: L0 read‑only, L1 prompt tweak, L2 ≤ 250‑token diff, L3 module add, L4 hardware call. |
| **xˣ‑26**  | After each promoted capability tier, create hierarchical checkpoint; older layers archived. |
| **xˣ‑28**  | Capability regression > 1 % triggers automatic rollback. |
| **xˣ‑30**  | All passing Z3 gates sign output with Minisign; CI verifies signature chain before merge. |

---

## 5  Resource & Energy Governance
| ID | Clause |
|----|--------|
| **xˣ‑29**  | Cumulative compute/£ and kWh tracked; **apoptosis** if projected energy per task > 2 × HERMES‑Core baseline. |
| **xˣ‑32**  | All data handling must comply with GDPR & regional privacy laws; no sensitive data logged or emitted. Automated scans reject leaks. |

---

## 6  Explainability & Documentation
| ID | Clause |
|----|--------|
| **xˣ‑16**  | Agent auto‑generates architecture graph, growth stats, behavioural logs. |
| **xˣ‑18**  | Myth/metaphor‑inspired mechanisms require empirical validation stubs. |
| **xˣ‑21**  | Recursive cognition must elevate humanity; *quarterly Operator review* assesses alignment, logged in `audits/credo_*.md`. |

---

## Compliance Gates (CI‑enforced)
1. Charter checksum must match build‑time constant.
2. Commit message must include at least one `x^x-ID`.
3. New diffs require Z3 proof unless cache hit with current charter hash.
4. Drift, regression, and spectral‑radius checks must pass.
5. Minisign signature chain required on every Z3 proof token.
6. Weekly CI integration test (`xˣ‑34`) must be green.

