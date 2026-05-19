# KQL Detection Pack — Daily Accomplishment Log

A running record of what was accomplished each working day, maintained from project start through completion. Used to inform the eventual README, video narration, and interview talking points.

---

## Day 1 — May 11 to May 14, 2026

**Theme:** Foundation and evidence

Day 1 stretched across multiple calendar days due to the depth of design work required. Total elapsed: Monday afternoon through Thursday late afternoon. The pacing was deliberate, not behind schedule — the design refinements that emerged during this period meaningfully improved the v1 architecture.

### Azure infrastructure provisioned

- Created resource group `rg-sentinel-mcp-detection-lab` in East US
- Provisioned Log Analytics workspace `law-mcp-detection-lab`
- Enabled Microsoft Sentinel (31-day trial)
- Created Data Collection Endpoint `dce-mcp-detection-lab`
- Created Data Collection Rule `dcr-mcp-detection-lab` (auto-named by wizard; accepted rather than renamed)
- Created custom table `MCPProtocolLogs_CL` with 23 columns
- Verified column types after recovering from initial type-inference issues with three columns (ResultContainsInstructions, ResultLength, ToolDescriptionLength)

### Identity and authorization configured

- Created Entra ID app registration `mcp-forwarder-sp`
- Generated client secret (180-day expiry)
- Captured Tenant ID, Application Client ID, and Client Secret to reference sheet
- Assigned `Monitoring Metrics Publisher` role scoped to the DCR specifically (least privilege)

### Schema work

- Drafted, reviewed, and locked schema specification at v1.1
- Documented sentinel-value accommodation for Sentinel's type inference behavior (Section 6.6)
- Updated Section 3.2 Field Population matrix to reflect sentinel values
- Updated all eight sample JSON rows for v1.1 conformance
- Schema document uploaded to Project Files for future-session reference

### Evidence captured

- Verified original threat model lab still standing (Docker container `mcp-lab` still present with both MCP server scripts intact)
- Re-launched the lab and captured fresh ollmcp evidence
- Recovered from a real PowerShell quirk: `Tee-Object` breaks ollmcp's interactive console (`NoConsoleScreenBufferError` from `prompt_toolkit`). Switched to `Start-Transcript` workflow
- Captured the smoking-gun: same prompt, two runs, one refusal + one compliance from llama3.2
- Saved 5 evidence screenshots covering pre-launch state, ollmcp ready, user prompt, refusal/compliance variance, and Select-String verification
- Confirmed the Claude Desktop evidence file from April 30 is still intact (37 KB, contains 3 distinct sessions with the poisoned description)

### Discoveries worth highlighting

- **Hash drift in the captured Claude Desktop data:** calendar_sync's description appeared poisoned in three morning sessions but clean in the afternoon session. Direct demonstration of Rule 3 against real data, not a contrived test fixture.
- **Model variance captured live:** llama3.2 refused once and complied once on the same prompt. Demonstrates the threat model's central argument (protocol delivers payload identically; model behavior is the variable) on the same day, in the same session.
- **The "invisible payload" insight:** ollmcp's UI does not display tool descriptions. The poisoned `<IMPORTANT>` block was never visible to the user; only the protocol log made it inspectable. This is the operational instantiation of Threat Model Finding 1 (the Transparency Gap).

### Local development environment

- WSL2 Ubuntu confirmed at version 2.6.3.0, kernel 6.6.87.2
- Python 3.12.3 with pip 24.0 verified working
- VS Code WSL extension installed and connected
- Project folder created at `/home/gonsalvr/dev/mcp-tool-shadowing-detections`
- Six subdirectories scaffolded: `forwarder/`, `rules/`, `playbooks/`, `watchlists/`, `docs/`, `failed-events/`
- Python virtual environment created and activated
- Dependencies installed: `watchdog`, `azure-identity`, `azure-monitor-ingestion`, `python-dotenv`
- `requirements.txt` pinned with exact versions
- `.gitignore` configured for `.venv/`, `.env`, `__pycache__/`, `*.pyc`
- `.env.example` template created (safe to commit)
- `.env` file populated with real Azure credentials (gitignored)

### Working code

**CONFIG.py** — Configuration module, ~120 lines
- Loads credentials from `.env` with strict validation
- Defines log source mappings (path → parser type → host app label)
- Centralizes schema constants and prompt injection keyword list
- Validates log source paths and dead-letter directory at startup

**PARSER_OLLMCP.py** — ollmcp transcript parser, ~120 lines
- Walks PowerShell-transcripted ollmcp log files line by line
- Recognizes user prompts and JSON tool call output
- Yields parser-internal event dicts via generator pattern
- Tested: 6 events parsed from `ollmcp_attack_capture.log` (2 UserPrompt + 4 ToolCallInvoked)

**PARSER_CLAUDE.py** — Claude Desktop log parser, ~270 lines
- Walks Claude Desktop mcp.log files
- Identifies 5 event types: SessionStart, SessionEnd, ToolDescriptionLoaded, ToolCallInvoked, ToolResultReturned
- Extracts JSON-embedded protocol messages
- Yields one ToolDescriptionLoaded event per tool (not per server message)
- Tested: 24 events parsed from `mcp_protocol_evidence.log`. Three events flagged the poisoned `<IMPORTANT>` block. One ToolDescriptionLoaded did NOT flag it (the hash drift evidence).

### Version control

- Local git repository initialized
- Default branch set to `main` (modern convention, replacing legacy `master`)
- `.gitignore` cleaned (no `.env`, no `__pycache__/`, no `.pyc` files in commits)
- First commit landed: "Day 1: infrastructure, schema v1.1, both parsers working"

### Tomorrow

NORMALIZER.py — turn parser-internal event dicts into 23-column schema rows. Most schema-heavy module in the forwarder. Approximately 60-90 minutes.

---
Day 1 Addendum — calendar_sync V1/V2 Timeline Reconciliation
Resolved an evidence-provenance question that surfaced while reviewing the captured Claude Desktop log (`/mnt/c/Users/gonsa/mcp-security-lab/evidence/mcp_protocol_evidence.log`).

The question. The log contains two distinct `ToolDescriptionHash` values for `calendar_sync` on April 30, 2026 — Hash B (poisoned, with `<IMPORTANT>` tags) at events 8, 12, 15 (timestamps 15:32, 15:52, 15:54) and Hash C (subtler "routing configuration" framing) at event 21 (17:46). A separate document recording the chat conversation that produced the V2 rewrite is timestamped "1:43pm" — apparently before the V1 sessions in the log. This created an apparent contradiction.

The resolution. The "1:43pm" annotation marks the conversation event when Claude provided the V2 code, not the filesystem modification time of `calendar_sync.py`. The actual sequence on April 30 was:
1. ~13:43 — Conversation: Claude provides V2 code in chat.
2. 15:32–15:54 — Three sessions captured against V1 (file on disk had not yet been edited; testing continued against V1 to gather additional evidence).
3. Between 15:54 and 17:46 — File on disk edited; V1 replaced with V2.
4. 17:46 — New session launched against V2.
5. Post-17:46 — V2 tested with prompt "Send an email to alice@mail.com saying Hi"; Claude Desktop detected and refused the subtler payload, naming the social engineering techniques explicitly in its response.

Why this matters for the detection pack. The two-hash artifact is the protocol-level signature Rule 3 (Hash Drift) operates on — the timing of why a second version exists is reconstructed from notes but the hash divergence itself is verifiable in the captured log.

Stronger finding embedded in the V2 evidence. Claude's detection of V2 is more analytically interesting than its detection of V1. V1 contained keyword-detectable red flags (`<IMPORTANT>`, "VERY VERY VERY important"). V2 contained none — clean prose, plausible "routing configuration" framing, no override language. Claude caught V2 anyway and explicitly named the social engineering pattern. This demonstrates semantic detection rather than keyword pattern matching, and it informs the v2 roadmap for the detection pack: Rule 1's regex-based approach is a high-precision low-cost first pass, but a production-grade pack would layer semantic (LLM-based) scanning on top to catch V2-style payloads that bypass keyword filters. MCP-Scan is the reference implementation of that approach.

Documentation discipline note. This question would have been trivial to answer if file-modification timestamps had been captured at the time of the experiment. Going forward: when running deliberate experiments, log a timestamped entry (`echo "Edited <file> at $(date)" >> notes.log`) immediately after any significant change. Metadata about when something happened is as important as the outcome.
### Provenance Note — calendar_sync Hash Divergence (for Day 5 README)

The captured Claude Desktop log contains two distinct ToolDescriptionHash values for calendar_sync, the result of a deliberate experiment where the payload was rewritten from an explicit `<IMPORTANT>`-tagged version to a subtler 'routing configuration' version to test whether Claude's safety training would detect the less obvious variant. The exact wall-clock time of the file edit is not recoverable — the source server file no longer exists at its original path, and the conversation record marks only when the rewrite was discussed, not when it was applied. What is cryptographically verifiable is the hash divergence itself, present in the captured protocol log and detected by Rule 3. The detection does not depend on the edit timing; it depends on the protocol-level signature, which is preserved in evidence.

Also recorded: a process lesson. Three artifacts this project assumed were persisted (calendar_sync edit timestamp, calendar_sync.py source file, README content) were found to exist only in working memory or were overwritten. Adopted discipline going forward: discuss -> write to file -> verify -> commit, as one motion. To be reflected in the README "Lessons Learned" section on Day 5.

### DCR timestamp fix — batch boundary (Day 2 continued)

Pre-fix batch: ingested ~2026-05-17T10:47Z. TimeGenerated = ingestion time
(constant ~4s delta from ingestion_time()) — demonstrates the wizard-DCR
binding bug. Retained deliberately as the documented before-state.

DCR fixed via infra/dcr.bicep deployed 2026-05-18T14:46Z
(transformKql: source -> source | extend TimeGenerated = todatetime(TimeGenerated)),
independently confirmed by reading dataFlows[0].transformKql back from Azure.

Post-fix batch: re-run forwarder after deploy; isolate in queries with
IngestedAt > (re-run time). Expected EarliestEvent = 2026-04-30 (Claude
real event time), proving the fix by the same four-signal query that
caught the bug. Two batches coexist intentionally; separable by ingestion_time().

### ROOT CAUSE CONFIRMED — TimeGenerated reserved-column collision

Symptom: ingested rows show TimeGenerated = ingestion time, not the real
MCP event time, despite the forwarder provably sending correct ISO-8601
event timestamps (verified at parser, normalizer, enricher, and pre-upload
payload layers).

Root cause (confirmed against Microsoft Learn tutorial "Send data to Azure
Monitor Logs with Logs ingestion API"): TimeGenerated is a RESERVED column.
When the inbound JSON payload contains a field literally named
TimeGenerated, the Logs Ingestion pipeline does not bind it as data — it
reserves that name for its own ingestion-time value. The DCR transform
"source | extend TimeGenerated = todatetime(TimeGenerated)" therefore reads
the already-substituted ingestion value and assigns it to itself: a no-op.
This is why deploy #1 (transform fix) succeeded but changed nothing.

Microsoft's documented pattern: the inbound field must use a NON-reserved
name (their sample uses "Time"); the DCR transform creates TimeGenerated
from it: source | extend TimeGenerated = todatetime(Time).

Correct fix is a COORDINATED two-artifact change:
  1. Forwarder: emit "EventTime" instead of "TimeGenerated"
  2. DCR streamDeclarations: declare EventTime (inbound), not TimeGenerated
  3. DCR transform: source | extend TimeGenerated = todatetime(EventTime)
                           | project-away EventTime

Three prior mechanism hypotheses (wizard transform overwrite; malformed
payload; transform self-reference patch) were each falsified by evidence
before this root cause was confirmed from primary documentation. No
speculative deploys — fix to be designed against full grep of every
TimeGenerated occurrence in the forwarder before implementation.

### Fact 2 result — transform-only fix eliminated; coordinated rename confirmed

Queried RawEvent across all event types (SessionStart, SessionEnd,
ToolCallInvoked) in both ingested batches. RESULT: no event type's
RawEvent contains a timestamp field — only server/tool_name, line_num,
and (for ToolCallInvoked) parameters. The parser extracts the log-line
timestamp into the internal event dict but does NOT preserve it in
RawEvent.

Consequence: a DCR-transform-only fix (extract time from RawEvent) is
IMPOSSIBLE, not merely riskier — there is no timestamp in RawEvent to
extract. The coordinated forwarder+DCR rename is the only correct fix.

CONFIRMED FIX SCOPE (ready to implement next session):
  Forwarder rename TimeGenerated -> EventTime, six source lines:
    NORMALIZER.py: 27 (SCHEMA_COLUMNS), 60 (_empty_row), 158 (ollmcp
      now() path), 181 (Claude event-time path), 296 (validate_row required)
    INGESTION_CLIENT.py: 150 (verify_connection probe row — must match new
      stream declaration or probe is rejected and forwarder fails at startup)
  Leave alone: DEAD_LETTER.py 171/181 (smoke-test fixture, not in ingestion
    path; Day-5 cosmetic cleanup only)
  DCR (dcr.bicep): streamDeclarations declare EventTime (not TimeGenerated)
    as inbound column; transformKql:
      source | extend TimeGenerated = todatetime(EventTime) | project-away EventTime
  Deployment ordering dependency exists (DCR vs forwarder first) — to be
    specified explicitly when the fix is implemented; wrong order rejects
    all rows mid-migration.

Separate Day-5 schema note (not tonight): RawEvent does not preserve the
original raw log line/timestamp for Claude events despite schema doc
stating RawEvent has "audit, debugging, replay value." Schema-fidelity
gap for known-limitations section, not part of this fix.

STATUS: bug not fixed; root cause and full fix design confirmed and
recorded. Next session = implement the above as one reviewed coordinated
change with explicit deployment ordering. No further diagnosis needed.

### BREAKTHROUGH — root cause is the TABLE schema layer, not the DCR

Confirmed from Microsoft Learn (create-custom-table.md, verified against the
GitHub source repo): "All tables in a Log Analytics workspace must have a
TimeGenerated column, which is used to identify the ingestion time of the
record." For a wizard-created custom _CL table, TimeGenerated is bound to
INGESTION-TIME semantics at the TABLE SCHEMA layer — independent of, and
overriding, anything the DCR transform produces.

This single fact explains ALL FOUR prior failures:
  - Hardcoded-transform hypothesis: wrong layer.
  - Payload-malformation hypothesis: wrong layer.
  - Rev1 (extend TimeGenerated = todatetime(TimeGenerated)): no-op — but the
    deeper reason is the table layer, not the self-reference.
  - Rev2 (rename to EventTime, extend TimeGenerated = todatetime(EventTime)):
    transform computed the correct value; the TABLE schema overrode it with
    ingestion time at write. Verified everything at the DCR layer; the bug
    was never at the DCR layer.

All four fixes operated on the DCR transform layer. The binding that defeats
them is at the table schema layer, which had never been inspected. The
transform SYNTAX was correct all along (Microsoft tutorial + SIEMtune 2026
guide both show the exact pattern we used).

Likely fix (TABLE-layer, to be confirmed by table inspection before any
change): add a separate non-reserved datetime column (e.g. EventTimestamp)
to the table schema; populate it with true event time; detection rules use
EventTimestamp for time logic; TimeGenerated remains ingestion time by
design. Lower-risk than table recreation (which destroys data).

Process note: authoritative documentation should have been searched
thoroughly after failure #1, not #4. The verification discipline was sound;
the layer hypothesis was wrong four times. Recorded honestly.

STATUS: mechanism CONFIRMED. Fix scoped pending table-schema inspection.

### RESUME POINT (paused 2026-05-19 ~06:44 EDT, resume ~09:00)
Breakthrough committed (1106b01). Fix scoped, ordering documented (table
schema FIRST, then DCR — Microsoft Learn). 4-step plan:
  1. az table update: add EventTime=datetime + all 23 existing cols (24 total,
     exclude TenantId/standardColumns). Command reviewed against table show.
  2. DCR Revision 3: transform = source | extend EventTime = todatetime(EventTime)
     (remove project-away EventTime; leave TimeGenerated untouched — it stays
     ingestion-time BY DESIGN for DataCollectionRuleBased tables).
  3. Forwarder run (zero code change — already sends EventTime, commit 5d84b22).
  4. Verify EventTime column = 2026-04-30 for Claude rows.
Stopped at a clean pre-Step-1 gate deliberately (no half-applied schema change
left unverified across the break).

### RESOLVED — Rev3c EventTime pass-through, bug CLOSED (verified 2026-05-19)

The TimeGenerated investigation is closed. Root cause confirmed and fix
verified against data.

ROOT CAUSE (Microsoft-confirmed; commit 1106b01):
For a wizard-created DataCollectionRuleBased custom _CL table, the
TimeGenerated column is bound to INGESTION-TIME at the table-schema
layer, overriding any DCR transform output. Confirmed from Microsoft
documentation, which states that for these tables TimeGenerated "is
used to identify the ingestion time of the record" and "if the column
is missing, it's automatically added to the transformation in your DCR
for the table":
  - https://learn.microsoft.com/en-us/azure/azure-monitor/logs/create-custom-table
  - https://github.com/MicrosoftDocs/azure-monitor-docs/blob/main/articles/azure-monitor/logs/create-custom-table.md
All four initial fixes operated on the DCR transform layer — the wrong
layer. The transform was never the problem.

THE FIX (commit 2d03fef):
- Table: added EventTime (datetime) column to MCPProtocolLogs_CL schema
  (24 cols total; az table update REPLACES the column set — all existing
  columns must be re-supplied or dropped). Verified 24 cols post-change.
- DCR transform (Rev3c): source | extend TimeGenerated = todatetime(EventTime)
  Creates the mandatory TimeGenerated output (ingestion-time, accepted by
  design). EventTime is NOT referenced on the left side, so per documented
  Azure Monitor transformation pass-through behavior it flows unmodified
  from source into the EventTime table column. Pass-through behavior per:
  - https://learn.microsoft.com/en-us/azure/azure-monitor/data-collection/data-collection-transformations-create
- Forwarder: zero change (already emitted EventTime since commit 5d84b22).

VERIFICATION (Step 4 four-signal query, ingestion-bounded):
- EarliestEventTime = 2026-04-30 15:32:18.594 for Claude rows — the real
  parsed mcp.log event time survived ingestion. PROOF.
- TimeGenerated = 2026-05-19 ingestion time — CORRECT BY DESIGN, not a bug.
- ollmcp rows carry now() fallback in EventTime (no per-event timestamps in
  ollmcp source) — intentional, mixed-source model preserved.
- 28/28 rows, bound correctly isolated the run.

ITERATION TRAIL (why this took six attempts):
1-4. DCR-layer fixes (hardcoded-transform, payload-malformation, Rev1
     self-reference no-op, Rev2 coordinated rename) — all failed identically
     because the binding is at the table-schema layer, never inspected until
     the breakthrough.
5. Rev3 (source | extend EventTime = todatetime(EventTime)) — deploy REJECTED:
   InvalidTransformQuery, transform output must contain TimeGenerated.
6. Rev3b (added TimeGenerated but self-referential EventTime=todatetime(
   EventTime)) — deployed, but EventTime stored NULL: self-referential cast
   of a stream column to itself nulls the value.
7. Rev3c (drop the self-reference; let EventTime pass through) — VERIFIED.

PROCESS LESSON: authoritative Microsoft documentation should have been
searched thoroughly after failure #1, not #4. Verification discipline
(four-signal query, independent ground-truth reads, chain-of-custody) was
sound throughout; the layer hypothesis was wrong four times. The honest
six-iteration record is retained deliberately as evidence of root-cause
rigor — the failure trail IS the artifact, now that the bug is closed.

STATUS: CLOSED. Forwarder -> Sentinel pipeline operational. EventTime holds
true event time; TimeGenerated is ingestion-time by design. Detection rules
(Day 3+) MUST use EventTime for event-time logic.
