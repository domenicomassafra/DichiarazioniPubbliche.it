# Dichiarazioni Pubbliche — rebrand and runtime cutover receipt

Date: 2026-10-03
Owner decision: **Dichiarazioni Pubbliche**
Canonical domain label: dichiarazionipubbliche.it

This receipt records the technical rename requested and approved by the owner. It does
not claim domain registration, trademark clearance, social-handle ownership, or public
launch readiness.

## Canonical identity map

Only the canonical identity is retained in active documentation:

| Surface | Canonical identity |
| --- | --- |
| Product | Dichiarazioni Pubbliche |
| Repository / domain label | DichiarazioniPubbliche.it |
| Python package | dichiarazioni_pubbliche |
| Python distribution / service prefix | dichiarazioni-pubbliche |
| Ticket namespace | DP-* |
| Environment prefix | DICHIARAZIONI_PUBBLICHE_* |
| PostgreSQL database | dichiarazioni_pubbliche |
| Public schema identifier | dichiarazioni-pubbliche-public-v2 |

## Source and desktop surfaces

- Git/source authority moved to /Users/domenico/Code/DichiarazioniPubbliche.it.
- Python package moved to poc/dichiarazioni_pubbliche.
- package/CLI metadata, OpenAPI metadata, headers, fixture-policy identifiers, docs,
  tests, systemd source units and ticket filenames/references were migrated.
- Obsidian durable identity is now
  05-knowledge/tools/dichiarazioni-pubbliche.md and its owned-software MOC points at the
  new repo path.
- ControlCenter operational handoff is now
  handoffs/dichiarazioni-pubbliche-continue-20261001.md.
- active product-film / Remotion / audio source uses the new name.
- MacBook Air and Omarchy had no active legacy project paths at the final fleet scan;
  only Syncthing .stversions history retained the former card name.
- the retained Windows MateBook was offline during the scan and is not a source/runtime
  authority for this project.

Historical external ledgers, recovery inventories, browser recordings and version-history
stores may preserve immutable historical text outside this repository. Active source,
documentation, runtime naming and maintained project files use only the canonical name.

## Local validation

- python compileall: PASS.
- full Python suite: **977/977 PASS**.
- restore-drill verification: PASS.
- deterministic benchmark: **5/5 PASS**.
- Astro check: **47 files, 0 errors, 0 warnings, 0 hints**.
- production-style static build without a projection remained fail-closed as designed.
- explicit local demo build: **16 pages built, PASS**.
- git diff --check: PASS.
- active-repo legacy-name scan: zero matches.

The repository was already carrying owner WIP before this rename and it remains
preserved: queue_runtime.py, tests/test_queue_runtime.py,
poc/dichiarazioni_pubbliche/timestamp_acceptance.py and
tests/test_timestamp_acceptance.py. The rebrand is intentionally not committed over that
WIP.

## MiniPC pre-cutover proof

The new mirror was synchronized to /home/udodo/src/DichiarazioniPubbliche.it before
stopping the former runtime and independently passed compileall plus the full **977/977**
Python suite and restore-drill comparison.

## Recovery material

A temporary cutover rollback bundle existed during the migration window. After the
canonical identity was fully verified on 2026-10-04, a fresh production backup was
created with the canonical naming and the temporary rename-era rollback bundle was
deleted so obsolete runtime identities would not remain on disk.

Current recovery authority:

`~/.local/share/dichiarazioni-pubbliche-backups/20261004T014945Z/`

The set contains `dichiarazioni_pubbliche.dump`, its SHA-256 and the row-count manifest;
`pg_restore --list` validation passed at creation time.

## MiniPC runtime cutover

Runtime authority was migrated to:

- mirror: /home/udodo/src/DichiarazioniPubbliche.it;
- database: dichiarazioni_pubbliche;
- config: ~/.config/dichiarazioni-pubbliche;
- private/state data: ~/.local/share/dichiarazioni-pubbliche and
  ~/.local/state/dichiarazioni-pubbliche;
- systemd prefix: dichiarazioni-pubbliche-*.

Final runtime proof:

- source-poll timer: active;
- daily source-poll timer: active;
- worker timer: active;
- health timer: active;
- web service: active;
- worker oneshot after cutover: Result=success, ExecMainStatus=0;
- source-poll oneshot after cutover: Result=success, ExecMainStatus=0;
- health oneshot: Result=success, ExecMainStatus=0;
- health JSON exists under the new state path;
- loopback web read-back: **HTTP 200**.

The initial new web start briefly failed because the old web process still held port
18090. The exact legacy process and old units were then stopped; the new web service was
restarted and verified active/HTTP 200. No data migration failed during that transient
port conflict.

Former unit files and live config/state/source paths were removed after verification.
The rename-era rollback bundle and obsolete timer stamps/backups were also removed on
2026-10-04 after a fresh canonical backup had been verified.

## Public projection

The moved production projection initially still carried the old schema identifier. It
was regenerated from the renamed production database with the renamed code:

- schema: dichiarazioni-pubbliche-public-v2;
- dossier count: **2**;
- omitted count: **0**;
- dataset SHA-256:
  8c430c1bb36ad8135c313247d6cf276ffc6fea6c2f998e31f9d55aa02da85383;
- projection scan after regeneration: no legacy brand/codename strings;
- web read-back after regeneration: HTTP 200.

## Database contract registry

The production `public_schema_contract` registry was canonicalized on 2026-10-04 in one
guarded transaction after verifying exactly one pre-canonical row. The active row is now:

`contract:dichiarazioni-pubbliche-public-v2 | dichiarazioni-pubbliche-public-v2 | ACTIVE`

A fresh post-cutover backup was taken immediately afterward and scanned for obsolete
identity strings with no matches.

## Still external / not claimed

- no claim is made that dichiarazionipubbliche.it has been purchased or registered;
- trademark/name legal clearance remains open;
- social-handle ownership remains open;
- stable-v1/public-launch gates remain independent.

## 2026-10-04 consolidation closure

The previously preserved owner WIP and the rebrand working tree were subsequently
consolidated on `main` after a fresh validation pass. This closes the temporary state
described above where the rename was intentionally left uncommitted.

Closure evidence:

- Python compileall: PASS;
- full Python suite: **977/977 PASS**;
- deterministic benchmark: **5/5 PASS**;
- DP-207 timestamp acceptance fixture: **84 segments / 36 claims / 57 provenance edges / 0 provider calls**;
- Astro check: **47 files, 0 errors, 0 warnings, 0 hints**;
- design-system check: PASS;
- explicit demo static build: **16 pages PASS**;
- `git diff --check`: PASS;
- active-tree former-brand scan: zero matches outside intentional historical receipts;
- no Git stashes and no auxiliary worktrees remained.

The public architecture decision was also closed rather than left as an open redesign:
`docs/35-public-product-architecture-v3.md` is canonical, the maintained prototype set is
the nine page families in `prototypes/final-hybrid/`, and the real route/template cutover
is isolated as `DP-422` instead of remaining implicit working-tree scope.

## Canonical GitHub/source identity

The canonical source repository is now:

`https://github.com/domenicomassafra/DichiarazioniPubbliche.it`

Before the first GitHub push, local `main` was rewritten to a single canonical root
snapshot and unreachable pre-canonical Git objects/reflogs were pruned. This prevents the
new hosted repository from carrying obsolete project identities in browsable source
history. The current working tree, filenames, package/module identifiers, service names,
ticket namespace and active documentation use only the canonical identity.
