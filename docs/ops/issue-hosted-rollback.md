# DP-606 — Hosted labels: read-only backup and rollback preparation

Authority: `.github/labels.v1.json`, `.github/triage-policy.v1.json`,
and the repository-local `PLAN.md` tickets. No issue/project/label
synchronization has been authorized or enabled.

## Safe operator procedure (does not mutate GitHub)

1. Read the public repository's existing labels into a **new** snapshot,
   stored outside the Git checkout:

   `python3 tools/issue_label_rollback.py --capture-live --output-snapshot /tmp/dp606-labels-before.json > /tmp/dp606-plan.json`

   The snapshot is created owner-only (0600) and will **not** overwrite a
   previous backup. Do not commit it; it captures live hosted state.
   The tool invokes only `gh api` GET on the canonical repository. It
   does **not** alter hosted state or read issue bodies/security reports.

2. Reproduce the proposal offline:

   `python3 tools/issue_label_rollback.py --snapshot-file /tmp/dp606-labels-before.json`

   Compare the `before_sha256`, `proposed_sha256`,
   `rollback_sha256`, `change_count` and proposed actions. The
   `rollback_matches_before` field must be true. The plan adds or
   updates public-allowed manifest labels while preserving unrelated
   hosted labels; it never creates `security-private` or deletes
   an existing label.

3. Before any future **separately authorized** hosted change, freeze
   the snapshot and review every conflict (same-name label, color,
   description). Record the actor, scope, exact GitHub label IDs,
   project IDs, branch-protection/ruleset state, and rollback authority.
   Verify owner/administrator approval for **that exact mutation**.
   A dry-run cannot authorize the hosted operation itself.

4. If a later approved setup must roll back, first disable its
   automation. Compare the current host against the baseline and the
   accepted change receipt. Restore changed pre-existing labels'
   original color/description, remove **only** newly-created labels
   that are confirmed unreferenced and within the mutation receipt,
   and restore each separately approved project/branch policy from its
   own verified backup. Never bulk-delete unknown or manually-edited
   labels. Re-read hosted state and require the baseline digest or a
   reviewed, documented conflict before declaring rollback completed.

The script intentionally has no write/replay mode. This keeps the
prepared proposal separate from authorization and applies the
project's fail-closed policy when the host changes between backup
and execution.

## Read-only hosted observation — 2026-10-09

Against `domenicomassafra/DichiarazioniPubbliche.it`, an actual
GitHub API read found **10** existing labels. The public manifest
proposes **22** create/update actions and leaves a simulated
**30**-label state. Its rollback simulation reproduced the canonical
pre-change SHA-256 exactly:
`3f6e9c18359be9764fa59ceb80f355ebae4346630cf7e8b8b913da15e6f25106`.
The backup and plan were saved only outside Git. No hosted mutation
occurred; branch-protection and project backups/rollback have **not**
been accepted by the owner.

The regression tests cover duplicates, malformed hosted names/colors,
invalid manifests, omitted private-security labels, preservation of
unowned existing labels and the read-only GitHub pagination seam.

This is preparatory AC-606.10 evidence **not full acceptance**.
DP-606 remains IN PROGRESS until the exact authorized hosted
setup/export/rollback and protection policy are accepted.
