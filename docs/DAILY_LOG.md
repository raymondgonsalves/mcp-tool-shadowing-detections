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