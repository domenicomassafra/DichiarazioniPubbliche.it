#!/bin/sh
# Dichiarazioni Pubbliche backup (DP-502).
#
# Stdlib + PostgreSQL client tools only. No new infrastructure: this is a
# cron/systemd-timer friendly script writing into a private backup root.
#
# Usage:
#   deploy/ops/backup.sh BACKUP_ROOT [DATABASE_URL]
#
# Environment (or argv):
#   DICHIARAZIONI_PUBBLICHE_DATABASE_URL  libpq connection string
#   DICHIARAZIONI_PUBBLICHE_BACKUP_KEEP   number of backup sets to keep (default 7)
#
# Backups contain the same private transcript/evidence data as the live store.
# They are written 0600 into a 0700 root, never into the repository, and never
# into the public projection directory.

set -eu

BACKUP_ROOT=${1:-${DICHIARAZIONI_PUBBLICHE_BACKUP_ROOT:-$HOME/.local/share/dichiarazioni-pubbliche-backups}}
DATABASE_URL=${2:-${DICHIARAZIONI_PUBBLICHE_DATABASE_URL:-}}
KEEP=${DICHIARAZIONI_PUBBLICHE_BACKUP_KEEP:-7}

if [ -z "$DATABASE_URL" ]; then
    echo "BACKUP FAILED: no database url (set DICHIARAZIONI_PUBBLICHE_DATABASE_URL)" >&2
    exit 2
fi

case "$KEEP" in
    ''|*[!0-9]*|0)
        echo "BACKUP FAILED: DICHIARAZIONI_PUBBLICHE_BACKUP_KEEP must be an integer >= 1" >&2
        exit 2
        ;;
esac

for tool in pg_dump psql pg_restore sha256sum; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "BACKUP FAILED: required tool not found: $tool" >&2
        exit 2
    fi
done

umask 077
mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"

STAMP_BASE=$(date -u +%Y%m%dT%H%M%SZ)
STAMP=$STAMP_BASE
SET_DIR="$BACKUP_ROOT/$STAMP"
suffix=0
while [ -e "$SET_DIR" ]; do
    suffix=$((suffix + 1))
    STAMP=$(printf '%s-%03d' "$STAMP_BASE" "$suffix")
    SET_DIR="$BACKUP_ROOT/$STAMP"
done
mkdir "$SET_DIR"
chmod 700 "$SET_DIR"

echo "BACKUP root=$BACKUP_ROOT set=$STAMP"

# Custom-format dump: compressed, restorable, and lets pg_restore report
# per-object errors instead of aborting the whole restore on the first one.
pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --no-privileges \
    --file="$SET_DIR/dichiarazioni_pubbliche.dump"

if [ ! -s "$SET_DIR/dichiarazioni_pubbliche.dump" ]; then
    echo "BACKUP FAILED: dump file is empty: $SET_DIR/dichiarazioni_pubbliche.dump" >&2
    exit 1
fi

# Row-count manifest taken from the live database at backup time. The restore
# drill compares these against the restored database; it never re-derives them
# from the restored side.
TABLES="source person content_item content_locator content_capture capture_lifecycle_event research_collection \
research_collection_content research_discovery_manifest research_discovery_query research_discovery_run \
research_discovery_attempt research_discovery_hit content_derivation_family content_derivation_candidate \
proposition_cluster proposition_cluster_member topic topic_alias event event_alias organization_alias \
candidate_match_run candidate_match_result \
entity_identifier entity_resolution_candidate passage statement_candidate statement_candidate_passage \
claim_candidate claim_candidate_promotion candidate_extraction_run entity_mention_candidate \
source_profile source_evidence_role source_authority_scope source_relation \
evidence_requirement_profile evidence_requirement_rule evidence_set_assessment \
appearance transcript_variant transcript_segment canonical_transcript_segment \
atomic_claim claim_segment claim_text_provenance evidence claim_evidence_candidate \
evidence_observation verification_run inference_candidate review_event finding finding_evidence \
coverage_need coverage_need_event \
provider_receipt processing_job speaker_identity_candidate"

{
    echo "{"
    echo "  \"set\": \"$STAMP\","
    echo "  \"tables\": {"
    first=1
    for table in $TABLES; do
        count=$(psql --dbname="$DATABASE_URL" --no-align --tuples-only \
            --command="SELECT count(*) FROM $table" 2>/dev/null || echo "null")
        if [ "$first" -eq 1 ]; then first=0; else echo ","; fi
        printf '    "%s": %s' "$table" "$count"
    done
    echo ""
    echo "  }"
    echo "}"
} > "$SET_DIR/manifest.json"

# The public projection bundle, when one exists, is backed up verbatim. It is
# a projection: it is *verified* against the restored database by the drill, but
# it is never regenerated as a substitute for a restore.
if [ -n "${DICHIARAZIONI_PUBBLICHE_PUBLIC_BUNDLE:-}" ] && [ -d "$DICHIARAZIONI_PUBBLICHE_PUBLIC_BUNDLE" ]; then
    cp -a "$DICHIARAZIONI_PUBBLICHE_PUBLIC_BUNDLE" "$SET_DIR/public-bundle"
    # Keep the owner bit, drop everyone else. `chmod -R go-rwx` would also strip
    # the owner execute bit, turning the directories unreadable and making the
    # bundle look corrupt to the restore drill.
    chmod -R u+rwX,go-rwx "$SET_DIR/public-bundle"
    if [ ! -f "$SET_DIR/public-bundle/index.json" ]; then
        echo "BACKUP FAILED: public bundle has no index.json" >&2
        exit 1
    fi
    sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("dataset_sha256",""))' \
        "$SET_DIR/public-bundle/index.json" 2>/dev/null || echo "")
    if [ -z "$sha" ]; then
        echo "BACKUP FAILED: public bundle index.json has no readable dataset_sha256" >&2
        exit 1
    fi
    printf '%s' "$sha" > "$SET_DIR/public-bundle.sha256"
fi

# A backup is only useful if it is readable back. Verify the dump's table of
# contents now rather than discovering corruption during an outage.
if ! pg_restore --list "$SET_DIR/dichiarazioni_pubbliche.dump" >/dev/null 2>&1; then
    echo "BACKUP FAILED: dump is not readable (pg_restore --list failed)" >&2
    exit 1
fi

sha256sum "$SET_DIR/dichiarazioni_pubbliche.dump" > "$SET_DIR/dichiarazioni_pubbliche.dump.sha256"

# Private by default: files 0600, directories 0700. A blanket `chmod 600` over
# the set directory would strip the execute bit from the subdirectories and
# make the whole backup unreadable.
chmod 600 "$SET_DIR"/*.dump "$SET_DIR"/*.sha256 "$SET_DIR"/manifest.json 2>/dev/null || true
chmod 700 "$SET_DIR/public-bundle" "$SET_DIR/drill" 2>/dev/null || true

# Rotation by count. Glob expansion is oldest -> newest for the timestamped
# names used here. Compute the excess first, then remove that many oldest valid
# sets. Never delete the set just created.
count=0
for dir in "$BACKUP_ROOT"/2*; do
    [ -d "$dir" ] || continue
    [ -s "$dir/dichiarazioni_pubbliche.dump" ] || continue
    count=$((count + 1))
done

remove_count=$((count - KEEP))
if [ "$remove_count" -gt 0 ]; then
    for dir in "$BACKUP_ROOT"/2*; do
        [ "$remove_count" -gt 0 ] || break
        [ -d "$dir" ] || continue
        [ -s "$dir/dichiarazioni_pubbliche.dump" ] || continue
        if [ "$dir" = "$SET_DIR" ]; then
            echo "BACKUP FAILED: rotation selected the backup set just created" >&2
            exit 1
        fi
        echo "BACKUP rotate removing $dir"
        rm -rf "$dir"
        remove_count=$((remove_count - 1))
        count=$((count - 1))
    done
fi

# Fail closed: a successful backup may never report OK if its own dump vanished
# or became unreadable during rotation.
if [ ! -s "$SET_DIR/dichiarazioni_pubbliche.dump" ]; then
    echo "BACKUP FAILED: current dump missing after rotation: $SET_DIR/dichiarazioni_pubbliche.dump" >&2
    exit 1
fi
if ! pg_restore --list "$SET_DIR/dichiarazioni_pubbliche.dump" >/dev/null 2>&1; then
    echo "BACKUP FAILED: current dump unreadable after rotation" >&2
    exit 1
fi

dump_bytes=$(wc -c < "$SET_DIR/dichiarazioni_pubbliche.dump" | tr -d ' ')
echo "BACKUP OK set=$STAMP dump_bytes=$dump_bytes sets_kept=$count"
