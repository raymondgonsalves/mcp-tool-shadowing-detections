# Day 3 Plan — Behavioral & Integrity Detection Rules

Day 3 is the hardest day of the 5-day sprint. Three of the six rules
land today: one is genuinely novel (Rule 4 — parameter divergence),
two are joins across telemetry sources (Rules 5 and 6). Days 1-2
built the infrastructure; Day 3 produces the first detections that
make this a "pack," not just a pipeline. Budget: ~6 hours.

## Rules to deliver today

### Rule 4 — Parameter divergence (the toughest)

Detects: high-privilege tool calls whose parameters don't match
entities present in the user's original prompt. Maps to Threat Model
Findings 13, 15, 17 (Tool Shadowing attack signature).

Approach (high level — NOT writing KQL tonight):
- Requires a SECOND custom log table: MCPUserIntent_CL (user prompts
  + extracted entities, hash-keyed for privacy).
- Rule joins MCPProtocolLogs_CL (ToolCallInvoked events) against
  MCPUserIntent_CL on UserPromptHash + temporal proximity.
- Alerts when ToolCallInvoked parameters (e.g., recipient email)
  do not appear in the user-intent entities for the same prompt.
- This is the most novel rule in the pack — the one that demonstrates
  protocol-layer detection of a model-layer attack.

### Rule 5 — MCP host outbound anomaly

Detects: Claude Desktop / Cursor / ollmcp processes hitting
never-before-seen domains within N seconds of a tool call. Maps to
Threat Model Finding 5 (Expanding Injection Surface).

Approach: Join MCPProtocolLogs_CL (ToolCallInvoked) against
DeviceProcessEvents + DeviceNetworkEvents, filtered to MCP host
process names, with temporal correlation window.

### Rule 6 — Audit log integrity check

Detects: ToolCallInvoked events without a corresponding user-intent
record. Maps to Threat Model Finding 14 (Audit Log Gap).

Approach: Scheduled hunt — anti-join of MCPProtocolLogs_CL against
MCPUserIntent_CL. Any tool call lacking a matching user prompt is
either a missing log or evidence of upstream manipulation.

## Suggested order (most-difficult-first)

1. **Rule 4** (hardest, novel, requires the new MCPUserIntent_CL table):
   ~3 hours. Schema design FIRST, deploy second table, then the rule.
2. **Rule 5**: ~1.5 hours. Existing telemetry, just needs the join right.
3. **Rule 6**: ~1.5 hours. Once Rule 4's MCPUserIntent_CL exists, this
   is mostly an anti-join + scheduled-hunt query.

Front-loading Rule 4 means you do the hardest work fresh. If something
slips, it slips into Rule 6, which is the easiest of the three.

## Definition of done for each rule

- Working KQL in `/rules/<rule>.kql`
- One-page writeup in `/docs/detections/<rule>.md` (hypothesis, data
  sources, detection logic, MITRE mapping, known FPs, triage steps,
  response hook — per the project plan, ~40 min/writeup, do not rush)
- Test execution against the Day-1 captured data, screenshot of the
  fired incident
- Mapped to its Threat Model Finding in the traceability matrix
  stub (matrix completes Day 5)

## Standing rules for Day 3 (read before writing any KQL)

1. **EVERY time-based clause uses `EventTime`. Never `TimeGenerated`.**
   This is the entire reason `SCHEMA_NOTES.md` exists. If a rule needs
   ingestion timing (e.g., detection latency analysis), that is the
   ONE legitimate `TimeGenerated` use; document it inline.

2. **ollmcp rows have `EventTime` = forwarder `now()` fallback.** Rules
   needing precise event time should filter to `HostApp == 'Claude'`
   or otherwise account for the mixed-source reality.

3. **Detection-as-code.** Rules go in `/rules` as version-controlled
   files. Each rule = one commit. No "fix later" inline TODOs;
   they become permanent.

4. **The four-signal verification discipline applies to detection
   rules too.** When testing a rule, don't accept "it fired" —
   confirm count, time range, expected entities, AND that it
   doesn't fire on negative cases.

## What NOT to do on Day 3

- Don't write all three rules then commit at the end. One rule,
  one commit, one writeup.
- Don't skip the writeup to save time. Writeups are what hiring
  managers actually read — they're the senior-vs-junior signal.
- Don't expand scope to a 7th rule because there's time. Six is
  the planned set; seven looks scattered.
- Don't start the traceability matrix today — that's Day 5 by
  design (you'd build a stub here and finish then).

## First moves when you sit down

1. `az account show -o table` (auth check)
2. `git log --oneline -10` (read recent commits)
3. `cat docs/SCHEMA_NOTES.md` (governing document)
4. Read THIS file end-to-end
5. Begin Rule 4 with the MCPUserIntent_CL schema design — NOT KQL.
   Schema before query, every time.
