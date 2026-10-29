#!/bin/sh
# Run the real worker's provider-outage drill against a throwaway database.
# Usage: deploy/ops/provider_outage_drill.sh --database-url URL [--registry PATH] [--outage credential|http]
# Exit status: 0 pass, 1 invariant violated, 2 blocked/invalid input.

set -eu

if ! command -v python3 >/dev/null 2>&1; then
    echo "DRILL BLOCKED: python3 not found" >&2
    exit 2
fi

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)

# argparse in the Python entry point owns all option validation and defaults.
# A caller-supplied --registry overrides this repository-relative default.
PYTHONPATH="$REPO_ROOT/poc" python3 -m dichiarazioni_pubbliche.ops.provider_outage_drill \
    --registry "$REPO_ROOT/config/source-registry.v1.json" "$@"
