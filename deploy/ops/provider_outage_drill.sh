#!/bin/sh
# Dichiarazioni Pubbliche provider-outage drill (DP-506).
#
# Simulates a total provider outage against a throwaway database and asserts the
# system degrades to an explicit BLOCKED state rather than silently lowering
# quality. This is a hard product invariant, so the drill asserts the negative
# cases, not just the positive one:
#
#   1. jobs end BLOCKED (not COMPLETED, not retried forever);
#   2. no provider_receipt is written with a SUCCESS status;
#   3. no atomic_claim is created;
#   4. no finding changes publication_status;
#   5. estimated cost stays at zero.
#
# Usage:
#   deploy/ops/provider_outage_drill.sh --database-url URL [options]
#
# Options:
#   --database-url URL   throwaway database to run the drill in (required)
#   --registry PATH      source registry (default: config/source-registry.v1.json)
#   --outage {credential,http}   failure mode (default: credential)
#
# Exit codes:
#   0  outage handled correctly: blocked, nothing published, nothing downgraded
#   1  INVARIANT VIOLATED: a degraded path produced output
#   2  drill could not run -- BLOCKED, not failed

set -eu

DATABASE_URL=""
REGISTRY=""
OUTAGE=credential
WORKERS=2

while [ $# -gt 0 ]; do
    case "$1" in
        --database-url) DATABASE_URL=${2:-}; shift 2 ;;
        --registry)     REGISTRY=${2:-};     shift 2 ;;
        --outage)       OUTAGE=${2:-};       shift 2 ;;
        *) echo "provider_outage_drill: unknown option $1" >&2; exit 2 ;;
    esac
done

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)

if [ -z "$DATABASE_URL" ]; then
    echo "DRILL BLOCKED: --database-url is required" >&2
    exit 2
fi
if [ -z "$REGISTRY" ]; then
    REGISTRY="$REPO_ROOT/config/source-registry.v1.json"
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "DRILL BLOCKED: python3 not found" >&2
    exit 2
fi

case "$OUTAGE" in
    credential|http) ;;
    *) echo "DRILL BLOCKED: unknown --outage mode '$OUTAGE'" >&2; exit 2 ;;
esac

echo "DRILL mode=$OUTAGE"

# The drill runs the *real* worker daemon against the throwaway database, with
# a claim client that fails the way a real outage fails. Nothing about the
# worker is stubbed: the same ProcessWorker.run() path, the same budget
# preflight, the same blocked-job bookkeeping.
PYTHONPATH="$REPO_ROOT/poc" python3 -m dichiarazioni_pubbliche.ops.provider_outage_drill \
    --database-url "$DATABASE_URL" \
    --registry "$REGISTRY" \
    --outage "$OUTAGE" \
    --runs "$WORKERS"
