# DP-701 — Brand, domain, handle clearance and technical rename decision

Status: IN PROGRESS
Milestone: M7 — stable v1 launch
Depends on: DP-105, DP-106, DP-401, DP-402, DP-403, DP-601, and DP-603; coordinate with DP-307
Launch state: BLOCKED on external domain/handle/trademark/legal clearance and rollback rehearsal

## Problem

The owner approved **Dichiarazioni Pubbliche** as the product name on 2026-10-03, but that
is not launch clearance. The current domains, social handles, repository URL, package name,
public schema labels, and operator-facing identifiers have not been checked as one
release identity. A rename that happens after a public projection, database, source
registry, or API exists can create broken links, duplicate records, stale receipts, and
an unowned public name.

The owner also approved the technical identity DichiarazioniPubbliche.it /
dichiarazioni_pubbliche on 2026-10-03. The local and MiniPC runtime cutover is recorded
in docs/reviews/rebrand-cutover-2026-10-03.md. This does not register a domain or convert
preliminary availability signals into legal clearance.

## Outcome

Produce one owner-approved launch-identity decision packet that:

- selects the public brand or records the exact alternatives considered;
- records the qualified trademark/domain/handle disposition and its evidence date;
- fixes the canonical public name, short name, tagline, and disclosure wording;
- chooses whether the repository, Python package, database names, environment variables,
  public schema labels, and source registry need a technical rename;
- maps every existing technical identifier to a keep, deprecate, alias, or migrate
  decision;
- defines a compatibility, redirect, rollback, and re-review plan; and
- blocks DP-705 until the packet has an owner decision and no unresolved name collision.

The packet is a specification and decision record. It is not itself a trademark opinion,
domain registration, public URL, release, or production mutation.

## Baseline and evidence limits

- [`docs/21-brand-naming-v0.md`](../21-brand-naming-v0.md) records **Dichiarazioni Pubbliche** as the
  owner-approved product name and explicitly leaves registration/legal clearance open.
- The preliminary DNS, WHOIS, and same-space observations in that note are leads, not
  legal clearance or a reservation.
- The canonical public source remote is
  `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`. Package, web metadata,
  runtime units, database and production projection use the approved technical identity.
- M1 and M4 contracts are not closed in the current checkout. A technical rename cannot
  be treated as independent of DP-106, DP-601, DP-105, and the hosting/API contracts.
- No files named `W0S`, `W0R`, or `W0O` were found in this checkout. If the coordinator
  has external milestone reports, record their stable identifiers and hashes here before
  closing this ticket; do not invent a path or result.
- The owner naming decision and local technical rename are approved. Qualified trademark
  review, domain registration/ownership, and handle ownership remain `EXTERNAL` and are not assumed.

## Scope

### 1. Decision packet

Create a versioned decision record with, at minimum:

- `decision_id`, date, owner, reviewers, jurisdiction, and deployment assumptions;
- selected brand, alternate names, rejected names, and rationale;
- intended use, audience, product surfaces, and prohibited claims about the name;
- public name, repository/remote label, package/CLI label, schema/policy label, and
  operator display-name mapping;
- trademark classes/searches performed, evidence dates, and qualified disposition;
- domain and social/GitHub handle candidates, current status, and reservation action;
- technical rename scope and explicitly excluded renames;
- compatibility window, deprecation aliases, redirect behavior, and rollback owner;
- re-review triggers for source, product, jurisdiction, and public-copy changes; and
- unresolved decisions with `PENDING-OWNER`, `EXTERNAL`, or `BLOCKED` classification.

A generic search result, DNS response, social availability check, or model-generated
name list cannot close a row.

### 2. Clearance evidence handoff

The packet must request and index the following evidence from the owner or qualified
reviewer without copying privileged material into Git:

- professional trademark search and disposition for the intended classes and
  jurisdictions;
- domain and handle availability/reservation evidence for the selected launch identity;
- conflict review against existing project names, package names, public handles, and
  planned URLs;
- legal/editorial acceptance of the public description and any required trademark or
  attribution notice; and
- the date and scope of the next re-review.

Until the external evidence is present, keep the approved internal technical identity,
do not claim domain/handle ownership or expose an unregistered URL as production, and
keep the public launch gate closed.

### 3. Technical rename impact map

The decision must cover, without editing them in this ticket:

- repository directory and remote label;
- `dichiarazioni_pubbliche` import and `python -m` commands;
- `dichiarazioni-pubbliche` distribution metadata;
- `db/schema.v1.sql`, ordered migrations, and persisted IDs;
- environment variables, systemd units, user-agent strings, and private artifact paths;
- public schema/API examples, OpenAPI identifiers, and projection fingerprints;
- source registry IDs, fixture paths, research receipts, and documentation links; and
- correction, reply, and release receipts that must remain readable across a rename.

Each item must be classified `KEEP`, `ALIAS`, `MIGRATE`, or `DEFER`, with an owner and
an acceptance test. A rename is not complete when only the README changes.

### 4. Compatibility and rollback

If a rename is approved, the follow-up implementation must provide:

- an additive or explicitly ordered migration plan with replay proof in an isolated
  database;
- old-to-new identifier mapping for reads, receipts, URLs, and operational diagnostics;
- a deprecation window for imports, package metadata, environment names, and public links;
- redirect behavior that does not weaken public projection or review gates;
- a rollback receipt with before/after hashes, affected artifacts, restore procedure,
  operator, date, and verification result; and
- a correction/superseding record for material changes rather than silent rewriting.

No compatibility shim, alias, redirect, archive, or backup may be described as a
rollback receipt unless it is actually exercised and read back.

## Non-goals

- performing a trademark search, legal opinion, domain purchase, handle registration, or
  public availability claim on behalf of the owner;
- choosing a final logo, visual identity, or slogan without the owner decision;
- renaming the repository, package, database, schema files, environment variables, or
  public identifiers in this specification;
- creating a Git remote, tag, release, website, or public deployment;
- selecting a CDN, hosting vendor, registry, or signing authority;
- changing publication, evidence, speaker, privacy, or provider semantics; or
- using a preliminary availability signal as legal clearance.

## Invariants

- A public name is not a person, truth score, political ranking, or reliability claim.
- The brand decision cannot weaken provenance, no-intent, privacy, rights, or
  fail-closed publication rules.
- Provider failure, missing legal evidence, and unresolved name ownership remain
  explicit blockers.
- Existing public history is versioned; a rename does not silently rewrite findings or
  correction/reply receipts.
- Mac evidence is development evidence; any runtime or deployment claim requires the
  MiniPC authority defined by ADR 0004.
- No public URL, package, tag, or external artifact is created by this ticket.

## Launch blockers and exact unblock actions

| ID | Blocker | Exact unblock action | Evidence required | Owner/state |
|---|---|---|---|---|
| B-701-01 | Owner-approved public identity | **CLOSED 2026-10-03:** owner selected **Dichiarazioni Pubbliche**. | This decision record + repository cutover. | Product owner; `CLOSED` |
| B-701-02 | Trademark/name clearance absent | Commission and record the qualified trademark search/disposition for intended classes and jurisdictions. | Reviewer identity, scope, search date, sources, disposition, and conditions. | Qualified reviewer; `EXTERNAL` |
| B-701-03 | Domain purchase reported; DNS/handles evidence incomplete | **Owner-reported 2026-10-05:** `dichiarazionipubbliche.it` was purchased at Dynadot. As of 2026-10-06 the public DNS lookup returns no A, AAAA or NS record, and social-handle reservation evidence is still absent. Preserve the registrar receipt outside Git, configure the owner-approved DNS path, and record handle disposition before launch. | Controlled registrar ownership/expiry reference plus DNS and handle read-back; no secret data. | Product owner; `EXTERNAL` (partial evidence only) |
| B-701-04 | Technical rename decision | **CLOSED 2026-10-03:** repo/package/ticket/systemd/env/database/data paths and public projection migrated on Mac + MiniPC. | docs/reviews/rebrand-cutover-2026-10-03.md. | Maintainer + owner; CLOSED |
| B-701-05 | Name or URL collision possible | Run the read-only collision audit against repository metadata, public projection/API identifiers, package names, domains, handles, and source receipts. | Machine-readable audit output and manual disposition of every collision. | Maintainer; `BLOCKED` until clean |
| B-701-06 | Legal/public copy not accepted | Obtain DP-307 disposition for the selected name, description, disclosure, and launch surfaces. | Accepted Q-306/DP-307 decision ID and policy version. | Owner + counsel; `EXTERNAL` |
| B-701-07 | Rollback path unproven | If any rename/mapping is approved, rehearse the old-to-new mapping and rollback in an isolated environment. | Rollback receipt with hashes, restore read-back, and operator sign-off. | Maintainer; `BLOCKED` |

A blocker may be marked closed only when its evidence is linked and the owner accepts the
result. “No collision found” is not a legal clearance.

## Acceptance criteria

- [ ] **AC-701.1 — Decision packet:** A versioned packet records the selected brand,
  alternatives, rationale, jurisdiction, intended use, prohibited claims, reviewer, date,
  and re-review trigger.
- [ ] **AC-701.2 — Qualified disposition:** The packet links controlled evidence for
  trademark/name review and domain/handle decisions; preliminary DNS, WHOIS, or social
  checks are labeled only as preliminary observations.
- [ ] **AC-701.3 — Identity consistency:** The selected public name is mapped to every
  in-scope display, documentation, package, schema/API, source, and receipt surface, with
  an explicit decision for each surface.
- [ ] **AC-701.4 — Technical impact:** No rename is hidden in a documentation-only change.
  Every proposed rename has an owner, compatibility window, migration/test seam, and
  rollback classification.
- [ ] **AC-701.5 — Collision audit:** A deterministic audit finds no duplicate ticket
  IDs, filename IDs, public identifiers, package names, domains, handles, or unresolved
  launch-name claims. Every manual collision has a disposition.
- [ ] **AC-701.6 — Safety review:** The packet states that the brand decision cannot alter
  no-intent, privacy, rights, provenance, provider, or publication gates.
- [ ] **AC-701.7 — Compatibility proof:** If an alias or migration is approved, an
  isolated read/replay/rollback can read both identifiers, preserve receipts, and restore
  the prior state with a durable receipt.
- [ ] **AC-701.8 — Legal handoff:** DP-307/DP-306 records the accepted launch-name and
  disclosure decision, or the ticket remains `BLOCKED` with the exact safe default.
- [ ] **AC-701.9 — No external side effect:** The implementation creates no remote, URL,
  domain registration, handle, tag, release, deployment, or public brand claim.
- [ ] **AC-701.10 — Handoff:** DP-704 can consume the identity/rollback map, and DP-705
  cannot claim stable v1 while any B-701 row remains open.

## Validation / proof

The implementation receipt must record the exact candidate commit and run:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run build
cd .. && git diff --check
```

It must also run a read-only dependency/collision audit for `DP-701..DP-705` that checks
unique IDs and filenames, required sections, known dependency references, cycles, and
cross-ticket ownership. The audit must distinguish an absent external report from a
failed report and must not treat an unverified URL as evidence.

If a name mapping is implemented later, the receipt must include a detached clean-clone
run, isolated migration apply/replay where applicable, MiniPC mirror hash, public/private
read-back, and the rollback receipt described above. A documentation-only decision can
use link, syntax, and `git diff --check` proof, but cannot claim runtime or legal
completion.

## Documentation, data, and migration impact

- Add the decision packet and evidence index through the owning documentation change.
- Do not edit `PLAN.md`, rename files, or change package/database metadata in this ticket.
- A later approved rename may require additive migrations, aliases, redirects, or
  deprecation notices, but those changes require their own implementation ticket,
  compatibility tests, and MiniPC proof.
- Preserve historical receipts and public finding versions. Do not delete or rewrite a
  record merely to make a new name appear consistent.
- Keep trademarks, domains, handles, source terms, and third-party data outside the
  Apache-2.0 code-license grant.

## Completion receipt

Owner identity plus local and MiniPC technical cutover are complete. The owner subsequently
reported purchasing `dichiarazionipubbliche.it` at Dynadot on 2026-10-05; this is useful
ownership context but is not treated as a repository-contained registrar receipt or legal
clearance. A 2026-10-06 read-only DNS check returned no A, AAAA or NS records, so the domain
is not yet a verified public deployment path. Pending qualified trademark review, controlled
domain/handle evidence, collision audit, legal handoff, DNS/public-host read-back, and
exercised rollback proof. This ticket does not claim brand clearance or stable v1 readiness.
