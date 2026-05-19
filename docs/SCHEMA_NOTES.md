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
