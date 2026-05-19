"""
NORMALIZER.py — Convert parser-internal events into 23-column schema rows.

Both PARSER_OLLMCP and PARSER_CLAUDE produce parser-internal event dicts
with different shapes. NORMALIZER reconciles them into a single, consistent
output format that matches the MCPProtocolLogs_CL custom table schema (v1.1).

This module deliberately does NOT:
  - Compute hashes (ENRICHER's job; needs description/prompt text)
  - Scan for prompt-injection keywords (ENRICHER's job)
  - Talk to Azure (INGESTION_CLIENT's job)

NORMALIZER does one thing: dict shape transformation.
"""

import json
import uuid
from typing import Iterator, Optional

import CONFIG


# === Schema-required columns (v1.1) ===
# Every output row must have all 23 of these keys.
# This is the contract NORMALIZER guarantees.
SCHEMA_COLUMNS = [
    "EventTime",  # wire field; DCR transform maps -> reserved TimeGenerated column
    "EventType",
    "SessionId",
    "HostApp",
    "ModelName",
    "ServerName",
    "ServerVersion",
    "ServerTransport",
    "ToolName",
    "ToolDescription",
    "ToolDescriptionHash",
    "ToolDescriptionLength",
    "ToolParameters",
    "CallId",
    "CallParameters",
    "UserPromptHash",
    "ConfidenceClaim",
    "ResultStatus",
    "ResultLength",
    "ResultContainsInstructions",
    "IngestionAgent",
    "SchemaVersion",
    "RawEvent",
]


# === Sentinel-default row ===
# Every row starts from this skeleton. Specific normalizer functions
# overlay event-type-specific values on top.
# Note: ToolDescriptionLength, ResultLength, ResultContainsInstructions
# carry sentinel values (0, 0, false) per Schema v1.1 Section 6.6.
def _empty_row() -> dict:
    return {
        "EventTime": None,
        "EventType": None,
        "SessionId": None,
        "HostApp": None,
        "ModelName": None,
        "ServerName": None,
        "ServerVersion": None,
        "ServerTransport": "stdio",
        "ToolName": None,
        "ToolDescription": None,
        "ToolDescriptionHash": None,
        "ToolDescriptionLength": 0,
        "ToolParameters": None,
        "CallId": None,
        "CallParameters": None,
        "UserPromptHash": None,
        "ConfidenceClaim": None,
        "ResultStatus": None,
        "ResultLength": 0,
        "ResultContainsInstructions": False,
        "IngestionAgent": CONFIG.INGESTION_AGENT,
        "SchemaVersion": CONFIG.SCHEMA_VERSION,
        "RawEvent": None,
    }


# === Session ID generation ===
# Each forwarder run generates SessionIds per source.
# - ollmcp source: one SessionId for the whole file (single transcript = single session)
# - Claude Desktop source: a new SessionId at each SessionStart event

class SessionTracker:
    """
    Generates and maintains SessionId for a parser's event stream.
    For ollmcp: one ID for the whole stream.
    For Claude Desktop: new ID on each SessionStart event.
    """
    def __init__(self, mode: str):
        if mode not in ("single", "per_session_start"):
            raise ValueError(f"Unknown session mode: {mode}")
        self.mode = mode
        self._current_id = str(uuid.uuid4()) if mode == "single" else None

    def get_for_event(self, event_type: str) -> str:
        """
        Return the current SessionId. For per_session_start mode,
        advance to a new ID when EventType == SessionStart.
        """
        if self.mode == "per_session_start":
            if event_type == "SessionStart" or self._current_id is None:
                self._current_id = str(uuid.uuid4())
        return self._current_id


# === Per-parser normalizers ===

def normalize_ollmcp_event(event: dict, host_app: str, session_id: str) -> Optional[dict]:
    """
    Convert a PARSER_OLLMCP event dict into a schema-compliant row.

    ollmcp parser produces these event types:
      - UserPrompt: not directly stored in the schema (used to enrich tool calls).
                    Returns None — UserPrompt rows are not emitted.
      - ToolCallInvoked: maps to schema EventType "ToolCallInvoked"
    """
    parser_event_type = event["event_type"]

    if parser_event_type == "UserPrompt":
        # User prompts are not their own schema row.
        # They flow into the UserPromptHash of subsequent ToolCallInvoked events.
        return None

    row = _empty_row()
    row["HostApp"] = host_app
    row["SessionId"] = session_id
    row["ModelName"] = "llama3.2"  # Hard-coded for ollmcp; could be in CONFIG later

    if parser_event_type == "ToolCallInvoked":
        row["EventType"] = "ToolCallInvoked"
        row["ToolName"] = event.get("tool_name")
        row["ServerName"] = event.get("tool_name")  # ollmcp parser doesn't track separate ServerName
        # CallParameters must be a JSON-serializable dict — pass through as-is
        row["CallParameters"] = event.get("parameters", {})
        # Generate a synthetic CallId since ollmcp doesn't surface a protocol ID
        row["CallId"] = f"ollmcp_{event.get('line_num', 0)}"
        # The associated user prompt feeds into UserPromptHash via ENRICHER.
        # NORMALIZER passes it through in a temporary _user_prompt key.
        if event.get("associated_prompt"):
            row["_user_prompt"] = event["associated_prompt"]
        # RawEvent — for v1, store a JSON representation of the parser event
        row["RawEvent"] = json.dumps({
            "tool_name": event.get("tool_name"),
            "parameters": event.get("parameters"),
            "line_num": event.get("line_num"),
        })
        # EventTime: ollmcp parser doesn't capture per-event timestamps
        # so we use the forwarder's current time at normalization.
        # DCR transform maps this wire field -> stored TimeGenerated column.
        from datetime import datetime, timezone
        row["EventTime"] = datetime.now(timezone.utc).isoformat()
        return row

    # Unrecognized event type
    return None


def normalize_claude_event(event: dict, host_app: str, session_id: str) -> Optional[dict]:
    """
    Convert a PARSER_CLAUDE event dict into a schema-compliant row.

    Claude Desktop parser produces these event types:
      - SessionStart: maps to schema EventType "SessionStart"
      - SessionEnd: maps to schema EventType "SessionEnd"
      - ToolDescriptionLoaded: maps to schema EventType "ToolDescriptionLoaded"
      - ToolCallInvoked: maps to schema EventType "ToolCallInvoked"
      - ToolResultReturned: maps to schema EventType "ToolResultReturned"
    """
    parser_event_type = event["event_type"]

    row = _empty_row()
    row["HostApp"] = host_app
    row["SessionId"] = session_id
    row["EventTime"] = event.get("timestamp")  # real Claude event time; DCR maps -> TimeGenerated
    row["ServerName"] = event.get("server_name")
    row["ModelName"] = "claude-opus"  # Hard-coded for Claude Desktop; refine in v2

    if parser_event_type == "SessionStart":
        row["EventType"] = "SessionStart"
        row["RawEvent"] = json.dumps({
            "server": event.get("server_name"),
            "line_num": event.get("line_num"),
        })
        return row

    if parser_event_type == "SessionEnd":
        row["EventType"] = "SessionEnd"
        row["RawEvent"] = json.dumps({
            "server": event.get("server_name"),
            "line_num": event.get("line_num"),
        })
        return row

    if parser_event_type == "ToolDescriptionLoaded":
        row["EventType"] = "ToolDescriptionLoaded"
        row["ToolName"] = event.get("tool_name")
        desc = event.get("tool_description", "")
        row["ToolDescription"] = desc
        row["ToolDescriptionLength"] = len(desc)
        row["ToolParameters"] = event.get("tool_parameters", {})
        row["RawEvent"] = json.dumps({
            "tool_name": event.get("tool_name"),
            "description_preview": desc[:200],  # First 200 chars; full text in ToolDescription
            "line_num": event.get("line_num"),
        })
        return row

    if parser_event_type == "ToolCallInvoked":
        row["EventType"] = "ToolCallInvoked"
        row["ToolName"] = event.get("tool_name")
        row["CallParameters"] = event.get("parameters", {})
        row["CallId"] = f"claude_{event.get('line_num', 0)}"
        row["RawEvent"] = json.dumps({
            "tool_name": event.get("tool_name"),
            "parameters": event.get("parameters"),
            "line_num": event.get("line_num"),
        })
        return row

    if parser_event_type == "ToolResultReturned":
        row["EventType"] = "ToolResultReturned"
        # Extract status and content length from the result payload
        payload = event.get("result_payload", {})
        content = payload.get("content", [])
        if content and isinstance(content, list) and isinstance(content[0], dict):
            result_text = content[0].get("text", "")
            row["ResultLength"] = len(result_text)
            # Try to extract a status field from the text (it's often a JSON string)
            try:
                inner = json.loads(result_text)
                if isinstance(inner, dict):
                    row["ResultStatus"] = inner.get("status")
            except (json.JSONDecodeError, TypeError):
                pass
        row["RawEvent"] = json.dumps({
            "result_payload": payload,
            "line_num": event.get("line_num"),
        })
        return row

    # Unrecognized event type
    return None


# === The dispatcher: route to the right normalizer ===

def normalize_event(event: dict, source: dict, session_tracker: SessionTracker) -> Optional[dict]:
    """
    Dispatcher: given a parser event and its source config, return a
    schema-compliant row dict (or None if the event shouldn't produce a row).
    """
    session_id = session_tracker.get_for_event(event.get("event_type", ""))
    host_app = source["host_app"]

    parser_type = source["parser"]
    if parser_type == "ollmcp":
        return normalize_ollmcp_event(event, host_app, session_id)
    if parser_type == "claude_desktop":
        return normalize_claude_event(event, host_app, session_id)

    raise ValueError(f"Unknown parser type in source config: {parser_type}")


# === Schema validation ===
# Before emitting, every row is checked against the schema contract.

def validate_row(row: dict) -> Optional[str]:
    """
    Verify a row matches the schema contract.
    Returns None if valid, or an error message string if invalid.
    """
    # Strip any internal-only fields (those starting with underscore)
    public_keys = [k for k in row.keys() if not k.startswith("_")]

    # All 23 schema columns must be present
    missing = [col for col in SCHEMA_COLUMNS if col not in public_keys]
    if missing:
        return f"Missing schema columns: {missing}"

    # Check sentinel fields have correct types (not None)
    if row["ToolDescriptionLength"] is None:
        return "ToolDescriptionLength is None (should be int, sentinel 0)"
    if row["ResultLength"] is None:
        return "ResultLength is None (should be int, sentinel 0)"
    if row["ResultContainsInstructions"] is None:
        return "ResultContainsInstructions is None (should be bool, sentinel false)"

    # Required identity fields cannot be None
    required = ["EventTime", "EventType", "SessionId", "HostApp", "IngestionAgent", "SchemaVersion"]
    for field in required:
        if row.get(field) is None:
            return f"Required field {field} is None"

    return None


def normalize_source(source: dict) -> Iterator[dict]:
    """
    Run the appropriate parser for a source, normalize each event,
    and yield schema-compliant rows.
    """
    parser_type = source["parser"]

    if parser_type == "ollmcp":
        from PARSER_OLLMCP import parse_ollmcp_log
        events = parse_ollmcp_log(source["path"])
        tracker = SessionTracker(mode="single")
    elif parser_type == "claude_desktop":
        from PARSER_CLAUDE import parse_claude_log
        events = parse_claude_log(source["path"])
        tracker = SessionTracker(mode="per_session_start")
    else:
        raise ValueError(f"Unknown parser: {parser_type}")

    for event in events:
        row = normalize_event(event, source, tracker)
        if row is None:
            continue
        error = validate_row(row)
        if error:
            print(f"[NORMALIZER] WARNING: row failed validation: {error}")
            print(f"  Event: {event}")
            continue
        yield row


# === Test runner ===

def main():
    """Run the normalizer against all configured sources and report results."""
    total_rows = 0
    rows_by_source = {}
    rows_by_event_type = {}

    for source in CONFIG.LOG_SOURCES:
        print(f"[NORMALIZER] Reading from {source['parser']} parser...")
        rows_by_source[source["parser"]] = 0
        for row in normalize_source(source):
            total_rows += 1
            rows_by_source[source["parser"]] += 1
            event_type = row["EventType"]
            rows_by_event_type[event_type] = rows_by_event_type.get(event_type, 0) + 1

        print(f"[NORMALIZER]   {rows_by_source[source['parser']]} rows from {source['parser']}")

    print()
    print(f"[NORMALIZER] Total rows produced: {total_rows}")
    print(f"[NORMALIZER] All rows passed schema validation.")
    print(f"[NORMALIZER] Rows by EventType:")
    for event_type, count in sorted(rows_by_event_type.items()):
        print(f"    {event_type}: {count}")


if __name__ == "__main__":
    main()