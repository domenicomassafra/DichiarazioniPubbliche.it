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
| B-701-03 | Domain purchase reported; registrar/handle evidence incomplete | **Owner-reported 2026-10-05:** `dichiarazionipubbliche.it` was purchased at Dynadot. Fresh 2026-10-06 read-back now proves authoritative Cloudflare delegation (`candy.ns.cloudflare.com`, `kanye.ns.cloudflare.com`), proxied apex and `www` resolution, HTTPS `200` on the apex, and `www` `308` redirect to the canonical apex. Preserve the controlled registrar ownership/expiry receipt outside Git and record social-handle disposition before launch. | Controlled registrar ownership/expiry reference, current DNS/public-host read-back, and handle disposition; no secret data. | Product owner; `EXTERNAL` (DNS/public-host portion closed; registrar/handles still open) |
| B-701-04 | Technical rename decision | **CLOSED 2026-10-03:** repo/package/ticket/systemd/env/database/data paths and public projection migrated on Mac + MiniPC. | docs/reviews/rebrand-cutover-2026-10-03.md. | Maintainer + owner; CLOSED |
| B-701-05 | Name or URL collision possible | **Repository/public-route machine portion hardened and green on `2dfd323`; external package/domain/handle/manual disposition remains open.** Complete the read-only collision audit for those external namespaces and disposition every result. | Machine-readable audit output and manual disposition of every collision. | Maintainer; `BLOCKED` on external/manual collision disposition |
| B-701-06 | Legal/public copy not accepted | Obtain DP-307 disposition for the selected name, description, disclosure, and launch surfaces. | Accepted Q-306/DP-307 decision ID and policy version. | Owner + counsel; `EXTERNAL` |
| B-701-07 | Rebrand rollback path cannot currently be exercised | The temporary 2026-10-03 rename-era rollback bundle was deliberately deleted after canonical verification, the post-cutover `20261004T014945Z` backup has since rotated out, and the canonical Git baseline is a root snapshot with no retained pre-rename parent. Recover a controlled pre-cutover bundle/preimage with a stable hash and rehearse old -> new -> rollback in isolation; do not reconstruct one from guesses or unrelated unreachable objects. | Controlled pre-cutover artifact hash, exercised rollback receipt, restore read-back, and operator sign-off. | Maintainer; `BLOCKED` |

A blocker may be marked closed only when its evidence is linked and the owner accepts the
result. “No collision found” is not a legal clearance.

## Acceptance criteria

- [ ] **AC-701.1 — Decision packet:** A versioned packet records the selected brand,
  alternatives, rationale, jurisdiction, intended use, prohibited claims, reviewer, date,
  and re-review trigger.
- [ ] **AC-701.2 — Qualified disposition:** The packet links controlled evidence for
  trademark/name review and domain/handle decisions; preliminary DNS, WHOIS, or social
  checks are labeled only as preliminary observations.
- [x] **AC-701.3 — Identity consistency:** The selected public name is mapped to every
  in-scope display, documentation, package, schema/API, source, and receipt surface, with
  an explicit decision for each surface.
- [x] **AC-701.4 — Technical impact:** No rename is hidden in a documentation-only change.
  Every proposed rename has an owner, compatibility window, migration/test seam, and
  rollback classification.
- [ ] **AC-701.5 — Collision audit:** A deterministic audit finds no duplicate ticket
  IDs, filename IDs, public identifiers, package names, domains, handles, or unresolved
  launch-name claims. Every manual collision has a disposition.
- [x] **AC-701.6 — Safety review:** The packet states that the brand decision cannot alter
  no-intent, privacy, rights, provenance, provider, or publication gates.
- [ ] **AC-701.7 — Compatibility proof:** If an alias or migration is approved, an
  isolated read/replay/rollback can read both identifiers, preserve receipts, and restore
  the prior state with a durable receipt.
- [ ] **AC-701.8 — Legal handoff:** DP-307/DP-306 records the accepted launch-name and
  disclosure decision, or the ticket remains `BLOCKED` with the exact safe default.
- [x] **AC-701.9 — No external side effect:** The implementation creates no remote, URL,
  domain registration, handle, tag, release, deployment, or public brand claim.
- [x] **AC-701.10 — Handoff:** DP-704 can consume the identity/rollback map, and DP-705
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
clearance. Fresh 2026-10-06 read-only DNS/public-host checks now prove that the domain is
delegated to Cloudflare through `candy.ns.cloudflare.com` and `kanye.ns.cloudflare.com`; the
apex and `www` resolve through Cloudflare, the apex returns HTTPS `200`, and `www` returns a
`308` redirect to `https://dichiarazionipubbliche.it/`. The canonical host serves
`robots.txt` and `sitemap.xml`, and its public search/API fingerprint is the same approved
`501348d9638e...` empty projection observed on the MiniPC. This closes the machine-readable
DNS/public-host portion of B-701-03 only. Controlled registrar ownership/expiry evidence,
social-handle disposition, qualified trademark review, external collision disposition, legal
handoff, and exercised rollback proof remain open. The public API still identifies its contract
as `DRAFT` and the approved projection has zero dossiers; none of this host read-back is treated
as stable-v1 or legal launch clearance. Public linked data is served at `/index.nt` and validated
against a private sibling receipt; the receipt itself is intentionally not exposed as a public
route.

The repository-local portion of the collision/dependency audit is green at the CI-verified
code candidate `cdad363e8dff97b1465891e47f00b51fbbbadb0d`, with subsequent documentation-only
status reconciliation leaving the runtime payload unchanged. `tools/check_repository_contract.py`
passes and the launch preflight correctly remains `NO-GO` instead of treating missing external
decisions as evidence. After DP-223's isolated MiniPC attribution-integrity sub-rehearsal closed,
the current integrated launch preflight reports **41 blockers**. AC-701.5 remains open because external package/domain/handle collision checks and
their manual dispositions are not complete; AC-701.7 remains open until an exercised
pre-rename rollback receipt exists, while AC-701.10 is closed by the explicit blocked-state
handoff below. AC-701.1/.2/.8 remain blocked on the qualified decision/legal evidence described
above.

### Collision-audit hardening refresh — 2026-10-08

Runtime/public-contract candidate `2dfd3233a967dadf476350cf6e4f2e8eb633f759` closes two
repository-local false-green cases without claiming external name clearance:

- `tools/check_repository_contract.py` now extracts the ticket ID independently from the
  `docs/tickets/DP-###-...md` filename and from the H1. Filename/H1 mismatch, duplicate filename
  IDs, duplicate H1 IDs, and malformed ticket filenames fail closed. Dedicated regression coverage
  passes **6/6** and the full repository contract remains PASS.
- The public projection/web route boundary now rejects lossy-ID collisions instead of allowing two
  distinct public identities to normalize to one route. Finding, Person, fallback Content, reviewed
  Trace, explicit Content and Topic routes are checked before publication/build; exact duplicate
  `finding_id` is also rejected. The Python and TypeScript/web paths share the same NFKD/lowercase
  public-ID slug semantics, and the search-index verifier rejects duplicate output routes. Adversarial
  examples such as `person_a` versus `person-a` and `finding_a` versus `finding-a` are regression
  fixtures rather than accepted aliases.
- Frozen local validation on the candidate is **1812/1812 PASS**, benchmark **5/5**, repository and
  contributor acceptance PASS. Web `check`, `check:search`, production/demo build contracts,
  `check:routes`, and `check:quality` pass. The launch preflight remains intentionally `NO-GO` with
  41 blockers.
- The exact eight changed files were checksum-verified on the MiniPC. The isolated candidate and the
  deployed mirror both passed public-schema/API/repository-contract acceptance (**111/111** on the
  mirror). The real approved empty projection built to six public routes; route and public-quality
  checks pass. Production dataset fingerprint remains
  `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a` with 0 dossiers and API
  contract `DRAFT`.

This advances only the **machine-local** portion of B-701-05/AC-701.5. AC-701.5 remains unchecked:
external package/domain/handle namespaces and every manual collision disposition still require
controlled evidence. It is not a trademark, registrar, social-handle, or legal-clearance receipt.

The rollback blocker is concrete rather than bookkeeping-only. The 2026-10-03 cutover used a
temporary rename-era rollback bundle, but after the canonical identity was independently
verified on 2026-10-04 that bundle and the obsolete runtime identities were deliberately
removed; recovery authority then moved to the canonical backups. The repository's canonical
baseline commit is also a root baseline rather than a retained pre-rename parent. Therefore an
old-identity -> new-identity -> rollback rehearsal cannot now be executed from controlled
retained material without reconstructing a legacy state. No such reconstruction is treated as
proof. AC-701.7 remains open.

### Final compatibility / rollback audit and downstream handoff — 2026-10-07

Fresh read-only inspection of the actual runtime and source history confirms that the missing
pre-rename rollback material is still the exact blocker rather than a stale ticket note:

- the MiniPC backup root no longer contains the documented post-cutover
  `20261004T014945Z` set, and a bounded home/runtime scan finds no project rename-era rollback
  bundle or active path carrying the former project aliases;
- `cdf4e061020dc48ab73e4c579c8d038fcd1c49ba`, the first canonical GitHub/source baseline,
  is a root commit with no parent. Current `git fsck --no-reflogs --unreachable` exposes only
  an unrelated 2026-10-05 DP-423 commit, not a controlled pre-rename source snapshot;
- the retained `~/.local/share/dichiarazioni-pubbliche/public/v1.rollback-20261006T142259Z`
  bundle is itself post-rebrand (`dichiarazioni-pubbliche-public-v2`) and therefore cannot prove
  old-identifier compatibility or the 2026-10-03 rename rollback.

Current recovery authority is healthy but proves only the **canonical** identity. Backup set
`20261007T143042Z` has dump SHA-256
`7587f81f7c6e50da07713943ff1aea940cac36415207eae55fa447df020ced02` and manifest SHA-256
`21b623d43340baf1d06bc1707b5482551ce1cd432589af260ee8a31436788b6e`, covering 94 durable
tables. On 2026-10-07 an isolated MiniPC database `dp701_brand_compat_20261007` was created empty,
the canonical restore drill replayed that exact set, verified all **94/94** table counts and
reported `RESULT: PASS` / `DRILL PASS`, then reset the throwaway schema and dropped the database;
post-run database existence read-back was zero. This is valid current-state disaster-recovery
evidence, but it is **not** AC-701.7 proof because the backup contains only the canonical
identity and does not let the operator read/replay both old and new identifiers or restore the
pre-rename state. The set also has no public-bundle copy, so public-host state is verified
separately rather than represented as part of that rollback receipt.

Read-only public-host verification remains consistent with the canonical identity: Cloudflare
serves the apex with HTTPS `200`, `www` returns `308` to the apex, authoritative delegation is
`candy.ns.cloudflare.com` / `kanye.ns.cloudflare.com`, `/api/v1/health` reports `status=ok`,
`contract_status=DRAFT`, schema `dichiarazioni-pubbliche-public-v2`, zero dossiers/omissions and
dataset fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`;
`search-index.v1.json` reports the same fingerprint with zero records and `/index.nt` returns
HTTP `200`. This is current read-back only; it does not recreate the deleted legacy bundle or
constitute trademark/domain/handle/legal clearance.

AC-701.10 is now closed as a **blocked-state handoff**, not as rollback completion. DP-704 already
declares DP-701 a final-signoff dependency (`B-704-06`) and requires an actually exercised
`ROLLBACK_VERIFIED` receipt (`B-704-08` / `AC-704.10`). Its DP-701 input is therefore:

| Handoff field | DP-701 value for DP-704 |
|---|---|
| Canonical product / technical identity | `Dichiarazioni Pubbliche` / `DichiarazioniPubbliche.it` / `dichiarazioni_pubbliche` / `dichiarazioni-pubbliche` |
| Runtime/database/schema | MiniPC canonical paths from the 2026-10-03 cutover; DB `dichiarazioni_pubbliche`; public schema `dichiarazioni-pubbliche-public-v2` |
| Current recovery state | Canonical 94-table backup/restore authority proven; current-state restore is `PASS` |
| Rebrand rollback state | `BLOCKED_PRE_RENAME_ARTIFACT_DELETED`; no controlled old-identity bundle/preimage remains |
| Public read-back | Cloudflare apex `200`, `www` -> apex `308`, dataset fingerprint `501348d9...`, zero dossiers/records, API contract `DRAFT` |
| Launch instruction | Do not convert current recovery/read-back into rebrand rollback proof; DP-704 remains blocked until its independent rollback and launch prerequisites are met |

DP-705 independently enforces the same safe default: it is `FUTURE` / `BLOCKED`, depends on
DP-701..DP-704, and its `B-705-01` requires DP-701 technical rename/rollback actions to close
while `B-705-10` separately requires tested rollback/read-back. Therefore DP-705 cannot claim
stable v1 while B-701-02/03/05/06/07 or the corresponding open ACs remain unresolved. This
handoff requires no edit to DP-704/DP-705 and makes no legal, trademark, handle, registrar, DNS,
deployment, or public-service mutation.

Repository validation after this handoff is green: `tools/check_repository_contract.py` passes,
`tools/check_launch_preflight.py --expect-no-go` passes, and `git diff --check` passes. The integrated launch preflight
returns `NO-GO` with **41 blockers** and explicitly includes `TICKET_NOT_DONE:DP-701:IN PROGRESS`,
so the handoff cannot be misread by DP-705 as release authority while the deleted-preimage
rollback blocker or the external clearance rows remain open.
