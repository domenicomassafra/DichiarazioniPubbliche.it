# Release checklist (DP-604)

Runnable, fail-closed. Every gate below is either **PASS** with evidence or **BLOCKED**
/ **PENDING-OWNER** with a reason. A missing gate is never an assumed pass.

**This repository has a canonical Git remote but no release.** Publication remains
blocked until the release-specific legal, registry, signing, dataset, hosting and owner
authorization gates below are complete.

## 0. Set up a detached clean clone

Never build a candidate from a developer's working tree.

```bash
COMMIT=$(git rev-parse HEAD)
CLONE=$(mktemp -d)/dichiarazioni-pubbliche
git clone https://github.com/domenicomassafra/DichiarazioniPubbliche.it.git "$CLONE"
cd "$CLONE" && git checkout --detach "$COMMIT"
git status --short                       # must be empty
```

The release candidate must be reconstructed from the canonical hosted remote, not from a
developer working tree. Record the commit SHA and clone URL in the receipt.

## 1. Record the receipt header

| Field | Value |
|---|---|
| Commit SHA | `git rev-parse HEAD` |
| Clone method | canonical GitHub remote |
| Canonical version | `cat VERSION` |
| OS | `uname -a` |
| Python | `python3 -VV` |
| Node / npm | `node -v`, `npm -v` |
| Package-manager pin | `web/package-lock.json` lockfileVersion |
| Build backend | `setuptools>=68.0,<81.0` |

## 2. Gate 1 — Scope and ticket graph

```bash
python3 tools/check_repository_contract.py --only tickets
PYTHONPATH=poc python3 tools/check_launch_preflight.py --expect-no-go
```

Confirms: no duplicate ticket IDs, no duplicate filename IDs, valid status values, no
unknown dependency IDs, no dependency cycles, required sections present. The current
NO-GO check is a non-release regression check; in future authorized release
reviews run the preflight without the expect-no-go switch, inspect all blockers
and require a separate release-authority/owner gate. The preflight cross-checks
canonical ticket headers against PLAN and requires the M1R/M2 source/promotion
chain, including DP-214 real corpus and DP-229 challenger.

**Fails** → the ticket graph is inconsistent; do not release.

## 3. Gate 2 — Clean clone

- [ ] `git status --short` empty
- [ ] no `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `web/dist/`, `.astro/`
      carried in from the source (a clone never has them; a copy might)
- [ ] no `.env`, credential file, cookie jar, browser profile, or raw media
- [ ] ignored caches created by the build are removed in step 10 or recorded

**Fails** → the source tree is not self-sufficient.

## 4. Gate 3 — Backend

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
```

- [ ] `compileall` exit 0
- [ ] full suite: all tests pass
- [ ] benchmark: `N/N passed (100%)`, identical to the pre-release run
- [ ] no test was skipped because a provider credential was absent

**Fails** → contributor baseline is broken.

## 5. Gate 3b — Package install (DP-601)

```bash
python3 -m venv .venv-check && . .venv-check/bin/activate
python -m pip install ".[dev]"
python -c "import dichiarazioni_pubbliche; print(dichiarazioni_pubbliche.__file__)"
python -m dichiarazioni_pubbliche.benchmark --fixtures "$PWD/poc/fixtures/italian_cases.json"
dichiarazioni-pubbliche-review-admin --help
```

- [ ] wheel/sdist builds from a clean checkout
- [ ] all `dichiarazioni_pubbliche.*` modules import from the install
- [ ] console scripts resolve to real callables
- [ ] no runtime dependency was added

**Fails** → the documented install path is broken.

## 6. Gate 4 — Web

```bash
cd web && npm ci && npm run check && npm run build && cd ..
```

- [ ] `npm ci` from the lockfile, no lockfile edit
- [ ] `astro check` clean
- [ ] static build succeeds
- [ ] fictional demo banner is present and visible

**Fails** → the frontend contract/build is broken. Offline without a registry is
`BLOCKED — no npm registry access`, not a pass.

## 7. Gate 5 — Licensing / data (DP-603)

```bash
python3 tools/check_licensing_inventory.py
```

- [ ] every tracked fixture/data/visual asset has a row
- [ ] no duplicate `asset_id`
- [ ] no `redistribution_status: allowed` row has `UNKNOWN` license evidence
- [ ] no raw/private media, transcript, cookie, or credential is tracked
- [ ] unresolved rows are `pending-review`/`blocked` and are **not** in the artifact

**Fails** → do not ship the affected artifact; a repository release may still proceed
if it ships code only and the unresolved rows are not part of it — record which.

## 8. Gate 6 — Security / privacy

- [ ] secret/private-content scan clean (part of `tools/check_repository_contract.py`)
- [ ] `SECURITY.md` reviewed; no public security contact invented before owner approval
- [ ] dependency/license review: no incompatible-license code vendored
- [ ] unresolved legal/privacy decisions are explicit blockers (DP-304..DP-307)

## 9. Gate 7 — Public contract (only if a public artifact changed)

- [ ] DP-105 / DP-402 / DP-403 compatibility decision recorded
- [ ] examples regenerate and match
- [ ] the public projection remains fail-closed and sanitized

**N/A** if the candidate ships no public-schema change; say so in the receipt.

## 10. Gate 8 — Database (only if persistence changed)

```bash
# isolated database only; never production
for m in db/schema.v1.sql db/migrations/*.sql; do
  psql "$ISOLATED_DSN" -v ON_ERROR_STOP=1 -f "$m" || exit 1
done
# replay every migration a second time to prove idempotence where claimed
```

- [ ] ordered migrations apply in order with `ON_ERROR_STOP`
- [ ] replay result recorded
- [ ] no production data was read or mutated to obtain a pass

**Fails** → migration claim unproven. **N/A** if no persistence change; say so.

## 11. Gate 9 — Runtime (only if runtime-affecting)

- [ ] MiniPC receipt: mirror hash, migration result, service/command exit codes, read-back
- [ ] Mac-only evidence is explicitly **not** accepted as a substitute

**Fails / absent** → the candidate is blocked for that claim. A release that omits a
MiniPC receipt for runtime-affecting behavior must ship nothing runtime-affecting.

## 12. Gate 10 — Version / changelog

```bash
python3 tools/check_version_consistency.py
```

- [ ] `VERSION` == `pyproject.toml` version
- [ ] changelog has a dated, ticket-linked entry for the version
- [ ] entry includes impact, compatibility, migration, rights, security, runtime notes
- [ ] no secrets, raw transcripts, evidence bodies, or unverified legal claims in it
- [ ] a benchmark `PUBLISH` label is not presented as publication authorization

**Fails** → do not release.

## 13. Gate 11 — Release authority (BLOCKED here)

- [ ] owner approval
- [ ] qualified legal review for the release scope (DP-307 / DP-702)
- [x] confirmed canonical remote URL — `https://github.com/domenicomassafra/DichiarazioniPubbliche.it`
- [ ] registry/signing/hosting decision

> **Current state: BLOCKED — release authority incomplete.** The canonical `origin` exists,
> but owner release approval, qualified legal review, signing/registry decisions and the
> remaining launch gates are not complete. Nothing in this checklist invents them.

## 14. Reproducibility: build twice

```bash
python3 -m pip install "build>=1.2,<2.0" "packaging>=24,<26" "setuptools>=68,<81" "wheel>=0.44,<0.46"
python3 tools/check_reproducible_package.py
```

The checker creates two independent detached clones of the exact commit, sets
`SOURCE_DATE_EPOCH` to that commit timestamp, builds wheel + sdist with the bounded build
tooling, normalizes only the sdist archive metadata through `tools/normalize_sdist.py`,
and requires identical artifact names and SHA-256 hashes. A mismatch fails the gate.

For the candidate artifacts kept for review, use the same metadata rule:

```bash
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
python3 -m build --no-isolation --outdir dist
python3 tools/normalize_sdist.py --source-date-epoch "$SOURCE_DATE_EPOCH" dist/*.tar.gz
sha256sum dist/* 2>/dev/null || shasum -a 256 dist/*
```

## 15. Cleanup and tree hygiene

```bash
rm -rf dist-1 dist-2 .venv-check web/dist web/.astro
rm -rf *.egg-info build dist
find . -name __pycache__ -type d -prune -exec rm -rf {} +
git status --short          # must be empty
```

`pip install -e .` / `python -m build` may write `*.egg-info/`, `build/`, or `dist/`
into the checkout. Remove only those generated paths after recording the artifact hashes;
the final `git status --short` must be empty in the detached candidate clone.

## 16. Final receipt

The receipt records: commit, version, tool versions, artifact hashes, each gate's
PASS/BLOCKED with reason, and every `PENDING-OWNER`/`BLOCKED` item. A local build
receipt is **not** a release receipt. Under-publication is the safe response when any
artifact, rights record, or public contract is uncertain.
