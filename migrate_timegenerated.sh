#!/usr/bin/env bash
# =============================================================================
#  migrate_timegenerated.sh
#  Coordinated migration: rename the WIRE field TimeGenerated -> EventTime
#  in the forwarder, so the inbound JSON no longer collides with Azure's
#  reserved TimeGenerated column. The DCR transform (deployed separately)
#  maps EventTime -> the stored TimeGenerated column.
#
#  SCOPE: 6 occurrences across 2 files (Fact 1 grep, verified content).
#    NORMALIZER.py:      lines 27, 60, ~158, ~181, ~296   (wire contract)
#    INGESTION_CLIENT.py: line ~150                        (verify probe row)
#  EXCLUDED (intentionally): DEAD_LETTER.py 171/181 (smoke-test fixture).
#
#  SAFETY: every target file has a committed baseline (commit 8273459).
#  If anything is wrong: git checkout forwarder/NORMALIZER.py
#                                     forwarder/INGESTION_CLIENT.py
#
#  This script is idempotent-safe: it asserts the OLD string exists before
#  replacing, and aborts loudly if any expected match is missing (which
#  would mean the file drifted from the verified content).
# =============================================================================
set -euo pipefail

REPO="$HOME/dev/mcp-tool-shadowing-detections"
NORM="$REPO/forwarder/NORMALIZER.py"
ING="$REPO/forwarder/INGESTION_CLIENT.py"

cd "$REPO"

echo "=== PRE-CHECK: confirm 6 TimeGenerated occurrences exist as expected ==="
norm_count=$(grep -c '"TimeGenerated"' "$NORM" || true)
ing_count=$(grep -c '"TimeGenerated"' "$ING" || true)
echo "NORMALIZER.py  \"TimeGenerated\" occurrences: $norm_count (expect 5)"
echo "INGESTION_CLIENT.py \"TimeGenerated\" occurrences: $ing_count (expect 1)"
if [ "$norm_count" -ne 5 ] || [ "$ing_count" -ne 1 ]; then
  echo "ABORT: occurrence counts do not match verified state. File drifted."
  echo "No changes made. Investigate before proceeding."
  exit 1
fi

echo ""
echo "=== APPLYING 6 EDITS ==="

# --- Helper: replace exactly one literal occurrence, assert it changed ----
replace_once () {
  local file="$1" old="$2" new="$3" label="$4"
  if ! grep -qF "$old" "$file"; then
    echo "ABORT ($label): expected text not found in $file"
    echo "Expected: $old"
    exit 1
  fi
  # Use perl for safe literal (non-regex) single replacement.
  perl -0777 -pi -e 'BEGIN{$o=shift;$n=shift} s/\Q$o\E/$n/' "$old" "$new" "$file"
  echo "  [OK] $label"
}

# Edit 1 — SCHEMA_COLUMNS wire contract (NORMALIZER ~27)
replace_once "$NORM" \
'SCHEMA_COLUMNS = [
    "TimeGenerated",' \
'SCHEMA_COLUMNS = [
    "EventTime",  # wire field; DCR transform maps -> reserved TimeGenerated column' \
"Edit 1: SCHEMA_COLUMNS"

# Edit 2 — _empty_row() template (NORMALIZER ~60)
replace_once "$NORM" \
'    return {
        "TimeGenerated": None,' \
'    return {
        "EventTime": None,' \
"Edit 2: _empty_row()"

# Edit 3 — ollmcp path comment + assignment (NORMALIZER ~155-158)
replace_once "$NORM" \
'        # TimeGenerated: ollmcp parser doesn'"'"'t capture per-event timestamps
        # so we use the forwarder'"'"'s current time at normalization
        from datetime import datetime, timezone
        row["TimeGenerated"] = datetime.now(timezone.utc).isoformat()' \
'        # EventTime: ollmcp parser doesn'"'"'t capture per-event timestamps
        # so we use the forwarder'"'"'s current time at normalization.
        # DCR transform maps this wire field -> stored TimeGenerated column.
        from datetime import datetime, timezone
        row["EventTime"] = datetime.now(timezone.utc).isoformat()' \
"Edit 3: ollmcp path"

# Edit 4 — Claude path assignment (NORMALIZER ~181)
replace_once "$NORM" \
'    row["TimeGenerated"] = event.get("timestamp")' \
'    row["EventTime"] = event.get("timestamp")  # real Claude event time; DCR maps -> TimeGenerated' \
"Edit 4: Claude path"

# Edit 5 — validate_row() required list (NORMALIZER ~296)
replace_once "$NORM" \
'    required = ["TimeGenerated", "EventType", "SessionId", "HostApp", "IngestionAgent", "SchemaVersion"]' \
'    required = ["EventTime", "EventType", "SessionId", "HostApp", "IngestionAgent", "SchemaVersion"]' \
"Edit 5: validate_row()"

# Edit 6 — verify_connection probe row (INGESTION_CLIENT ~150)
replace_once "$ING" \
'    test_row = {
        "TimeGenerated": datetime.now(timezone.utc).isoformat(),' \
'    test_row = {
        "EventTime": datetime.now(timezone.utc).isoformat(),' \
"Edit 6: verify probe row"

echo ""
echo "=== POST-CHECK: confirm rename complete ==="
norm_old=$(grep -c '"TimeGenerated"' "$NORM" || true)
ing_old=$(grep -c '"TimeGenerated"' "$ING" || true)
norm_new=$(grep -c '"EventTime"' "$NORM" || true)
ing_new=$(grep -c '"EventTime"' "$ING" || true)
echo "NORMALIZER.py  remaining \"TimeGenerated\": $norm_old (expect 0)"
echo "NORMALIZER.py  new \"EventTime\":          $norm_new (expect >=5)"
echo "INGESTION_CLIENT.py remaining \"TimeGenerated\": $ing_old (expect 0)"
echo "INGESTION_CLIENT.py new \"EventTime\":          $ing_new (expect >=1)"
if [ "$norm_old" -ne 0 ] || [ "$ing_old" -ne 0 ]; then
  echo ""
  echo "WARNING: residual \"TimeGenerated\" remains. Rename INCOMPLETE."
  echo "Review with: grep -n TimeGenerated $NORM $ING"
  echo "Revert with: git checkout forwarder/NORMALIZER.py forwarder/INGESTION_CLIENT.py"
  exit 1
fi
echo ""
echo "=== MIGRATION EDITS APPLIED CLEANLY ==="
echo "Next: python _main.py --dry-run   (must show 28 rows, 0 NORMALIZER warnings)"
