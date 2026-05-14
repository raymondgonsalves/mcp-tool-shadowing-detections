"""
PARSER_OLLMCP.py — Parser for ollmcp transcript files.

ollmcp output is captured via PowerShell's Start-Transcript, which wraps
the actual session content in a transcript header/footer. The session itself
contains a mix of:
  - ollmcp UI decorations (Update Available box, separators)
  - User prompts at the llama3.2/X-tools> prompt
  - JSON tool call output emitted by the model

This parser walks the file line by line, identifies meaningful lines,
and yields parser-internal event dicts. The downstream NORMALIZER converts
these dicts into schema-compliant rows.
"""

import json
import re
from pathlib import Path
from typing import Iterator


# ollmcp emits tool calls as JSON on their own line.
# A line that starts with '{' and contains '"name"' is our signal.
TOOL_CALL_PATTERN = re.compile(r'^\s*\{.*"name"\s*:\s*"[^"]+"', re.DOTALL)

# ollmcp's interactive prompt looks like: llama3.2/2-tools> <user text>
# The ❯ character (heavy right-pointing angle, U+276F) is the actual separator.
# We accept either > or ❯ to handle terminal encoding variations.
USER_PROMPT_PATTERN = re.compile(r'^llama3\.2/\d+-tools[❯>]\s*(.+)$')

# PowerShell transcript boundaries — lines of asterisks
TRANSCRIPT_BOUNDARY = re.compile(r'^\*{10,}$')


def parse_ollmcp_log(file_path: str) -> Iterator[dict]:
    """
    Walk an ollmcp transcript file and yield event dicts.

    Yields one of:
      - {"event_type": "UserPrompt", "prompt_text": "..."}
      - {"event_type": "ToolCallInvoked", "tool_name": "...", "parameters": {...}}

    Lines that don't match either pattern are silently skipped
    (PowerShell metadata, UI decorations, blank lines, etc.)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ollmcp log file not found: {file_path}")

    # Track the most recent user prompt, so we can associate it
    # with the tool call that follows.
    most_recent_prompt = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n").rstrip("\r")

            # Skip PowerShell transcript boundary lines
            if TRANSCRIPT_BOUNDARY.match(line):
                continue

            # Skip blank lines
            if not line.strip():
                continue

            # Check for user prompt line
            prompt_match = USER_PROMPT_PATTERN.match(line)
            if prompt_match:
                prompt_text = prompt_match.group(1).strip()

                # Skip slash-commands like /quit, /help, /tools
                if prompt_text.startswith("/"):
                    continue

                most_recent_prompt = prompt_text
                yield {
                    "event_type": "UserPrompt",
                    "prompt_text": prompt_text,
                    "line_num": line_num,
                }
                continue

            # Check for tool call JSON line
            if TOOL_CALL_PATTERN.match(line):
                try:
                    parsed = json.loads(line.strip())
                except json.JSONDecodeError:
                    # Not actually valid JSON — skip
                    continue

                # Validate it has the structure we expect
                if "name" not in parsed or "parameters" not in parsed:
                    continue

                yield {
                    "event_type": "ToolCallInvoked",
                    "tool_name": parsed["name"],
                    "parameters": parsed["parameters"],
                    "associated_prompt": most_recent_prompt,
                    "line_num": line_num,
                }
                continue

            # Line didn't match anything we care about — skip silently


def main():
    """
    Run the parser against the configured ollmcp log
    and print every event it yields. For testing/debugging.
    """
    # Import here to avoid circular imports if CONFIG ever imports the parser
    from CONFIG import LOG_SOURCES

    # Find the ollmcp source in CONFIG
    ollmcp_source = next(
        (src for src in LOG_SOURCES if src["parser"] == "ollmcp"),
        None
    )
    if not ollmcp_source:
        print("ERROR: No ollmcp source configured in CONFIG.LOG_SOURCES")
        returnp

    print(f"[PARSER_OLLMCP] Parsing {ollmcp_source['path']}")
    print()

    event_count = 0
    for event in parse_ollmcp_log(ollmcp_source["path"]):
        event_count += 1
        print(f"--- Event {event_count} (line {event['line_num']}) ---")
        print(f"  Type: {event['event_type']}")
        if event["event_type"] == "UserPrompt":
            print(f"  Prompt: {event['prompt_text']!r}")
        elif event["event_type"] == "ToolCallInvoked":
            print(f"  Tool: {event['tool_name']}")
            print(f"  Parameters: {event['parameters']}")
            if event.get("associated_prompt"):
                print(f"  Associated prompt: {event['associated_prompt']!r}")
        print()

    print(f"[PARSER_OLLMCP] Total events yielded: {event_count}")


if __name__ == "__main__":
    main()