"""
ENRICHER.py — Compute hash and flag fields on schema rows.

NORMALIZER produces schema-compliant rows but leaves three fields
for ENRICHER to fill in (because they're derived from row content,
not from the parser's data shape):

  - ToolDescriptionHash: SHA-256 of whitespace-normalized description
                         (Schema Section 6.3)
  - UserPromptHash: SHA-256 of the user prompt text (unnormalized)
  - ResultContainsInstructions: boolean from keyword scan
                                (Schema Section 6.1)

ENRICHER does not modify the row's shape — it only populates fields
that NORMALIZER left at sentinel values.
"""

import hashlib
import re
from typing import Iterator

import CONFIG


# Pre-compile the regex pattern that collapses internal whitespace.
# Compiled once at module load; reused for every row.
_WHITESPACE_COLLAPSE = re.compile(r"\s+")


def _normalize_description(text: str) -> str:
    """
    Whitespace-normalize a tool description for hashing.

    Per Schema Section 6.3:
      - Strip leading and trailing whitespace
      - Collapse internal runs of whitespace to a single space

    This ensures hash stability across captures that may have
    different indentation or line-ending conventions.
    """
    if not text:
        return ""
    return _WHITESPACE_COLLAPSE.sub(" ", text.strip())


def _sha256_hex(text: str) -> str:
    """Compute SHA-256 of text, returned as lowercase hex string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_tool_description(description: str) -> str:
    """
    Hash a tool description per the Schema 6.3 contract:
    whitespace-normalize, then SHA-256.
    """
    normalized = _normalize_description(description)
    return _sha256_hex(normalized)


def _hash_user_prompt(prompt: str) -> str:
    """
    Hash a user prompt per Schema 6.3 contract:
    NO normalization — preserves the user's intent fidelity exactly.
    """
    return _sha256_hex(prompt)


def _scan_for_instructions(text: str) -> bool:
    """
    Scan text for any of the configured prompt-injection keywords.
    Case-insensitive match.

    Used to set ResultContainsInstructions flag.
    Keywords are defined in CONFIG.PROMPT_INJECTION_KEYWORDS.
    """
    if not text:
        return False
    text_lower = text.lower()
    for keyword in CONFIG.PROMPT_INJECTION_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


def enrich_row(row: dict) -> dict:
    """
    Take a NORMALIZER-output row and fill in the three computed fields.

    Modifies the row in place AND returns it (for use in pipelines).
    """
    event_type = row.get("EventType")

    # Hash the tool description if this event has one
    if event_type == "ToolDescriptionLoaded":
        desc = row.get("ToolDescription", "")
        if desc:
            row["ToolDescriptionHash"] = _hash_tool_description(desc)

    # Hash the user prompt if NORMALIZER passed one through
    # (only ollmcp tool calls carry _user_prompt)
    user_prompt = row.get("_user_prompt")
    if user_prompt:
        row["UserPromptHash"] = _hash_user_prompt(user_prompt)
        # Clean up the internal-only field before downstream consumers see it
        del row["_user_prompt"]

    # Scan tool results for prompt-injection keywords
    if event_type == "ToolResultReturned":
        # Extract result text from RawEvent (NORMALIZER stored it there)
        raw = row.get("RawEvent", "")
        if raw and _scan_for_instructions(raw):
            row["ResultContainsInstructions"] = True

    return row


def enrich_stream(rows: Iterator[dict]) -> Iterator[dict]:
    """
    Take a stream of NORMALIZER rows and yield enriched rows.

    Generator pattern — rows pass through one at a time, no buffering.
    """
    for row in rows:
        yield enrich_row(row)


# === Test runner ===

def main():
    """
    Run NORMALIZER through ENRICHER and report what got enriched.
    """
    from NORMALIZER import normalize_source

    total_rows = 0
    enrichments = {
        "ToolDescriptionHash": 0,
        "UserPromptHash": 0,
        "ResultContainsInstructions_true": 0,
    }
    unique_hashes = set()
    poisoned_hashes = set()

    for source in CONFIG.LOG_SOURCES:
        print(f"[ENRICHER] Reading from {source['parser']}...")
        for row in enrich_stream(normalize_source(source)):
            total_rows += 1

            if row.get("ToolDescriptionHash"):
                enrichments["ToolDescriptionHash"] += 1
                unique_hashes.add(row["ToolDescriptionHash"])
                # Track if this hash corresponds to a poisoned description
                desc = row.get("ToolDescription", "")
                if "<IMPORTANT>" in desc:
                    poisoned_hashes.add(row["ToolDescriptionHash"])

            if row.get("UserPromptHash"):
                enrichments["UserPromptHash"] += 1

            if row.get("ResultContainsInstructions"):
                enrichments["ResultContainsInstructions_true"] += 1

    print()
    print(f"[ENRICHER] Total rows enriched: {total_rows}")
    print(f"[ENRICHER] Fields populated:")
    for field, count in enrichments.items():
        print(f"    {field}: {count}")
    print(f"[ENRICHER] Unique ToolDescriptionHash values: {len(unique_hashes)}")
    print(f"[ENRICHER] Of those, hashes flagged as poisoned: {len(poisoned_hashes)}")

    if len(unique_hashes) > 2:
        print()
        print("[ENRICHER] >>> HASH DRIFT DETECTED <<<")
        print("[ENRICHER] More than 2 unique hashes seen across all sessions.")
        print("[ENRICHER] This is exactly what Rule 3 (Hash Drift) detects.")


if __name__ == "__main__":
    main()