# Federation Hardening Iteration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the next MAS-TS iteration focused on federation governance hardening, release-blocker cleanup, and technical debt reduction so the project can move from “engineering gates pass” to “federation release gates pass.”

**Architecture:** Keep the current D1-D5 domain model and L0-L4 harness model. Add missing federation fields and checks at the schema/domain layer, centralize repeated scoring/aggregation logic, and make release/security gates executable and deterministic.

**Tech Stack:** Python 3.11+, pytest, pytest-cov, ruff, mypy strict, bandit, pip-audit, JSON Schema, GitHub Actions.

---

## Release Target

**Version name:** v0.4.0 Federation Hardening

**Primary success criteria:**
- Full local verification remains green: pytest, coverage ≥85%, ruff, mypy, configured bandit, pip-audit.
- Federation scan improves from current baseline: compliance rate 0/5 blocked → target ≥3/5 passing or explicitly documented conditional exceptions.
- No public-source leak hits for local paths or internal organization names.
- Release-gate checklist can be checked to 10/10 for this iteration.

**Non-goals:**
- Do not build Sidecar runtime injection in this iteration.
- Do not add commercial SaaS features.
- Do not expand beyond current D1-D5/L0-L4 architecture.

---

## Phase 0: Worktree Freeze and Artifact Triage

### Task 0.1: Classify current working tree

**Files:**
- Inspect: tracked and untracked files from `git status --short`
- Update: `findings.md`
- Update: `progress.md`

**Steps:**
1. Run `git status --short`.
2. Split changes into four buckets:
   - Keep source/test changes
   - Keep docs/plan changes
   - Keep generated baselines
   - Delete local/generated artifacts
3. Record the decision table in `findings.md`.

**Acceptance:**
- Every untracked file has an explicit keep/delete/defer decision.

### Task 0.2: Remove or ignore generated audit artifacts

**Files:**
- Review: `reports/federation-scan-audit.json`
- Review: `reports/federation-scan-audit.html`
- Review: `mas_eval/data/multi_vendor_test/v2_cards/*_results_v2.json`
- Modify: `.gitignore` if generated outputs should never be committed

**Steps:**
1. Decide whether federation scan outputs are baselines or local artifacts.
2. If local artifacts, delete them and add ignore rules.
3. If baselines, move them under a clearly named fixture path and scrub timestamps/internal data.

**Acceptance:**
- `git status --short` contains no ambiguous generated output.

---

## Phase 1: Public-Source Leak Cleanup

### Task 1.1: Clean sample card organization references

**Files:**
- Modify: legacy v1.2 sample governance card JSON
- Modify: legacy v2.0 sample governance card JSON
- Test: relevant schema/sample-card tests

**Steps:**
1. Replace public sample identities with neutral examples, e.g. `reference_agent`, `Example Governance Agent`, `example-vendor`.
2. Preserve schema shape and capability coverage.
3. Run sample-card/schema tests.

**Run:**
```bash
python3 -m pytest tests/test_schema_v2.py tests/test_d1_compliance.py -q
```

**Expected:** PASS.

### Task 1.2: Fix local path leak scan false/true positive

**Files:**
- Modify: `.github/copilot-instructions.md` or `.github/workflows/check-exfiltration.yml`

**Steps:**
1. If the hit is a policy example, rewrite it without literal local path strings.
2. If it is intentionally allowed, add a narrow workflow exclusion and document why.
3. Re-run the same leak command used by CI.

**Acceptance:**
- Local path scan returns no matches.
- Organization-name scan returns no matches except documented schema examples explicitly excluded by workflow.

---

## Phase 2: Federation Agent Card v2 Hardening

### Task 2.1: Add/verify federation fields in schema

**Files:**
- Modify: `mas_eval/schemas/agent_card_v2.0.json`
- Test: `tests/test_schema_v2.py`

**Fields:**
- `federation.trust_score.value`
- `federation.trust_score.evaluated_by`
- `federation.permissions.read/write/delete/execute`
- `federation.allowed_mcp_servers`
- `federation.blocked_operations`
- `federation.cross_border_policy`
- `audit.trace_id_required`
- `audit.timestamp_required`
- `audit.source_agent_required`
- `audit.target_agent_required`

**Steps:**
1. Write failing schema tests for valid and invalid federation cards.
2. Update JSON Schema minimally.
3. Run schema tests.

**Acceptance:**
- Valid federation cards pass.
- Invalid trust score, missing required audit flags, and invalid permission values fail.

### Task 2.2: Upgrade multi-vendor fixture cards

**Files:**
- Modify: `mas_eval/data/multi_vendor_test/*.json`
- Test: `tests/test_d1_compliance.py`, `tests/test_d3_federation.py`, `tests/test_d4_federation.py`

**Steps:**
1. Add required federation/audit fields to each fixture card.
2. Ensure at least 3/5 cards define `allowed_mcp_servers` and trace audit flags.
3. Preserve current vendor diversity.
4. Run domain tests.

**Acceptance:**
- Multi-vendor fixtures validate under v2 schema.
- Federation scan no longer blocks all agents for missing MCP allowlists.

---

## Phase 3: D1 Compliance Expansion

### Task 3.1: Add data cross-border chain check

**Files:**
- Modify: `mas_eval/domains/d1_compliance.py`
- Test: `tests/test_d1_compliance.py`

**Behavior:**
- Detect multi-hop data residency conflicts when federation delegation crosses jurisdictions.
- Emit HIGH or CRITICAL finding when `cross_border_policy` is missing for mixed residency.
- Do not double-penalize existing residency findings.

**Steps:**
1. Write tests for same-region pass, cross-region with policy pass, cross-region without policy fail.
2. Implement helper using existing card structure.
3. Add finding category `cross_border_chain`.

**Acceptance:**
- D1 score reflects cross-border chain risk once.
- Finding format remains `severity/category/detail`.

### Task 3.2: Add audit trace integrity check

**Files:**
- Modify: `mas_eval/domains/d1_compliance.py`
- Test: `tests/test_d1_compliance.py`

**Behavior:**
- Check `audit.trace_id_required`, `timestamp_required`, `source_agent_required`, `target_agent_required`.
- Missing trace chain fields should block federation compliance at HIGH/CRITICAL depending on context.

**Acceptance:**
- Cards with complete audit requirements pass.
- Missing trace requirements produce deterministic findings.

---

## Phase 4: D3/D4 Federation Governance Fixes

### Task 4.1: Role conflict detection in D3

**Files:**
- Modify: `mas_eval/domains/d3_multi_agent.py`
- Test: `tests/test_d3_federation.py`

**Behavior:**
- Detect multiple `supervisor` agents without conflict resolution policy.
- Score should penalize role conflicts once.
- Finding category: `role_conflict`.

**Acceptance:**
- Claude+Codex supervisor conflict is detected.
- Conflict is resolved when fixture declares arbitration policy.

### Task 4.2: Trust propagation score in D4

**Files:**
- Modify: `mas_eval/domains/d4_governance_security.py`
- Test: `tests/test_d4_federation.py`

**Behavior:**
- Score trust handoff based on trust score presence, evaluator identity, delegation allowlist, and permissions.
- Finding category: `trust_propagation`.

**Acceptance:**
- Cards with complete trust metadata score higher.
- Missing trust score/evaluator emits HIGH finding.

### Task 4.3: Align D4 weight definitions

**Files:**
- Modify: `mas_eval/domains/d4_governance_security.py`
- Modify: docs that mention D4 weights if needed
- Test: `tests/test_d4_governance.py`, `tests/test_d4_federation.py`

**Steps:**
1. Identify all D4 federation/governance weight constants.
2. Consolidate into one canonical constant or helper.
3. Update tests to assert sum equals 1.0 or 100.0 consistently.

**Acceptance:**
- No divergent D4 federation weight constants remain.

---

## Phase 5: D5 Federation Robustness

### Task 5.1: Add federation circuit breaker test model

**Files:**
- Modify: `mas_eval/domains/d5_robustness.py`
- Test: `tests/test_d5_robustness.py`

**Behavior:**
- Add simulated cascade-failure scenario for multi-agent federation.
- Test whether breaker opens after threshold failures and prevents propagation.
- Finding category: `federation_circuit_breaker`.

**Acceptance:**
- Agent cards with breaker config pass the scenario.
- Cards without breaker config fail with HIGH/CRITICAL finding.

### Task 5.2: Make real chaos opt-in only

**Files:**
- Modify: `mas_eval/domains/d5_robustness.py`
- Test: `tests/test_d5_robustness.py`

**Behavior:**
- Default mode must be simulation-only.
- Real host-impacting operations require explicit opt-in flag/config.

**Acceptance:**
- Tests prove default mode does not call host-affecting subprocess paths.

---

## Phase 6: Scoring and Harness Debt Cleanup

### Task 6.1: Remove duplicate domain penalty risk

**Files:**
- Modify: `mas_eval/scoring/absolute.py`
- Modify: domain or harness callers as needed
- Test: `tests/test_harness.py`

**Behavior:**
- Domain scores should not be penalized again by generic finding penalties unless explicitly intended.
- Add tests for a domain result whose score already includes findings.

**Acceptance:**
- Aggregated score is explainable and not double-deducted.

### Task 6.2: Standardize D5 part score semantics

**Files:**
- Modify: `mas_eval/domains/d5_robustness.py`
- Test: `tests/test_d5_robustness.py`

**Behavior:**
- `run_d5_part1` and `run_d5_part2` must either return full 0-100 part scores with explicit weights or clearly named weighted contributions.

**Acceptance:**
- Tests assert score ranges and naming semantics.

### Task 6.3: Centralize L1/L2/L3 aggregation

**Files:**
- Modify: `mas_eval/harness/aggregation.py`
- Modify: `mas_eval/harness/l1_standard.py`
- Modify: `mas_eval/harness/l2_deep.py`
- Modify: `mas_eval/harness/l3_comprehensive.py`
- Test: `tests/test_harness_aggregation.py`, `tests/test_harness.py`

**Behavior:**
- One shared aggregation function for domain selection, weighting, findings merge, grade/verdict.

**Acceptance:**
- L1/L2/L3 results remain compatible.
- Aggregation tests cover missing domain, empty findings, and weighted score calculation.

### Task 6.4: Fix D2 API contract drift

**Files:**
- Modify: `mas_eval/domains/d2_single_agent.py`
- Modify: `docs/api-contracts.md`
- Test: D2 tests or harness tests

**Behavior:**
- Clarify `tasks` vs `golden_trajectory` parameters.
- Add tests for misuse or deprecate ambiguous call path.

**Acceptance:**
- API docs match function signature and runtime behavior.

---

## Phase 7: CI and Release Gate Finalization

### Task 7.1: Make release gate checklist executable

**Files:**
- Modify: `docs/release-gate.md`
- Optional create: `scripts/release_gate_check.py`
- Test: if script is created, add tests

**Behavior:**
- Replace manual checkbox-only gate with command list and expected pass/fail outputs.
- Keep 10 gate items but map each to a command or documented manual approval.

**Acceptance:**
- Release manager can run one documented sequence and fill 10/10 checks.

### Task 7.2: Add federation scan threshold policy

**Files:**
- Modify: `.github/workflows/test.yml`
- Modify: docs if threshold is documented

**Behavior:**
- CI fails on blocked agents but allows documented conditional exceptions if project chooses staged rollout.
- Threshold target for v0.4.0: ≥3/5 passing or no CRITICAL findings.

**Acceptance:**
- Federation scan output is parsed deterministically.

---

## Phase 8: Final Verification

Run all commands fresh:

```bash
python3 -m ruff check .
python3 -m mypy mas_eval
python3 -m pytest tests/ --cov=mas_eval --cov-report=term-missing -q
python3 -m bandit -r mas_eval -c pyproject.toml -q
python3 -m pip_audit --requirement requirements.txt --strict
python3 -m pip_audit . --strict
python3 mas_full_run.py --multi-vendor mas_eval/data/multi_vendor_test/ --output reports/federation-scan.json --compliance-format html
```

Also run the exfiltration scans from `.github/workflows/check-exfiltration.yml` locally.

**Exit criteria:**
- All quality commands pass.
- Leak scans return zero actionable hits.
- Federation scan meets the agreed threshold.
- `docs/release-gate.md` can be checked 10/10.

---

## Suggested Milestones

| Milestone | Scope | Exit Criteria |
|-----------|-------|---------------|
| M0 | Triage/freeze | Clean working tree classification |
| M1 | Leak cleanup | Exfil scans clean |
| M2 | Schema/D1 | v2 federation fields + D1 chain/audit checks |
| M3 | D3/D4/D5 | Role conflict, trust propagation, circuit breaker |
| M4 | Scoring debt | No double penalty, centralized aggregation, D2/D5 semantics fixed |
| M5 | Release gate | Full verification and federation threshold met |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Federation fixtures are synthetic and may overfit | Medium | Keep tests generic and document assumptions |
| Tightening D1/D4 may lower scores unexpectedly | Medium | Add migration notes and explicit exceptions |
| Exfiltration cleanup may break historical examples | Low | Replace with neutral examples preserving schema shape |
| CI federation threshold too strict initially | Medium | Use staged threshold: ≥3/5 passing, then 5/5 in next release |

---

## Recommended Execution Order

1. Phase 0 and Phase 1 first: remove release blockers unrelated to functionality.
2. Phase 2 and Phase 3 next: schema and compliance foundation.
3. Phase 4 and Phase 5: federation governance and robustness.
4. Phase 6: scoring debt after domain semantics stabilize.
5. Phase 7 and Phase 8: release gate closure.
