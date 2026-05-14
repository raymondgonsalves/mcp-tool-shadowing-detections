"""
CONFIG.py — Forwarder configuration.

Loads credentials from .env, defines log source mappings,
and exposes constants for downstream forwarder modules.

This is the single source of truth for all configuration.
No other module should contain hardcoded paths or credentials.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# === Load environment variables from .env ===
# The .env file lives in the project root, one level above /forwarder/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

if not ENV_PATH.exists():
    raise FileNotFoundError(
        f".env file not found at {ENV_PATH}. "
        f"Copy .env.example to .env and fill in your credentials."
    )

load_dotenv(ENV_PATH)


# === Azure credentials (required) ===
def _require(name: str) -> str:
    """Get an environment variable or fail loudly if missing."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(
            f"Required environment variable '{name}' is missing or empty. "
            f"Check your .env file."
        )
    return value


AZURE_TENANT_ID = _require("AZURE_TENANT_ID")
AZURE_CLIENT_ID = _require("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = _require("AZURE_CLIENT_SECRET")
DCE_INGESTION_URL = _require("DCE_INGESTION_URL")
DCR_IMMUTABLE_ID = _require("DCR_IMMUTABLE_ID")
DCR_STREAM_NAME = _require("DCR_STREAM_NAME")


# === Log source configuration ===
# Each source is a dict with:
#   path: absolute path to the log file (as seen from WSL2)
#   parser: which parser module to use ("claude_desktop" or "ollmcp")
#   host_app: the HostApp value to stamp on every event from this source
#             (must match schema's controlled vocabulary: ClaudeDesktop, ollmcp, Cursor)
LOG_SOURCES = [
    {
        "path": "/mnt/c/Users/gonsa/mcp-security-lab/evidence/mcp_protocol_evidence.log",
        "parser": "claude_desktop",
        "host_app": "ClaudeDesktop",
    },
    {
        "path": "/mnt/c/Users/gonsa/mcp-security-lab/evidence/ollmcp_attack_capture.log",
        "parser": "ollmcp",
        "host_app": "ollmcp",
    },
]


# === Schema constants ===
SCHEMA_VERSION = "1.1"
INGESTION_AGENT = "mcplog-forwarder-v1.0"


# === Prompt injection detection keywords ===
# ENRICHER.py uses these to set ResultContainsInstructions flag.
# Match case-insensitively against tool result content.
PROMPT_INJECTION_KEYWORDS = [
    "IMPORTANT",
    "you must",
    "do not inform",
    "ignore previous",
    "<SYSTEM>",
    "<system>",
    "SYSTEM:",
]


# === Dead-letter queue path ===
# Failed events are saved here for manual replay
DEAD_LETTER_DIR = PROJECT_ROOT / "failed-events"


# === Sanity check on startup ===
def verify_config():
    """
    Verify all required configuration is present and accessible.
    Called at forwarder startup; raises if anything is missing.
    """
    # Verify all log source paths exist
    missing_paths = [
        src["path"] for src in LOG_SOURCES
        if not Path(src["path"]).exists()
    ]
    if missing_paths:
        raise FileNotFoundError(
            f"Configured log source paths do not exist: {missing_paths}"
        )

    # Verify dead-letter dir exists or can be created
    DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[CONFIG] Configuration loaded successfully.")
    print(f"[CONFIG] Loaded {len(LOG_SOURCES)} log sources.")
    print(f"[CONFIG] Schema version: {SCHEMA_VERSION}")
    print(f"[CONFIG] DCE URL: {DCE_INGESTION_URL}")
    print(f"[CONFIG] DCR Immutable ID: {DCR_IMMUTABLE_ID}")
    print(f"[CONFIG] Stream name: {DCR_STREAM_NAME}")
    print(f"[CONFIG] Dead-letter queue: {DEAD_LETTER_DIR}")


# When CONFIG.py is run directly (python -m forwarder.CONFIG),
# perform the verification. When imported, just expose the constants.
if __name__ == "__main__":
    verify_config()