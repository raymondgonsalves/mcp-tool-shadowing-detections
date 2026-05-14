"""
PARSER_CLAUDE.py — Parser for Claude Desktop mcp.log files.

Claude Desktop logs the MCP protocol exchange with one event per line
in the format:

    2026-04-30T15:32:20.573Z [info] [calendar_sync] Message from server: {...JSON...}

This parser walks the file line by line, identifies protocol events,
and yields parser-internal event dicts. Multi-line server-launch metadata
blocks (Docker command args, PATH listings) are skipped — they don't carry
protocol-level signal.

The downstream NORMALIZER converts these dicts into schema-compliant rows.
"""

import json
import re
from pathlib import Path
from typing import Iterator, Optional
from unittest import result


# Each log line starts with an ISO 8601 timestamp.
# Capturing groups: timestamp, level, server name, message
LOG_LINE_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\s+'
    r'\[(?P<level>\w+)\]\s+'
    r'\[(?P<server>[^\]]+)\]\s+'
    r'(?P<message>.+?)\s*$'
)


def _extract_json_from_message(message: str) -> Optional[dict]:
    """
    Some message text contains an embedded JSON object, e.g.:
        "Message from server: {...JSON...}"
        "Message from client: {...JSON...}"

    Find the first '{' and try to parse from there. Return the dict
    or None if no parseable JSON found.
    """
    json_start = message.find("{")
    if json_start == -1:
        return None
    try:
        return json.loads(message[json_start:])
    except json.JSONDecodeError:
        return None


def parse_claude_log(file_path: str) -> Iterator[dict]:
    """
    Walk a Claude Desktop mcp.log file and yield parser-internal events.

    Yields event dicts of several types:
      - SessionStart: server connected
      - SessionEnd: server shut down
      - ToolDescriptionLoaded: tools/list response carrying tool definitions
      - ToolCallInvoked: tools/call request from client
      - ToolResultReturned: tools/call response from server

    Lines that don't match the timestamped format (multi-line continuations)
    are silently skipped.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Claude Desktop log file not found: {file_path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n").rstrip("\r")

            # Skip blank lines
            if not line.strip():
                continue

            # Skip lines that don't start with a timestamp
            # (these are multi-line continuations of the previous event)
            match = LOG_LINE_PATTERN.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            server = match.group("server")
            message = match.group("message")

            # Identify event type based on message content

            
            event = _classify_event(timestamp, server, message, line_num)
            if event is None:
                continue

            # Expand _ToolsListResponse into one ToolDescriptionLoaded per tool
            if event["event_type"] == "_ToolsListResponse":
                for tool in event.get("tools", []):
                    yield {
                        "timestamp": event["timestamp"],
                        "server_name": event["server_name"],
                        "line_num": event["line_num"],
                        "event_type": "ToolDescriptionLoaded",
                        "tool_name": tool.get("name"),
                        "tool_description": tool.get("description", ""),
                        "tool_parameters": tool.get("inputSchema", {}).get("properties", {}),
                    }
            else:
                yield event


def _classify_event(
    timestamp: str, server: str, message: str, line_num: int
) -> Optional[dict]:
    """
    Examine a parsed log line and decide what kind of event it represents.
    Returns an event dict, or None if the line is not a protocol-level event
    of interest.
    """
    base = {
        "timestamp": timestamp,
        "server_name": server,
        "line_num": line_num,
    }

    # Session lifecycle events
    if message == "Server started and connected successfully":
        return {**base, "event_type": "SessionStart"}

    if message == "Shutting down server...":
        return {**base, "event_type": "SessionEnd"}

    # Protocol message events — these contain embedded JSON
    if message.startswith("Message from server:"):
        payload = _extract_json_from_message(message)
        if payload is None:
            return None
        return _classify_server_message(base, payload)

    if message.startswith("Message from client:"):
        payload = _extract_json_from_message(message)
        if payload is None:
            return None
        return _classify_client_message(base, payload)

    # Other log lines we don't care about
    return None


def _classify_server_message(base: dict, payload: dict) -> Optional[dict]:
    """
    Classify a 'Message from server' event by inspecting its JSON payload.
    The server's most interesting messages are tools/list responses
    (carrying tool descriptions) and tools/call responses (results).
    """
    # tools/list response — carries tool definitions
    if "result" in payload and isinstance(payload["result"], dict):
        result = payload["result"]

        # Response to tools/list contains a "tools" array
    if "tools" in result:
    # The server's tools/list response carries one or more tools.
    # We'd emit one event per tool, but a function can only return once.
    # Wrap as a list and let the orchestrator iterate.
        return {
        **base,
        "event_type": "_ToolsListResponse",
        "tools": result["tools"],
    }


        # Response to tools/call carries the tool result
        # (typically a "content" array with text fragments)
    if "content" in result:
            return {
                **base,
                "event_type": "ToolResultReturned",
                "result_payload": result,
            }

    return None


def _classify_client_message(base: dict, payload: dict) -> Optional[dict]:
    """
    Classify a 'Message from client' event by inspecting its JSON payload.
    The client's most interesting message is tools/call requests.
    """
    method = payload.get("method")

    if method == "tools/call":
        params = payload.get("params", {})
        return {
            **base,
            "event_type": "ToolCallInvoked",
            "tool_name": params.get("name"),
            "parameters": params.get("arguments", {}),
        }

    # Other client methods (initialize, tools/list, notifications/initialized)
    # are not protocol-level events of interest for our detection rules.
    return None


def main():
    """
    Run the parser against the configured Claude Desktop log
    and print every event it yields. For testing/debugging.
    """
    from CONFIG import LOG_SOURCES

    claude_source = next(
        (src for src in LOG_SOURCES if src["parser"] == "claude_desktop"),
        None
    )
    if not claude_source:
        print("ERROR: No Claude Desktop source configured in CONFIG.LOG_SOURCES")
        return

    print(f"[PARSER_CLAUDE] Parsing {claude_source['path']}")
    print()

    event_count = 0
    events_by_type = {}

    for event in parse_claude_log(claude_source["path"]):
        event_count += 1
        events_by_type[event["event_type"]] = (
            events_by_type.get(event["event_type"], 0) + 1
        )

        print(f"--- Event {event_count} (line {event['line_num']}) ---")
        print(f"  Type: {event['event_type']}")
        print(f"  Server: {event['server_name']}")
        print(f"  Timestamp: {event['timestamp']}")

        if event["event_type"] == "ToolDescriptionLoaded":
            tool_name = event.get("tool_name", "?")
            desc = event.get("tool_description", "")
            desc_preview = desc[:80].replace("\n", " ").strip()
            print(f"  Tool: {tool_name}")
            print(f"  Description preview: {desc_preview}...")
            if "<IMPORTANT>" in desc:
                print(f"  *** POISONED DESCRIPTION DETECTED ***")

        elif event["event_type"] == "ToolCallInvoked":
            print(f"  Tool: {event.get('tool_name')}")
            print(f"  Parameters: {event.get('parameters')}")

        elif event["event_type"] == "ToolResultReturned":
            # Show a preview of the result
            payload = event.get("result_payload", {})
            content = payload.get("content", [])
            if content and isinstance(content, list):
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text", "")[:80]
                    print(f"  Result preview: {text}...")

        print()

    print(f"[PARSER_CLAUDE] Total events yielded: {event_count}")
    print(f"[PARSER_CLAUDE] Events by type:")
    for event_type, count in sorted(events_by_type.items()):
        print(f"    {event_type}: {count}")


if __name__ == "__main__":
    main()