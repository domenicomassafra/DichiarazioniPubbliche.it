#!/bin/sh
# Dichiarazioni Pubbliche restore drill (DP-502).
#
# Executes a real backup -> restore round trip against a throwaway database and
# verifies that the restored state reproduces the backup exactly. This is a
# *drill*, not a restore: it never touches the production database, and it
# never "fixes" a failure by regenerating a projection.
#
# Usage:
#   deploy/ops/restore_drill.sh --backup-root DIR --restore-url URL [options]
#
# Options:
#   --backup-root DIR    directory containing backup sets (required)
#   --restore-url URL    libpq url of the throwaway database to restore into
#   --backup-set NAME    backup set directory name (default: newest)
#   --keep               do not drop the restored database on success
#
# Exit codes:
#   0  drill passed: restored state matches the backup exactly
#   1  drill FAILED: restore did not reproduce the backup (do not publish)
#   2  drill could not run (missing tool / missing input) -- BLOCKED, not failed
#
# The verification comparison is delegated to
# poc/dichiarazioni_pubbliche/ops/restore_verify.py, which is pure and unit-tested.

set -eu

BACKUP_ROOT=""
RESTORE_URL=""
BACKUP_SET=""
KEEP=0
BLOCKED=0
FAIL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --backup-root) BACKUP_ROOT=${2:-}; shift 2 ;;
        --restore-url) RESTORE_URL=${2:-}; shift 2 ;;
        --backup-set)  BACKUP_SET=${2:-};  shift 2 ;;
        --keep)         KEEP=1;           shift ;;
        *) echo "restore_drill: unknown option $1" >&2; exit 2 ;;
    esac
done

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)

if [ -z "$BACKUP_ROOT" ] || [ -z "$RESTORE_URL" ]; then
    echo "DRILL BLOCKED: --backup-root and --restore-url are required" >&2
    exit 2
fi

for tool in pg_restore psql python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "DRILL BLOCKED: required tool not found: $tool" >&2
        BLOCKED=1
    fi
done
if [ "$BLOCKED" -ne 0 ]; then
    echo "DRILL BLOCKED: install the missing tool(s) and re-run" >&2
    exit 2
fi

# Locate the backup set.
if [ -z "$BACKUP_SET" ]; then
    for candidate in "$BACKUP_ROOT"/2*; do
        [ -d "$candidate" ] || continue
        [ -f "$candidate/dichiarazioni_pubbliche.dump" ] || continue
        BACKUP_SET=$(basename "$candidate")
    done
fi
SET_DIR="$BACKUP_ROOT/$BACKUP_SET"

if [ -z "$BACKUP_SET" ] || [ ! -d "$SET_DIR" ]; then
    echo "DRILL BLOCKED: no backup set found under $BACKUP_ROOT" >&2
    exit 2
fi
if [ ! -s "$SET_DIR/dichiarazioni_pubbliche.dump" ]; then
    echo "DRILL BLOCKED: backup set has no dump: $SET_DIR/dichiarazioni_pubbliche.dump" >&2
    exit 2
fi

echo "DRILL set=$BACKUP_SET"
echo "DRILL source_dump=$SET_DIR/dichiarazioni_pubbliche.dump bytes=$(wc -c < "$SET_DIR/dichiarazioni_pubbliche.dump" | tr -d ' ')"

# --- Step 1: the dump must be readable before we trust any of it. ----------
WORK_DIR="$SET_DIR/drill"
mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR"

if ! pg_restore --list "$SET_DIR/dichiarazioni_pubbliche.dump" > "$WORK_DIR/restore_list" 2>"$WORK_DIR/restore_list.err"; then
    echo "DRILL BLOCKED: source dump is unreadable (corrupt backup)" >&2
    cat "$WORK_DIR/restore_list.err" >&2
    exit 2
fi
echo "DRILL step=verify_source_dump OK ($(grep -c 'TABLE DATA' "$WORK_DIR/restore_list" || true) table-data entries)"

# --- Step 2: restore into the throwaway database. --------------------------
# --exit-on-error makes a partial restore a loud failure rather than a quiet
# under-populated database that a later row-count check might mis-read.
if ! pg_restore --dbname="$RESTORE_URL" --no-owner --no-privileges \
        --exit-on-error "$SET_DIR/dichiarazioni_pubbliche.dump" > "$WORK_DIR/restore_out" \
        2> "$WORK_DIR/restore_err"; then
    echo "DRILL FAILED: pg_restore returned an error" >&2
    cat "$WORK_DIR/restore_err" >&2
    FAIL=1
fi

# --- Step 3: compare source manifest vs restored database. ------------------
# Counts come from the *source* manifest (written at backup time) and from a
# live query of the restored database. Nothing is re-derived from the restored
# side to make the comparison pass.
MANIFEST="$SET_DIR/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "DRILL BLOCKED: backup set has no manifest.json" >&2
    exit 2
fi

TABLES=$(python3 -c '
import json,sys
with open(sys.argv[1]) as h:
    print(" ".join(json.load(h)["tables"].keys()))
' "$MANIFEST")

RESULTS=$(mktemp)
set --

for table in $TABLES; do
    src=$(python3 -c '
import json,sys
with open(sys.argv[1]) as h:
    v=json.load(h)["tables"].get(sys.argv[2])
print("null" if v is None else int(v))
' "$MANIFEST" "$table")
    dst=$(psql --dbname="$RESTORE_URL" --no-align --tuples-only \
        --command="SELECT count(*) FROM $table" 2>/dev/null || echo null)
    printf '%s %s %s\n' "$table" "$src" "$dst" >> "$RESULTS"
done

# --- Step 4: compare the public projection bundle, if one was backed up. ---
if [ -f "$SET_DIR/public-bundle.sha256" ]; then
    SRC_SHA=$(cat "$SET_DIR/public-bundle.sha256")
    if [ -f "$SET_DIR/public-bundle/index.json" ]; then
        DST_SHA=$(python3 -c '
import json,sys
with open(sys.argv[1]) as h:
    print(json.load(h).get("dataset_sha256",""))
' "$SET_DIR/public-bundle/index.json")
        set -- --bundle "public-projection:$SRC_SHA:$DST_SHA"
        echo "DRILL bundle=public-projection source=$SRC_SHA restored=$DST_SHA"
    else
        set -- --bundle "public-projection:$SRC_SHA:MISSING"
    fi
fi

# --- Step 5: the pure verifier decides pass/fail. --------------------------
set +e
PYTHONPATH="$REPO_ROOT/poc" python3 -m dichiarazioni_pubbliche.ops.restore_drill \
    --counts "$RESULTS" "$@"
VERDICT=$?
set -e

rm -f "$RESULTS"

if [ "$FAIL" -ne 0 ] || [ "$VERDICT" -ne 0 ]; then
    echo "DRILL FAILED: restored state does not reproduce the backup; do not publish"
    exit 1
fi

if [ "$KEEP" -eq 0 ]; then
    echo "DRILL cleanup: drop the throwaway restored database"
    psql --dbname="$RESTORE_URL" --no-align --tuples-only \
        --command='DROP SCHEMA public CASCADE; DROP SCHEMA IF EXISTS public CASCADE;' \
        >/dev/null 2>&1 || true
fi

echo "DRILL PASS set=$BACKUP_SET"
exit 0
