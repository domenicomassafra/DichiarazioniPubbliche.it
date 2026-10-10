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

## Read-only branch/ruleset/project governance export — 2026-10-10

The complementary exporter now captures the exact main-branch protection
response and **full** ruleset definitions, rather than assuming the label
backup also covered those policy objects:

`python3 tools/issue_hosted_governance_backup.py --output-snapshot /tmp/dp606-hosted-governance-20261010.json`

It uses only fixed-argument GitHub API reads, rejects repository identity
drift and incomplete ruleset pages, creates an exclusive 0600 snapshot
outside Git, and reports a digest without dumping hosted metadata. It does
not change labels, projects, protection, issues, releases, or permissions.

Actual 2026-10-10 read receipt: the public canonical repo still has **no
main-branch protection** and **zero rulesets**. Backup SHA-256 is
`74d8365e64ff5f5417b56dbce7fe229ef8c4096a80cce57566e0439cfd6e0ca1`.
Project V2 was **not** readable: the authenticated token lacks GitHub
`read:project` permission. That means `UNVERIFIED_MISSING_READ_PROJECT_SCOPE`,
**not** evidence that the repository has zero projects. The governance export
is deliberately classified **incomplete** until the owner supplies bounded
project read permission and accepts policy/rollback evidence. A read-only
backup does not count as an executed or successful rollback. Four new tests
prove identity drift, full ruleset snapshot, missing-scope fail-closed
behavior and private exclusive backups; 11 focused issue tests pass.
