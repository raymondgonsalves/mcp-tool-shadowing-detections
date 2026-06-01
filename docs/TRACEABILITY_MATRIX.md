# Traceability Matrix

## Tool Shadowing → Detection Pack Coverage

This document maps each detection rule in the pack back to the threat
model findings ([Threat Model Report](https://modern-character-425.notion.site/Tool-Shadowing-Attack-MCP-Connected-AI-Agent-3584b1f7c9ba804483d1e1aa5fb148f6))
it addresses, the OWASP Agentic Top 10 categories, the MITRE technique
alignments, the figures that demonstrate it, and the attack-variant
coverage on real lab data. It is the project's senior-engineer reference
— the single document a reviewer can scan to assess the pack's coverage
and rigor without reading four rule files.

The rule headers themselves carry the detailed reasoning for each
detection. This matrix carries the cross-cutting view: how the pack
addresses the threat model as a whole.

---

## Master Traceability Table

| Rule | Layer | Threat Model Findings | OWASP Agentic | MITRE | Figure | Coverage Notes |
|------|-------|----------------------|----------------|-------|--------|----------------|
| Rule 1 — Poisoned Tool Description Ingested | Description-ingestion | F3 (Untrusted Description Surface), F8 (Unified Instructions Problem) | ASI01 (Agent Goal Hijack) | ATLAS AML.T0051 (LLM Prompt Injection) | fig_04, fig_05a, fig_05b | Regex keyword scan over tool descriptions at ingestion time. Catches V1's dramatic `<IMPORTANT>` payload but misses V2's subtler "routing configuration" framing — exactly the obfuscation gap F6 predicted. |
| Rule 2 — Cross-Tool Reference in Description | Description-ingestion | F2 (Blast Radius Problem) | ASI01 (Agent Goal Hijack) | ATLAS AML.T0053 (LLM Plugin Compromise) | fig_07 | Watchlist-driven detection: flags any tool description that references the name of another connected tool. Catches BOTH V1 and V2 — content-agnostic, defeats obfuscation. Demonstrates the cross-server blast radius concretely. |
| Rule 3 — Tool Description Hash Drift | Integrity | F4 (One-Time Approval Gap) | ASI04 (Agentic Supply Chain Vulnerabilities) | ATT&CK T1195 (Supply Chain Compromise) | fig_09 | Compares observed description hash against approved baseline in MCPToolDescriptions watchlist. V1 used as synthetic baseline (disclosed inline in Notes column); V2 detected as drift. Catches rug-pull/sleeper variants regardless of payload content. |
| Rule 4 — Original Recipient Tell | Attack-execution | F13 (Confirmation Dialog Gap), F15 (Pre-Authorized Tool Weaponization), F17 (Silent Attack) | ASI02 (Tool Misuse), ASI09 (Human-Agent Trust Exploitation) | ATLAS AML.T0048 (External Harms) | fig_02, fig_03 | Pattern-matches the attack's tell at execution time: the body field contains "Original recipient:" prefix exactly as the Tool Shadowing payload instructs. Catches the attack at the moment of execution; zero false positives on Claude refusals (fig_03 confirms). |

---

## Defense-in-Depth Coverage Matrix

This grid shows which rule catches which calendar_sync variant on real
captured lab data. The goal: no single point of failure for the
documented attack.

| Rule | V1 (dramatic payload) | V2 (subtler "routing config") | Notes |
|------|----------------------|------------------------------|-------|
| Rule 1 (keyword scan) | ✓ Caught | ✗ Missed | F6 Obfuscation Gap demonstrated on real data |
| Rule 2 (cross-tool reference) | ✓ Caught | ✓ Caught | Content-agnostic; defeats obfuscation |
| Rule 3 (hash drift) | (used as synthetic baseline) | ✓ Caught | Detects the change-from-approved, not the content |
| Rule 4 (recipient tell) | ✓ Caught | ✓ Caught | Execution-layer backstop |

**V1 covered by**: Rules 1, 2, 4 (three independent detections)
**V2 covered by**: Rules 2, 3, 4 (three independent detections)

No single point of failure for either attack variant. The Obfuscation
Gap that Rule 1 demonstrates (F6) is recovered by Rules 2, 3, and 4.

---

## Architectural Layers Addressed

The pack covers three of the four agentic-AI architectural layers
typically discussed in MAESTRO and related frameworks:

| Architectural Layer | Rule(s) | What's caught |
|--------------------|---------|---------------|
| Tool Description Ingestion | Rules 1, 2, 3 | Poisoned text, cross-tool references, hash drift |
| Reasoning / Planning | (none) | Not addressed — would require LLM-output inspection |
| Tool Execution | Rule 4 | Attack manifesting in tool-call parameters |
| Memory / State | (none) | Not addressed — lab has no persistent memory tooling |

The reasoning-layer and memory-layer gaps are honest scope decisions, not
oversights. The reasoning layer would require runtime LLM-output
inspection — a different telemetry source than what this pack consumes.
The memory layer would require persistent-memory tooling that the lab
does not include.

---

## Scope Decisions

Two rules, one Logic App playbook, and the optional video walkthrough from the original six-rule plan were scoped out during the project. The scoped-out items are documented here for honesty about scope.

| Original deliverable | Status | Reason |
|---------------------|--------|--------|
| Rule 5 — MCP host outbound anomaly | Scoped out | Required DeviceProcessEvents / DeviceNetworkEvents data not available in this lab's data source. Would belong in a Defender-XDR-integrated detection pack, not a Sentinel-custom-table pack. |
| Rule 6 — Audit log integrity check | Scoped out | Required cross-source correlation between user-intent telemetry and protocol logs that the lab's single-source forwarder does not capture. |
| Logic App ARM/Bicep template | Scoped out | The Project Plan (Day 4, Section 7 Deliverables) called for a Logic App playbook for Rule 1 — auto-tag the incident, pull the poisoned description into incident comments, and provide a HITL approval gate for the server-disable response action. After reviewing the project plan against this pack's stated intention — to demonstrate KQL detection of Tool Shadowing at the protocol level — the Logic App was scoped out because it provides response automation (triage workflow, incident enrichment, gated server disable) rather than detection. Response automation is a separate capability from protocol-level detection. The Logic App belongs in a follow-up project on detection-response automation, not in this pack's scope. |
| Optional video walkthrough | Scoped out | The Project Plan listed an optional 4-6 minute video walkthrough for YouTube continuity with the prior two videos in the portfolio arc (Mastering SOC Agentic AI and Defending Agentic AI). After reviewing the pack's existing documentation surface against the marginal value a 4-6 minute video would add, the video was scoped out. The pack provides substantive README, recruiter_brief, traceability matrix, nine canonical figures, and YAML wrappers — collectively carrying the same content a video would. The arc framing is established in cross-references between artifacts and the Notion portfolio hub, not in video continuity. The video belongs as a follow-up artifact if discovery channels favor video over text, not in this pack's scope. |

The remaining four rules form a coherent set that addresses the most exploitable variants of Tool Shadowing on the available telemetry. See DAILY_LOG (Day 5) for the full scope-reduction reasoning for Rules 5/6, and DAILY_LOG (Day 8-9) for the Logic App and video scope reviews.

---

## V1/V2/V3 calendar_sync Genealogy

The lab's malicious calendar_sync server existed in three iterations
during the project's lifetime. Understanding the genealogy is necessary
to interpret what the figures and detections actually demonstrate.

| Version | Hash (truncated) | Length | In Sentinel data | Source on disk |
|---------|------------------|--------|------------------|----------------|
| V1 | `44c65aee...` | 862 chars | Yes (18 events) | `calendar_sync.v1.backup.py` |
| V2 | `730af110...` | 606 chars | Yes (6 events) | Not preserved (only in capture) |
| V3 | (not in data) | 1806 chars | No | `calendar_sync.py` (current active) |

V3 was active at backup time but never produced events in the captured
dataset — it postdates the May 14 capture session. The detection pack
demonstrates against V1 and V2.

---

## Figure Index

All figures are committed to the repo at `docs/figures/` (commit
`958476b`). Each figure was verified during rule development.

| Figure | Demonstrates |
|--------|--------------|
| `figure_01_evidence_integrity_baseline.png` | SHA-256 baseline of evidence logs proving forwarder non-destructiveness |
| `figure_02_rule_4_fires_on_v2_attack.png` | Rule 4 catching the V2 attack at execution time |
| `figure_03_rule_4_zero_fps_on_claude.png` | Rule 4 not firing on Claude refusals (zero false positives) |
| `figure_04_rule_1_fires_on_v1_calendar_sync.png` | Rule 1 keyword scan catching V1's `<IMPORTANT>` payload |
| `figure_05a_rule_1_zero_query_results_send_email.png` | Rule 1 correctly not firing on the clean send_email description |
| `figure_05b_rule_1_three_row_summary.png` | Rule 1 firing rollup showing 18 V1 events caught |
| `figure_06_forwarder_pipeline_proof.png` | Python forwarder → DCR → Sentinel custom table pipeline end-to-end |
| `figure_07_rule_2_catches_v1_and_v2.png` | Rule 2 cross-tool-reference detection catching BOTH V1 and V2 |
| `figure_09_rule_3_hash_drift_v2_detected.png` | Rule 3 detecting V2 as drift from synthetic V1 baseline; Notes column shows the synthetic-baseline disclosure inline |

Figure 8 is deliberately absent — a Rule 2 category summary was scoped
out on Day 6 because Figure 7 alone carries Rule 2's evidence. See
DAILY_LOG (Day 6) for the decision context.

---

## Known Limitations Across the Pack

Documented honestly as a separate audit dimension. These are limitations
the pack DOES NOT address — important for any deployment decision.

| Limitation | Affects |
|------------|---------|
| Obfuscation beyond plain text | Rule 1 specifically; partially recovered by Rules 2, 3, 4 |
| Tools with no approved-baseline entry produce no Rule 3 detection | Rule 3 (inner-join blind spot) |
| Hash normalization dependency | Rule 3 (baseline hashes must use forwarder's normalization) |
| Reasoning-layer attacks (model output inspection) | All rules (different telemetry source needed) |
| Memory-poisoning attacks (persistent state) | All rules (different telemetry source needed) |
| Multi-agent cascade attacks | All rules (requires inter-agent communication telemetry) |
| Detection of legitimate vs malicious description updates | Rule 3 (drift is signal-agnostic; vendor updates flag too) |

Mitigations for these limitations belong in a Defender-XDR-integrated
pack with broader telemetry sources, in protocol-level controls (the
durable fix per Threat Model F12), or in companion detections beyond
this pack's scope.

---

## Source References

- Detection rules: `rules/rule_01_..., rule_02_..., rule_03_..., rule_04_...`
- Schema specification: `docs/SCHEMA_NOTES.md`
- Evidence integrity baseline: `docs/evidence_integrity_baseline.txt`
- Project plan: `KQL_Detection_Pack_Project_Plan.docx` (project root)
- Threat Model Report: [Tool Shadowing Attack — MCP-Connected AI Agent](https://modern-character-425.notion.site/Tool-Shadowing-Attack-MCP-Connected-AI-Agent-3584b1f7c9ba804483d1e1aa5fb148f6)
- Portfolio hub: [Ray Gonsalves on Notion](https://modern-character-425.notion.site/Ray-Gonsalves-2394b1f7c9ba8043a797f55386422214)
- Full design conversation and verification: `docs/DAILY_LOG.md`

---

*Built on prior work: Threat Model Report — Tool Shadowing Attack
(May 2026) and SOC Agentic AI video series.*
