# DP-606 — Public issue labels and project automation after a remote exists

Status: IN PROGRESS
Milestone: M6 — open-source and release hardening
Depends on: DP-001, a confirmed canonical remote, owner authorization, and the repository governance/security contracts
Launch state: BLOCKED on owner-approved hosted visibility, maintainer/security ownership, permission scopes, and hosted dry-run; the canonical remote is confirmed

## Problem

The repository has local issue templates and repo-local ticket IDs, and the canonical
GitHub remote is configured. A label scheme, project board, triage automation,
or branch/issue policy cannot be truthfully installed or verified without knowing the
canonical hosting platform, repository visibility, owner, and security boundary. Guessing
a remote URL or creating external issues would turn a repository-local planning task into
an unauthorized publication or governance change.

Once a remote is confirmed, contributors need a small, auditable workflow that routes
bugs, proposals, security-sensitive reports, and ticket-linked work without allowing an
automation to publish a finding, merge code, close a legal blocker, or expose private
data.

## Outcome

After the owner confirms the canonical remote, define and apply a minimal public issue
and project workflow that:

- uses the same `DP-###` ticket vocabulary as `PLAN.md` and `docs/tickets/`;
- keeps security reports on the private path in `SECURITY.md`;
- uses explicit labels/statuses for triage, blocked dependencies, and milestone/release
  context;
- keeps automation read-only or non-destructive by default; and
- preserves repo-local tickets and durable audit history when the remote changes or is
  retired.

This ticket specifies the future setup. It does not create a remote, issue, project,
label, webhook, or external publication.

## Baseline and evidence limits

Current baseline:

- `.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`, and
  `config.yml` exist in the checkout;
- blank issues are disabled and the templates request sanitized provenance and invariant
  checkboxes;
- `.github/pull_request_template.md` requires ticket/spec, validation, safety, and
  MiniPC/runtime fields;
- `PLAN.md` and `docs/tickets/README.md` remain the canonical backlog until a public
  tracker is explicitly linked; and
- the canonical GitHub remote is `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`.

The templates do not prove that labels, project automation, visibility, or issue
sync exist. No file named W0R/W0P or separate DP-601 baseline was present in this
checkout; that evidence gap must be verified before setup.

## Remote decision gate

Before any external mutation, record:

- the canonical hosting platform and repository identifier supplied by the owner;
- whether the repository is public, private, or intentionally undecided;
- the owner/maintainer account or role that controls labels/projects/automation;
- the private security-reporting channel and its response owner;
- the initial milestone/ticket synchronization policy; and
- the exact permission level required for read, triage, label, project, and automation
  actions.

Do not infer any of these from a Git directory name, a generic `<repository-url>`, or a
provider login. If the remote is not confirmed, the safe state is `PENDING-REMOTE` and
the repo-local tickets remain authoritative.

## Scope

### 1. Issue and label contract

The implementation should use a versioned label manifest, for example
`.github/labels.yml`, with a stable label ID, display name, description, color, and
allowed transitions. The initial vocabulary should be small and auditable:

- type: `bug`, `proposal`, `documentation`, `security-private`, `maintenance`;
- state: `needs-triage`, `ready`, `in-progress`, `blocked`, `needs-owner`, `closed`;
- area: `backend`, `web`, `data`, `docs`, `security`, `release`;
- contract/risk: `public-contract`, `migration`, `rights-review`, `runtime-proof`,
  `no-auto-publication`;
- contribution: `good-first-issue` only when the maintainer has supplied a bounded,
  reproducible task.

The manifest must define which labels are mutually exclusive, which are automatically
suggested, and which require human action. It must not use a label to imply a person
score, political priority, legal approval, or truth verdict.

Every public issue title should begin with `DP-###:` when a repo-local ticket exists,
or use the owner-approved external issue ID. A body must link the exact ticket path or
controlled issue identifier and must not paste secrets, raw transcripts, private
evidence, or personal data. The security template must direct reporters to
`SECURITY.md` and must not solicit a public issue for a vulnerability.

### 2. Project and triage automation

The project view should represent the existing milestone graph, not create a competing
backlog. At minimum, automation may:

- apply a bounded type/area suggestion from the issue form;
- add `needs-triage` to a new issue;
- link an issue to an existing `DP-###` ticket when the owner-approved synchronization
  process runs;
- move an item to `blocked` when a named dependency or owner/legal decision is recorded;
- add a release/milestone label only from an accepted DP-604 version decision; and
- notify the configured owner through the platform's native mechanism without including
  private issue content in a public channel.

Automation must not:

- auto-close, auto-merge, auto-publish, auto-approve evidence, or auto-approve a
  Finding;
- infer legal, rights, security, or publication status from labels or comments;
- fetch a URL, transcript, or evidence body from an issue body;
- expose a private issue, reviewer note, credential, or provider response;
- create a public issue from a private/security report; or
- rewrite or delete the repo-local ticket/spec source.

Every automation rule must be reviewable, bounded, and reversible. If the platform
requires an app, OAuth scope, webhook secret, or token, the credential must be stored
in the approved secret store and never in the repository.

### 3. Synchronization and archival policy

The owner-approved synchronization process must define whether public issues are links
to repo-local tickets, mirrors, or replacements. Until that decision, public issue
state cannot change the canonical `PLAN.md` status. A synchronization change must record
source ID, target ID, timestamp, and actor/receipt without copying private content.

When a ticket closes, the process must preserve the issue/ticket relationship and the
final decision link. A closed issue is not proof that code merged, that a legal gate
closed, or that a release occurred.

## Non-goals

- guessing or creating a remote, repository URL, organization, visibility, or owner;
- creating real issues, labels, projects, webhooks, or external automations now;
- replacing `PLAN.md`, `docs/tickets/`, or the canonical status vocabulary;
- opening public security reports or exposing private intake;
- automatic publication, evidence approval, verification, merge, deployment, or release;
- adding a project-management service, bot, database, or new infrastructure;
- setting response-time promises or triage policy without owner acceptance; or
- using issue labels as person rankings or political prioritization.

## Invariants

- private/security intake remains private by default;
- a public issue or label is not a Review Event, Evidence approval, publication gate, or
  legal decision;
- no automation may weaken provenance, fail-closed publication, privacy, or no-intent
  rules;
- public content is sanitized and contains no raw/private data; and
- no external state is considered proof until the owner accepts the remote and receipt.

## Acceptance criteria

- [ ] **AC-606.1 — Owner/remote gate:** Before any external setup, the canonical remote,
  platform, visibility, owner, security channel, and permission model are recorded;
  absent these, status remains `PENDING-REMOTE` and no external object is created.
- [x] **AC-606.2 — Versioned label manifest:** A checked, reviewable manifest defines
  stable label IDs, descriptions, colors, allowed transitions, and mutually exclusive
  states. Unknown labels and implicit state changes are rejected or surfaced.
- [x] **AC-606.3 — Ticket linkage:** New public issues require an `DP-###`/external issue
  linkage and sanitized reproduction/provenance fields; repo-local tickets remain the
  canonical source until an owner-approved synchronization decision says otherwise.
- [x] **AC-606.4 — Security boundary:** Security templates and automation direct
  vulnerability reports to the private `SECURITY.md` path, do not create public issues,
  and do not copy confidential report content into project metadata or logs.
- [x] **AC-606.5 — Safe automation:** All enabled rules are read-only or explicitly
  reversible, use least privilege, have bounded triggers, and cannot auto-close,
  auto-merge, auto-publish, auto-approve, or change a legal/rights state.
- [x] **AC-606.6 — CI validation:** DP-602 validates label-manifest syntax, issue/PR
  template structure, ticket-link rules, forbidden fields/secrets, and collision/
  dependency audits before any workflow is enabled. CI does not require a remote for
  local validation.
- [ ] **AC-606.7 — Clean-clone proof:** A detached clean clone can validate all templates,
  manifests, and automation definitions without credentials, provider calls, or private
  issue data. A hosted dry-run is separately classified `PENDING-REMOTE` until a remote
  exists.
- [ ] **AC-606.8 — Licensing:** Any automation app, action, or dependency is inventoried
  with exact version, license evidence, notice, and review status under DP-603. Native
  platform features are preferred when they avoid an unlicensed dependency.
- [ ] **AC-606.9 — Versioning:** Milestone/release labels are generated only from an
  accepted DP-604 version decision; CI does not bump a version or alter the changelog
  automatically.
- [ ] **AC-606.10 — Migration/rollback:** Existing repo-local tickets remain readable;
  label/project changes have a versioned manifest, an export/backup, and a rollback
  procedure. No database migration or production data change is involved.
- [x] **AC-606.11 — No publication:** This ticket does not create a remote, issue,
  project, webhook, public page, release, or external publication. Any later setup is
  a separately authorized change with a receipt.

## Validation / proof

Before a remote exists, run locally:

1. parse the label manifest, issue templates, PR template, and automation definitions;
2. run the DP-601..DP-607 ticket completeness/collision audit;
3. run the relative-link, secret/private-data, license/dependency, and version/changelog
   checks;
4. create sanitized fixture issues in a local mock/validator and prove invalid titles,
   missing ticket links, security reports, and forbidden transitions are rejected;
5. perform a detached clean-clone validation with no credentials or external calls; and
6. run the standard repository checks:

   ```text
   python3 -m compileall -q poc tests
   PYTHONPATH=poc python3 -m unittest discover -s tests -v
   PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
   git diff --check
   ```

After a remote is confirmed, the owner may run a bounded hosted dry-run using a
non-sensitive test issue/project. The receipt must record the remote identifier,
visibility, actor, permission scopes, label/project IDs, rule IDs, timestamps, and
result. It must not include a real security report or private data.

## Documentation, data, and migration impact

- Add/update the label/automation manifest and contributor documentation in the later
  authorized setup change.
- Do not edit `PLAN.md`; issue synchronization cannot silently change milestone status.
- No database migration is introduced. Project/label metadata is versioned and
  exportable; a failed setup must be rolled back or left visibly disabled.
- Update DP-603 if a third-party automation dependency is introduced.
- DP-604 owns any release/milestone version label and changelog update.
- Do not publish external issues, labels, projects, or webhooks from this specification.

## Blocked conditions

Keep the ticket `FUTURE`/`BLOCKED` or classify setup incomplete if:

- the canonical remote/platform, owner, visibility, or security channel is unconfirmed;
- owner authorization for the exact external mutations is absent;
- a proposed automation would expose private/security data or credentials;
- a label/status would be interpreted as legal, publication, truth, or person ranking;
- a third-party automation dependency lacks compatible license evidence;
- a clean clone cannot validate the definitions without secrets or external state;
- DP-604 has not approved a release/milestone label source; or
- the requested action would create a remote, issue, project, webhook, or publication
  before the gate is satisfied.

## Completion receipt

The canonical GitHub fetch/push remote is present in the checkout, but hosted visibility,
maintainer/security ownership and exact permission scopes are still intentionally unclaimed.
Local governance is now executable: `.github/labels.v1.json` defines stable label IDs,
mutually-exclusive state/type groups and a closed state transition graph;
`.github/triage-policy.v1.json` keeps `PLAN.md`/`docs/tickets` authoritative, disables remote
mutation, enumerates the small reversible suggestion set and explicitly forbids close/merge/
publish/evidence/finding/legal/rights/security-copy automation. Both public issue forms now
require an existing DP ticket linkage and direct vulnerability reports to `SECURITY.md`.

`tools/check_issue_workflow.py` validates manifests/templates and local mock issues, rejects
unknown labels, state conflicts, mismatched/missing DP IDs, public security intake and
secret/private-shaped bodies. DP-602 contributor acceptance runs this validator
unconditionally. No GitHub label, issue, project, webhook or workflow action was created.

AC-606.1 remains open for owner/visibility/security-channel/permission decisions, AC-606.7
for a committed detached clean-clone proof, AC-606.8 unless a third-party automation is ever
introduced (none is used here), AC-606.9 for an accepted release-label decision, and
AC-606.10 for hosted export/rollback proof after an owner-authorized setup.
