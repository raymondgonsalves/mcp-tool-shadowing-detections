"""
_main.py — Forwarder orchestrator.

Wires every module into one pipeline:

    CONFIG.LOG_SOURCES
        -> NORMALIZER.normalize_source(source)   (parse + normalize + validate)
        -> ENRICHER.enrich_stream(rows)          (hashes + injection scan)
        -> batch
        -> INGESTION_CLIENT.upload_batch(batch)
              success -> log
              failure -> DEAD_LETTER.write_failed_batch(batch, ctx)

Control-flow philosophy:
    - Fail fast on setup. If CONFIG validation or the connection probe
      fails, abort before processing any data — there is no point.
    - Fail soft on batches. One failed batch is dead-lettered and the
      run continues. A single bad batch must never lose the other rows.

Usage:
    python _main.py              # full run — uploads to Azure
    python _main.py --dry-run    # parse + normalize + enrich, but DO NOT
                                 # upload; print a summary of what WOULD
                                 # have been sent. Use this first to
                                 # validate the pipeline against captured
                                 # logs without touching Azure.
"""

import argparse
import logging
import sys
import time
from collections import Counter
from typing import Dict, List

import CONFIG
import NORMALIZER
import ENRICHER
import INGESTION_CLIENT
import DEAD_LETTER


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

# Quiet the very chatty Azure SDK HTTP logger. The verify_connection probe
# already proved auth works; we don't need every request/response header
# dumped on a 28-row run. Set to WARNING so real Azure errors still show.
logging.getLogger("azure").setLevel(logging.WARNING)

log = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Run statistics
# ---------------------------------------------------------------------------

class RunStats:
    """
    Accumulates counters across the whole run so the forwarder can print
    a single structured summary at the end — the line that gets
    screenshotted for the README and read out in interviews.
    """

    def __init__(self):
        self.rows_processed = 0
        self.rows_uploaded = 0
        self.rows_dead_lettered = 0
        self.batches_uploaded = 0
        self.batches_failed = 0
        self.hash_counter = Counter()      # ToolDescriptionHash -> count
        self.event_type_counter = Counter()
        self.start_time = time.time()

    def observe_row(self, row: Dict):
        """Update per-row counters as each enriched row flows past."""
        self.rows_processed += 1
        self.event_type_counter[row.get("EventType", "UNKNOWN")] += 1
        h = row.get("ToolDescriptionHash")
        if h:                                # only count non-null hashes
            self.hash_counter[h] += 1

    def print_summary(self, dry_run: bool):
        elapsed = time.time() - self.start_time
        mode = "DRY RUN (nothing uploaded)" if dry_run else "LIVE RUN"

        log.info("=" * 60)
        log.info("FORWARDER RUN SUMMARY — %s", mode)
        log.info("=" * 60)
        log.info("Rows processed:        %d", self.rows_processed)
        if not dry_run:
            log.info("Rows uploaded:         %d", self.rows_uploaded)
            log.info("Rows dead-lettered:    %d", self.rows_dead_lettered)
            log.info("Batches uploaded OK:   %d", self.batches_uploaded)
            log.info("Batches failed:        %d", self.batches_failed)
        log.info("Distinct tool-desc hashes: %d", len(self.hash_counter))
        for h, count in self.hash_counter.most_common():
            log.info("    %s...  x%d", h[:16], count)
        log.info("Event type breakdown:")
        for etype, count in self.event_type_counter.most_common():
            log.info("    %-22s x%d", etype, count)
        log.info("Elapsed: %.2fs", elapsed)
        log.info("=" * 60)


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------

def run(dry_run: bool) -> int:
    """
    Execute the full forwarder pipeline. Returns a process exit code:
    0 on success, non-zero if a fatal setup error occurred.
    """
    stats = RunStats()

    # ---- Setup phase: fail fast --------------------------------------
    log.info("Starting forwarder (%s)...",
             "DRY RUN" if dry_run else "LIVE RUN")

    try:
        CONFIG.verify_config()
    except Exception as e:
        log.error("CONFIG verification failed: %s", e)
        log.error("Aborting — fix configuration before retrying.")
        return 1

    if not dry_run:
        # Only probe the connection on a live run. A dry run never talks
        # to Azure, so the probe would be pointless cost.
        if not INGESTION_CLIENT.verify_connection():
            log.error("Connection probe failed. Aborting before processing "
                      "any data.")
            return 1

    # ---- Processing phase: fail soft ---------------------------------
    batch: List[Dict] = []

    for source in CONFIG.LOG_SOURCES:
        log.info("Processing source: %s (parser=%s, host=%s)",
                 source["path"], source["parser"], source["host_app"])

        # Chain the two generator stages. Rows flow one at a time —
        # normalize_source yields a validated row, enrich_stream adds
        # hashes and the injection scan, and we accumulate into a batch.
        normalized = NORMALIZER.normalize_source(source)
        enriched = ENRICHER.enrich_stream(normalized)

        for row in enriched:
            stats.observe_row(row)
            batch.append(row)

            if len(batch) >= INGESTION_CLIENT.BATCH_SIZE:
                _flush_batch(batch, stats, dry_run)
                batch = []

    # Flush any partial final batch (the captured 28-row dataset is one
    # partial batch since 28 < BATCH_SIZE).
    if batch:
        _flush_batch(batch, stats, dry_run)
        batch = []

    stats.print_summary(dry_run)
    return 0


def _flush_batch(batch: List[Dict], stats: RunStats, dry_run: bool) -> None:
    """
    Send one batch. On a dry run, just account for it. On a live run,
    upload it and dead-letter on failure. Never raises — a batch failure
    is logged and dead-lettered, and the run continues.
    """
    if dry_run:
        log.info("[DRY RUN] Would upload batch of %d rows", len(batch))
        return

    success, failure = INGESTION_CLIENT.upload_batch(batch)

    if failure == 0:
        stats.rows_uploaded += success
        stats.batches_uploaded += 1
    else:
        # Upload failed. Preserve the batch so no data is lost.
        stats.batches_failed += 1
        error_context = {
            "status_code": None,        # upload_batch logs the detail;
            "error_type": "upload_failed",  # we tag generically here.
            "message": "upload_batch reported failure; see ingestion_client "
                       "log lines above for HTTP status and Azure message.",
        }
        path = DEAD_LETTER.write_failed_batch(batch, error_context)
        stats.rows_dead_lettered += len(batch)
        if path:
            log.warning("Batch of %d rows dead-lettered to %s",
                        len(batch), path.name)
        else:
            log.error("Batch of %d rows FAILED to dead-letter — data lost.",
                      len(batch))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MCP protocol log forwarder — parses captured MCP logs, "
                    "normalizes and enriches them, and ingests into "
                    "Microsoft Sentinel via the Logs Ingestion API."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full parse/normalize/enrich pipeline but do NOT "
             "upload to Azure. Prints a summary of what would have been "
             "sent. Use this first to validate the pipeline.",
    )
    args = parser.parse_args()

    exit_code = run(dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()