"""
INGESTION_CLIENT.py — Authenticates to Azure and POSTs enriched rows to the
Data Collection Endpoint (DCE), which routes them through the Data Collection
Rule (DCR) into the MCPProtocolLogs_CL custom table in Log Analytics.

Public surface:
    upload_batch(rows)        — send a list of enriched row dicts; returns
                                (success_count, failure_count)
    verify_connection()       — startup probe; sends a single trivial test row
                                to confirm auth and DCR wiring before the
                                forwarder pumps real data. Returns True/False.

Design notes:
    - Authenticates via ClientSecretCredential (service principal flow).
    - The LogsIngestionClient is constructed lazily on first use and cached
      at module scope. We do not re-authenticate per batch.
    - The library handles HTTPS, retries, and the DCR routing internally.
      Our job is just to give it well-formed rows.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

from azure.core.exceptions import HttpResponseError
from azure.identity import ClientSecretCredential
from azure.monitor.ingestion import LogsIngestionClient

import CONFIG


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Batch size: 100 rows per POST. Well under the library's 1 MB / 32k-row
# limits even with the RawEvent field included, and small enough that a
# single failed batch loses only a bounded amount of data.
BATCH_SIZE = 100

# Logger named after the module so log lines are attributable to this layer
# (vs PARSER, NORMALIZER, ENRICHER).
log = logging.getLogger("ingestion_client")


# ---------------------------------------------------------------------------
# Internal: lazy client construction
# ---------------------------------------------------------------------------

# Cached at module scope. Constructed on first call to _get_client().
_client: Optional[LogsIngestionClient] = None


def _get_client() -> LogsIngestionClient:
    """
    Build the LogsIngestionClient once and cache it. Subsequent calls
    return the cached instance — we do not re-authenticate per batch.

    Why lazy: it lets the module import cleanly even if credentials are
    bad, so other modules that import this one don't crash at import time.
    The auth failure surfaces on the first call instead.
    """
    global _client
    if _client is None:
        credential = ClientSecretCredential(
            tenant_id=CONFIG.AZURE_TENANT_ID,
            client_id=CONFIG.AZURE_CLIENT_ID,
            client_secret=CONFIG.AZURE_CLIENT_SECRET,
        )
        _client = LogsIngestionClient(
            endpoint=CONFIG.DCE_INGESTION_URL,
            credential=credential,
        )
        log.info("Constructed LogsIngestionClient (endpoint=%s)",
                 CONFIG.DCE_INGESTION_URL)
    return _client


# ---------------------------------------------------------------------------
# Public: upload a batch
# ---------------------------------------------------------------------------

def upload_batch(rows: List[Dict]) -> Tuple[int, int]:
    """
    Send a list of enriched row dicts to the DCE as a single POST.

    Returns (success_count, failure_count). On success the library returns
    silently — there is no per-row acknowledgment, so success_count is
    either len(rows) or 0 depending on whether the call raised.

    The caller (typically _main.py) is responsible for collecting failed
    batches and routing them to DEAD_LETTER.
    """
    if not rows:
        return (0, 0)

    client = _get_client()

    try:
        client.upload(
            rule_id=CONFIG.DCR_IMMUTABLE_ID,
            stream_name=CONFIG.DCR_STREAM_NAME,
            logs=rows,
        )
        log.info("Uploaded batch of %d rows", len(rows))
        return (len(rows), 0)

    except HttpResponseError as e:
        # Azure returned a structured error. Log enough detail that we can
        # diagnose without re-running. The status code and the error.message
        # are the two fields worth seeing in the log.
        log.error(
            "Batch upload failed: HTTP %s — %s",
            e.status_code,
            getattr(e, "message", str(e)),
        )
        return (0, len(rows))

    except Exception as e:
        # Catch-all for network errors, credential expiry mid-batch, etc.
        # We don't want one bad batch to crash the forwarder loop.
        log.error("Batch upload failed with unexpected error: %s", e)
        return (0, len(rows))


# ---------------------------------------------------------------------------
# Public: startup probe
# ---------------------------------------------------------------------------

def verify_connection() -> bool:
    """
    Send a single trivial test row to confirm that auth, the DCE endpoint,
    the DCR Immutable ID, and the stream name are all wired correctly.

    Run this once at forwarder startup. If it returns False, abort before
    pumping any real data — there is no point in continuing.

    The test row uses EventType="SessionStart" and a recognizable
    SessionId so it can be filtered out in KQL during normal review:

        MCPProtocolLogs_CL
        | where SessionId !startswith "verify-"

    Sentinel ingestion latency is 1-5 minutes, so this row will not be
    queryable immediately after verify_connection() returns. That's fine —
    the return value tells us the POST itself succeeded.
    """
    test_row = {
        "EventTime": datetime.now(timezone.utc).isoformat(),
        "EventType": "SessionStart",
        "SessionId": f"verify-{uuid.uuid4()}",
        "HostApp": "ClaudeDesktop",
        "ModelName": "verify-connection-probe",
        "ServerName": None,
        "ServerVersion": None,
        "ServerTransport": None,
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
        "RawEvent": '{"event":"verify_connection_probe"}',
    }

    log.info("Running connection verification probe...")
    success, failure = upload_batch([test_row])

    if success == 1:
        log.info("Verification probe succeeded — auth and DCR wiring confirmed.")
        return True
    else:
        log.error("Verification probe failed — check credentials, DCE URL, "
                  "DCR Immutable ID, and stream name.")
        return False


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Configure logging for standalone run. The forwarder's _main.py will
    # set up its own logging config; this block just makes the module
    # runnable on its own for debugging.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Run the verification probe and exit with a status code that reflects
    # the result, so this can be wired into shell scripts later.
    ok = verify_connection()
    exit(0 if ok else 1)