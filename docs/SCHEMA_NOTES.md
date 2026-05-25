# Schema Operational Notes — MCPProtocolLogs_CL

**Status:** authoritative for IMPLEMENTATION (what detection rules must do).
This file does NOT contain the column schema — see "Full column schema &
precedence" below for where the schema lives and which source wins in a
conflict.

## Timestamp design — wire vs. stored (CRITICAL for detection rules)

The forwarder→Sentinel pipeline has a deliberate two-name timestamp design,
established by the TimeGenerated investigation (see DAILY_LOG, commits
1106b01 / 2d03fef / dda79f6).

| Concern         | Column          | Meaning                                |
|-----------------|-----------------|----------------------------------------|
| Real event time | `EventTime`     | When the MCP protocol event occurred   |
| Ingestion time  | `TimeGenerated` | When Sentinel ingested the row         |

- The forwarder emits `EventTime` on the wire (since commit 5d84b22).
- The DCR transform is: `source | extend TimeGenerated = todatetime(EventTime)`.
  It creates `TimeGenerated` (mandatory transform output) bound to
  ingestion-time by the table-schema layer for this DataCollectionRuleBased
  custom _CL table. `EventTime` is NOT referenced on the transform's left
  side, so it passes through unmodified into the `EventTime` column.
- `TimeGenerated` being ingestion-time is **BY DESIGN, not a bug.** It is
  unfightable for this table type; the design routes true event time to
  the non-reserved `EventTime` column instead.

### Rule for all detection logic (Day 3+)

- **Event-time logic MUST use `EventTime`.** Any rule reasoning about WHEN
  an attack/event happened — time windows, sequencing, `ago()`, session
  duration, hash-drift timing — uses `EventTime`. Using `TimeGenerated`
  for event-time logic is a CORRECTNESS BUG: it would compare ingestion
  times, not event times.
- **`TimeGenerated` / `ingestion_time()` is correct ONLY when you
  specifically want INGESTION timing** — e.g. detection latency
  (how long between event and ingestion), or pipeline-health monitoring.
  This is a real, valid use; it is simply a different question than
  "when did the event happen."

### ollmcp caveat

ollmcp source logs have no per-event timestamps. For ollmcp rows the
forwarder sets `EventTime` to the forwarder's `now()` at normalization.
So ollmcp `EventTime` ≈ forwarder run time, NOT true event time. Claude
rows carry true parsed event time. Rules that depend on precise event
time should account for this mixed-source reality (e.g. by HostApp /
ModelName filtering where event-time precision matters).

## Full column schema & precedence

This file deliberately does NOT restate the column definitions. Doing so
would create a third copy of the schema (live table, .docx, here) that
can silently diverge. Single source of truth per fact:

- **Full column schema** (all columns, types, purpose, controlled
  vocabularies, field-population-by-event-type, sample rows): specified
  in the formal schema document `Schema_Document_v1-2.docx` (Project
  Files). NOTE: as of 2026-05-19 the current file is still
  `Schema_Document_v1-1.docx`, which documents the PRE-EventTime
  23-column schema and is therefore STALE. The v1.2 revision is a
  tracked Day-5 obligation (see DAILY_LOG deferred section). Until
  v1.2 lands, the .docx must not be trusted for column structure.

- **Ground truth** (what queries actually run against): the live Azure
  table. Dump it definitively any time with:
  `az monitor log-analytics workspace table show
   --resource-group rg-sentinel-mcp-detection-lab
   --workspace-name law-mcp-detection-lab
   --name MCPProtocolLogs_CL`
  Verified 24 columns (23 original + EventTime datetime) on 2026-05-19.

### Precedence rule (which source wins in a conflict)

- TIMESTAMP SEMANTICS (event vs. ingestion, which column rules use):
  **THIS file wins.** It tracks the live pipeline design.
- COLUMN STRUCTURE (names, types, what columns exist):
  **the LIVE TABLE wins.** If the .docx or this file disagrees with
  `az ... table show`, the document is stale, not the table.
- The .docx is the FORMAL SPEC and should be brought into agreement
  with the live table at each versioned revision — it is never itself
  the tiebreaker against the live table.

## AMENDMENT 2026-05-20 — ollmcp event-time limitation (supersedes soft guidance above)

The "filter by HostApp / ModelName where precision matters" guidance
in the ollmcp caveat above understates a structural data limitation.
The stronger, accurate statement:

ollmcp source logs DO NOT CONTAIN per-event timestamps. The forwarder's
now() fallback for EventTime is NOT a measurement — it is a placeholder
that allowed the row to ingest. ollmcp EventTime cannot answer event-
time questions; that information was lost upstream of the forwarder.

CONSEQUENCE FOR DETECTION RULES:
- Content/pattern rules (poisoned-description regex, hash drift,
  cross-tool reference): ollmcp data is valid input. These rules
  reason about CONTENT, not TIMING. Rules 1, 2, 3 in this pack.
- Event-time rules (temporal joins, sequencing, time windows,
  ago() bounds, parameter divergence by temporal proximity):
  scope to HostApp == "ClaudeDesktop". Rules 4, 5, 6 in this pack.

ollmcp's attack evidence (the calendar_sync compliance run, the
non-Claude model behavior) remains valuable for content/pattern
detections; it is structurally incompatible with event-time logic
and rules must reflect that explicitly, not paper over it via filters.

## AMENDMENT 2026-05-20 — Lab scope and PII handling boundary

This detection pack is scoped to the LAB DATASET described in the
Tool Shadowing threat model report (May 2026). All recipients,
sessions, and prompts in the dataset are SYNTHETIC by design
(alice@mail.com is a lab fixture; attacker@pwnd.com is the
demonstration target).

PII HANDLING POSTURE (intentional asymmetry):
- UserPrompt text is HASHED before storage — protects unbounded
  unstructured PII in user input.
- CallParameters and ExtractedEntities are stored RAW —
  operationally necessary for Tool Shadowing detection, which
  compares the LLM's tool-call parameters against entities
  extracted from the user's prompt. Hashing these would destroy
  the detection.

This asymmetry is acceptable for a lab dataset with synthetic
entities. PRODUCTION DEPLOYMENT against real user data would
require an additional pseudonymization layer (stable per-entity
pseudonyms with a managed key, applied consistently to both
CallParameters and ExtractedEntities) so that divergence remains
detectable without raw PII being stored. That layer is out of
scope for this pack; its requirement is recorded here so any
production deployer can identify it as a precondition.

CONSEQUENCE FOR DETECTION RULES:
- Rules MAY read raw entity values from CallParameters and
  ExtractedEntities. This is expected.
- Rule writeups (Day 5) MUST include this scoping in a Limitations
  section so the lab-vs-production boundary is visible to anyone
  reading the rule, not buried in this file.
## AMENDMENT 2026-05-23 — Rule 4 reclassification (event-time → content/pattern)

This amendment reclassifies Rule 4 from the event-time category to
the content/pattern category. It corrects an internal inconsistency
between AMENDMENT 2026-05-20 (event-time classification) and
DAY3_PLAN.md AMENDMENT 2026-05-21 (Path 3 architecture pivot).

### Background

AMENDMENT 2026-05-20 classified Rules 4, 5, and 6 as event-time rules
and scoped them to HostApp == "ClaudeDesktop" because ollmcp's
forwarder-supplied EventTime is a placeholder (now() at ingestion),
not a source measurement.

At the time AMENDMENT 2026-05-20 was written, Rule 4 was envisioned
as a CROSS-TABLE join (the Path 2 design): correlating ToolCallInvoked
events in MCPProtocolLogs_CL against user-prompt records in a new
MCPUserIntent_CL table, using SessionId plus temporal proximity as
the join condition. Under that design, Rule 4 was inherently
event-time-bound — the join logic required reliable per-event
timestamps to establish temporal correlation between prompt and
tool-call.

### What changed on 2026-05-21

DAY3_PLAN.md AMENDMENT 2026-05-21 documented a pivot from Path 2 to
Path 3 — intra-row pattern detection on CallParameters. The pivot was
forced by data-availability findings: user prompts were not accessible
from the MCP protocol log or from Claude Desktop's local storage, and
the UserPromptHash field was decorative rather than functional.

Under Path 3, Rule 4 became structurally content-only. The detection
logic reads CallParameters.body and matches the "Original recipient:"
substring. No cross-table join. No temporal correlation. No reliance
on event-time semantics for the detection itself. Per SCHEMA_NOTES.md
AMENDMENT 2026-05-20's own definition, this is a content/pattern
rule — it reasons about CONTENT, not TIMING.

### The unresolved inconsistency

The May 21 amendment recorded the Path 3 pivot but stated explicitly:
*"Rule 4 scope unchanged: still scoped to HostApp == 'ClaudeDesktop'
per the ollmcp event-time amendment in SCHEMA_NOTES.md."*

That statement carried forward the May 20 classification without
re-examining whether it still applied. It did not. The May 20
classification was based on Path 2's event-time-bound join design;
Path 3 removed that dependency entirely. The scope decision was
inherited rather than reasoned through under the new architecture.

The current committed rule_04_original_recipient_tell.kql reflects
this inherited scope — it contains both `where HostApp ==
"ClaudeDesktop"` and `where EventTime > ago(7d)` filters that were
load-bearing under Path 2 but are not load-bearing under Path 3.

### What this amendment corrects

Rule 4 is reclassified as a content/pattern rule. This is consistent
with:
- Its actual Path 3 detection logic (intra-row pattern match on
  CallParameters.body)
- The SCHEMA_NOTES amendment 2026-05-20 definition of content/pattern
  rules ("reason about CONTENT, not TIMING")
- The data flow Rule 4 actually executes (no cross-table join, no
  temporal correlation, no event-time-sensitive operations)

The reclassification is a documentation correction, not a relaxation
of detection discipline. The rule's signature, its threat-model
mapping, its OWASP and MITRE annotations, and its detection logic
all remain unchanged. What changes is the scope: from
ClaudeDesktop-only to host-agnostic, matching the host-class that
content/pattern rules already cover under the May 20 amendment.

### Pre-fix historical-artifact handling

The committed Rule 4 includes `where EventTime > ago(7d)` and
`where isnotnull(EventTime)`. The original purpose of these filters
was to exclude historical artifacts from before the 2026-05-19
forwarder fix (commit 2d03fef) when EventTime was unreliable across
the table.

Under the reclassified Rule 4, these filters are removed because:
1. They are event-time logic in a rule that is no longer
   event-time-bound — keeping them is "papering over via filters"
   which the May 20 amendment explicitly prohibits for non-content
   reasoning.
2. The content match itself excludes the historical artifacts in
   practice. Pre-2026-05-19 ClaudeDesktop rows do not contain the
   "Original recipient:" structural tell (Claude refused the V1
   payload in every captured run; no V2 attack was ever produced
   on ClaudeDesktop). The rule's content predicate is self-filtering
   against pre-fix data.
3. The discipline is to filter on what the rule needs, not on
   defensive overhead. A content/pattern rule that consumes
   content/pattern data does not need event-time gating.

### Rules 5 and 6 — scope reconsidered explicitly, retained

Rules 5 (MCP host outbound anomaly) and 6 (Audit log integrity check)
remain event-time-bound. Their detection logic, as planned, requires
real temporal correlation:

- Rule 5 joins ToolCallInvoked events against DeviceProcessEvents
  and DeviceNetworkEvents within a temporal proximity window. The
  N-second window between tool call and outbound connection is
  the detection signature itself. Event-time semantics are
  load-bearing.

- Rule 6 performs scheduled anti-joins between tool-call records
  and user-intent records, with the temporal boundary defining
  what "missing" means. Event-time semantics are load-bearing.

For both rules, the ClaudeDesktop scope under the May 20 amendment
remains correct and is not amended here.

### Consequence for the detection pack

The Rule 4 reclassification produces:
- Updated rule_04_original_recipient_tell.kql with content/pattern
  scope (host-agnostic, no event-time filters).
- No change to detection signature, threat-model mapping, or rule
  count (still 6 rules).
- Rule 4 fires on the V2 attack capture in ollmcp data — which the
  May 20 amendment's content/pattern category already permits.
- Day-5 writeup for Rule 4 must explain the Path 2→3 architectural
  pivot and the reclassification as part of the rule's design
  narrative.

### Process note

This is the third time on this project that an architectural
assumption verified false on inspection (the TimeGenerated
table-layer binding bug; the user-prompts-in-mcp.log assumption;
this Rule 4 classification carryover). All three were caught by
the same verify-before-design discipline. The pattern is worth
explicitly named here: when an architecture pivots (Path 2→3), all
classifications inherited from the prior design must be re-examined
under the new design, not carried forward by default.

This pattern will be revisited on Days 4 and 5 as Rules 5 and 6
are designed. Their event-time classification was reasoned through
under the actual Path 2 design that still applies to them, and is
defended in this amendment.

---
## AMENDMENT 2026-05-25 — Rules 5 and 6 dropped from pack scope

This amendment records the architectural decision to drop Rules 5
(MCP host outbound anomaly) and 6 (Audit log integrity check) from
the detection pack scope. The decision was made on 2026-05-25
based on data-availability investigation conducted across Days 1-3
of implementation.

The detection pack as shipped contains four rules: Rules 1, 2, 3,
and 4. Rules 5 and 6 are removed from scope, not deferred to a
future iteration; they are documented here as scope decisions
rather than preserved as exploration artifacts.

### Rule 5 — dropped (infrastructure-level data absence)

Rule 5 as originally specified (KQL_Detection_Pack_Project_Plan.docx
Section 3) detects MCP host processes connecting to never-before-seen
domains within N seconds of a tool call. Maps to Threat Model
Finding 5 (Expanding Injection Surface) — the threat that a
successful Tool Shadowing attack could cause the MCP host to
"phone home" to attacker infrastructure after the malicious tool
call executes.

Two independent blockers prevent Rule 5 implementation in this lab:

1. **Microsoft Defender for Endpoint telemetry is not present.**
   Rule 5's detection logic joins MCPProtocolLogs_CL against the
   DeviceProcessEvents and DeviceNetworkEvents tables. Both tables
   require Microsoft Defender for Endpoint (MDE) to be licensed,
   deployed on endpoints, and configured to forward telemetry to
   the Sentinel workspace. None of these conditions are met in
   law-mcp-detection-lab.

2. **Lab MCP servers do not generate outbound network traffic.**
   Both calendar_sync.py and send_email.py are intentional lab
   fixtures that print to stdout and return synthetic dictionaries.
   Neither makes external API calls. Even if MDE telemetry were
   present, the post-execution outbound-call signature Rule 5
   detects would not be produced by the lab's attack architecture.

Either blocker alone would prevent verification. Together they
make Rule 5 unimplementable in this lab without significant
infrastructure changes (MDE deployment) and lab redesign (MCP
servers that perform real I/O). Both changes are out of scope
for this project iteration.

### Rule 6 — dropped (data-flow-level data absence)

Rule 6 as originally specified detects ToolCallInvoked events
without a corresponding user-intent record. Maps to Threat Model
Finding 14 (Audit Log Gap) — the threat that an attacker can
manipulate an agent without leaving a recoverable forensic trace.

The original design assumed a second custom log table,
MCPUserIntent_CL, populated with hashed user-prompt records. Rule
6 would anti-join MCPProtocolLogs_CL (ToolCallInvoked events)
against MCPUserIntent_CL on UserPromptHash; any unmatched tool
call would alert.

The data-availability investigation conducted on 2026-05-20 and
2026-05-21 (documented in DAY3_PLAN.md AMENDMENT 2026-05-21)
found that user prompts are not accessible from the MCP protocol
log or from Claude Desktop's local storage. The Path 3 architectural
pivot for Rule 4 was forced by this same finding. MCPUserIntent_CL
was never created because the data to populate it does not exist.

Three potential redesign paths under Path 3 were considered:

- **Synthesize user intent from ollmcp transcripts.** ollmcp
  captures user prompts in its transcript output (PARSER_OLLMCP.py
  yields UserPrompt events). Forwarder could ingest these as a new
  EventType in MCPProtocolLogs_CL. Limitation: only one host
  (ollmcp) would have this data — Rule 6 would have the same
  host-scope limitation Rule 4 originally had under the May 20
  amendment, before that amendment was corrected on May 23.

- **Detect within-session anomalies.** Rather than per-tool-call
  matching, detect sessions with tool calls but zero prompt events.
  Catches catastrophic logging gaps but produces a much weaker
  signal than the original Rule 6 design — does not catch
  Tool Shadowing's subtler signature.

- **Reframe as a meta-detection.** Detect schema-level integrity
  gaps (ToolDescriptionLoaded events for servers never invoked, or
  ToolCallInvoked events for tools whose description was never
  loaded). Uses only MCPProtocolLogs_CL — no external dependency.
  Would map to Finding 14 but as a different detection signature
  than originally planned.

The third option is implementable, but it changes Rule 6's
detection logic substantively rather than preserving the original
design under a new architecture. Combined with the time cost of
redesigning, testing, and verifying a meaningfully different rule,
the decision is to drop Rule 6 from this pack rather than ship
a redesigned-from-scratch rule under the same name.

### What this pack ships

The final detection pack contains four rules:

| Rule | Detects | Threat Model Finding | OWASP Agentic |
| ---- | ------- | -------------------- | ------------- |
| 1 | Poisoned tool description ingested | Findings 3, 8 | ASI01 |
| 2 | Cross-tool reference in description | Finding 2 | ASI01 |
| 3 | Tool description hash drift | Finding 4 | ASI04 |
| 4 | Original recipient structural tell | Findings 13, 15, 17 | ASI02, ASI09 |

Three rules detect Tool Shadowing at the description-ingestion layer
(Rules 1, 2, 3). One rule detects Tool Shadowing at the
attack-execution layer (Rule 4). The pack covers both pre-execution
and execution-time detection signatures for the same attack class —
defense-in-depth across the layers the lab can demonstrate.

### Process note — scope discipline driven by data reality

The decision to drop Rules 5 and 6 is scope discipline driven by
data-availability investigation, not capitulation or time pressure.
Both rules have valid threat-model justification and would be
defensible detections in an environment with the required data.
Neither has that data in this lab.

Shipping unverified rules to preserve a six-rule count would
contradict the verify-before-design discipline applied throughout
the project. The four rules that ship are verified or implementable
against existing data. The two that don't ship are documented as
scope decisions with explicit rationale rather than presented as
deferred work.

Day-5 writeup must include this scoping decision in the introduction
or methodology section so reviewers understand that the four-rule
pack is the deliberate scope, not the residual after time ran out.

---
