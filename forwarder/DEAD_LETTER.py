"""
DEAD_LETTER.py — Persists batches that failed to upload to Azure so no data
is silently lost. Failed batches are written to /failed-events/ as JSONL
files with timestamped names and an error-context metadata header.

Public surface:
    write_failed_batch(rows, error_context) — writes the failed batch to a
                                              timestamped JSONL file in
                                              CONFIG.DEAD_LETTER_DIR. Returns
                                              the file path for caller logging.

Design notes:
    - JSONL format (one JSON object per line) because it is append-safe and
      stream-readable. Standard format for log queues and dead-letter files.
    - Each file's first line is a metadata object describing why the batch
      failed (HTTP status, error message, batch timestamp). Subsequent lines
      are the failed rows themselves. Without this metadata, a dead-letter
      file three months from now would be uninterpretable.
    - This module does not retry. Retry logic belongs in a separate replay
      script or an explicit operational action. Mixing persistence with
      retry creates failure modes where a dead-letter queue retries itself
      into oblivion.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import CONFIG


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Logger named after the module so log lines are attributable to this layer.
log = logging.getLogger("dead_letter")


# ---------------------------------------------------------------------------
# Public: write a failed batch to disk
# ---------------------------------------------------------------------------

def write_failed_batch(
    rows: List[Dict],
    error_context: Optional[Dict] = None,
) -> Path:
    """
    Write a failed batch to a timestamped JSONL file in the dead-letter
    directory. Returns the path to the file written.

    The first line of the file is an error-context metadata object. The
    subsequent lines are the failed rows, one per line. A replay script
    can read line 1 for context, then process lines 2-N as rows.

    Filename convention:
        dead_letter_YYYYMMDD_HHMMSSffffff_<reason>_<count>rows.jsonl

    The filename includes microseconds because two failures in the same
    second would otherwise collide. The reason is a short tag like
    "http403", "network", or "unknown" — derived from error_context if
    present, defaulted to "unknown" otherwise.
    """
    if not rows:
        log.warning("write_failed_batch called with empty rows list; nothing to write")
        return None

    # ---- Build the filename ----------------------------------------------
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S%f")
    reason = _derive_reason(error_context)
    filename = f"dead_letter_{timestamp_str}_{reason}_{len(rows)}rows.jsonl"
    filepath = CONFIG.DEAD_LETTER_DIR / filename

    # ---- Build the metadata header --------------------------------------
    metadata = {
        "_dead_letter_metadata": True,
        "timestamp_utc": now.isoformat(),
        "row_count": len(rows),
        "reason": reason,
        "error_context": error_context or {},
        "ingestion_agent": CONFIG.INGESTION_AGENT,
        "schema_version": CONFIG.SCHEMA_VERSION,
    }

    # ---- Write the file --------------------------------------------------
    # Open in write mode (not append) — each failed batch gets its own
    # file, so we never append to an existing dead-letter file. This
    # keeps the model simple and makes replay scripts deterministic.
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            # Line 1: metadata header
            f.write(json.dumps(metadata) + "\n")
            # Lines 2-N: the failed rows
            for row in rows:
                f.write(json.dumps(row) + "\n")

        log.warning(
            "Dead-lettered batch of %d rows to %s (reason=%s)",
            len(rows),
            filepath.name,
            reason,
        )
        return filepath

    except Exception as e:
        # If we cannot even write to the dead-letter directory, we are in
        # serious trouble — the rows will be lost. Log loudly so the
        # operator sees this in the forwarder output, but do not raise:
        # the caller is already in a failure path and should not be
        # interrupted by a secondary failure.
        log.error(
            "FAILED to write dead-letter file %s: %s. "
            "%d rows have been lost.",
            filepath.name,
            e,
            len(rows),
        )
        return None


# ---------------------------------------------------------------------------
# Internal: derive a short reason tag from error context
# ---------------------------------------------------------------------------

def _derive_reason(error_context: Optional[Dict]) -> str:
    """
    Produce a short filename-safe tag describing why the batch failed.
    Used as part of the dead-letter filename so an operator scanning the
    directory can categorize failures at a glance.

    Returns one of:
        "http<status>"  — when HTTP status code is present (e.g. "http403")
        "network"       — when error context indicates a network issue
        "unknown"       — when no useful context is available
    """
    if not error_context:
        return "unknown"

    # If the caller passed an HTTP status code, use it.
    status_code = error_context.get("status_code")
    if status_code is not None:
        return f"http{status_code}"

    # If the caller categorized the error as a network failure, tag it.
    error_type = error_context.get("error_type", "").lower()
    if "network" in error_type or "connection" in error_type:
        return "network"

    return "unknown"


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Configure logging for standalone run.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Build a synthetic failed batch with two rows and write it. This
    # verifies that the directory is writable, the JSONL format is
    # well-formed, and the filename convention works.
    test_rows = [
        {
            "TimeGenerated": "2026-05-15T15:30:00.000Z",
            "EventType": "SessionStart",
            "SessionId": "smoke-test-001",
            "HostApp": "ClaudeDesktop",
            "ModelName": "smoke-test",
            "SchemaVersion": CONFIG.SCHEMA_VERSION,
            "IngestionAgent": CONFIG.INGESTION_AGENT,
            "RawEvent": '{"event":"smoke_test"}',
        },
        {
            "TimeGenerated": "2026-05-15T15:30:01.000Z",
            "EventType": "SessionEnd",
            "SessionId": "smoke-test-001",
            "HostApp": "ClaudeDesktop",
            "ModelName": "smoke-test",
            "SchemaVersion": CONFIG.SCHEMA_VERSION,
            "IngestionAgent": CONFIG.INGESTION_AGENT,
            "RawEvent": '{"event":"smoke_test_end"}',
        },
    ]

    test_error_context = {
        "status_code": 503,
        "error_type": "HttpResponseError",
        "message": "Service Unavailable (smoke test — not a real failure)",
    }

    print(f"Writing test batch to {CONFIG.DEAD_LETTER_DIR}...")
    filepath = write_failed_batch(test_rows, test_error_context)

    if filepath:
        print(f"\n[OK] Dead-letter file written: {filepath.name}")
        print(f"     Full path: {filepath}")
        print(f"\nFile contents:")
        print("-" * 60)
        with open(filepath, "r") as f:
            print(f.read())
        print("-" * 60)
        print("\nDelete this file before running the forwarder for real:")
        print(f"    rm {filepath}")
    else:
        print("\n[FAIL] Dead-letter file was not written. Check logs above.")
        exit(1)