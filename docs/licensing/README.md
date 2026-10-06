# Licensing, rights, and attribution

Implements DP-603. Owner: DP-603. This directory is the rights gate for every fixture,
data artifact, and visual reference in the repository.

## The boundary this directory protects

The repository **code** is Apache-2.0 ([`LICENSE`](../../LICENSE),
[`NOTICE`](../../NOTICE)). That license covers *code only*. It is **not** a grant for
media, transcripts, evidence bodies, datasets, screenshots, platform content, or any
third-party service's terms. Source/data rights are tracked separately, here.

## Machine-readable inventory

[`fixture-inventory.v1.json`](fixture-inventory.v1.json) is the canonical, versioned
inventory. Each row records `asset_id`, `path_or_locator`, `artifact_kind`, `origin`,
`source_reference`, `retrieved_at`, `content_hash`, `license_or_terms`,
`license_evidence`, `attribution`, `modifications`, `personal_data`,
`redistribution_status`, `public_projection_status`, `owner_and_review`, and `blocker`.

It is **generated** from the real tree so hashes and existence are true:

```bash
python3 tools/generate_fixture_inventory.py            # regenerate after adding an asset
python3 tools/generate_fixture_inventory.py --check    # fail if stale (CI)
python3 tools/check_licensing_inventory.py --check-hashes   # validate + verify hashes
```

Rights judgements are curated human decisions recorded in the generator; the tool
refuses to invent a licence for an unknown file. `UNKNOWN` is a valid audit value only
when paired with a `blocker` and an owner — it is never a pass for a releasable
artifact.

### Synthetic fixture policy {#synthetic-fixture-policy}

Fixtures authored for this project (`DICHIARAZIONI-PUBBLICHE-FIXTURE-POLICY-1.0`) are released with
the project under Apache-2.0 unless the row says otherwise. A synthetic fixture must be
fictional with respect to any real person, and must never be represented as a real
public finding.

## Status summary (as of the review date)

| `redistribution_status` | Count | Meaning |
|---|---|---|
| `allowed` | 30 | synthetic/derived/reference assets releasable with the code |
| `pending-review` | 3 | owner/legal decision required before distribution |
| `blocked` | 6 | **not** redistributable; must not ship in a release or public projection |
| `metadata-only` / `private-only` | 0 | (none currently) |

**The six `blocked` rows are real public-source artifacts** (Raffaele Giuliani and
Beppe Grillo content) collected from Instagram/TikTok/YouTube. Public availability is
not a redistribution grant; those platforms' terms reserve rights, and a qualified
legal/privacy review (DP-304 privacy, DP-305 copyright/excerpt, DP-306/DP-307 legal) is
required before any distribution. **They must not be included in a release artifact or
public projection in their current state.** This is a `BLOCKED` rights state, not a
failure of the check — the check's job is to keep it visible and blocked.

The three `pending-review` rows are the two `docs/ux/reference/p6.2/*.png` visual
references of unknown origin plus one derived receipt; they await an owner keep/remove
decision.

## Enforcement

`tools/check_licensing_inventory.py` (run in CI and as release gate 5) fails when:

- a tracked fixture/data/visual asset has no inventory row;
- an `asset_id` or `path_or_locator` is duplicated;
- a row marked `allowed` has `UNKNOWN`/missing licence evidence, attribution, or
  retrieval date;
- a row has an invalid `artifact_kind` or `redistribution_status`;
- an `owner-local` row is marked `allowed`;
- a hashed row's content hash does not match the file; or
- a raw/private/credential-class file is tracked (`*.mp4`, `*.wav`, `*.env`, `*.pem`,
  `*.db`, …).

## Related policy owners (linked, not duplicated here)

- **DP-301** — intentionality / no-intent wording in findings.
- **DP-304** — privacy minimization and sensitive-person handling.
- **DP-305** — copyright, transcript, and excerpt publication policy.
- **DP-306 / DP-307** — unresolved legal research and qualified legal review.
- **ADR 0005** — the Apache-2.0 code-vs-content boundary.
- **DP-604** — consumes this inventory as release gate 5.

## Adding an asset

Before committing a new fixture, dataset, screenshot, or donor artifact:

1. add a `ROW_DECISIONS` entry (or a visual rule) in `tools/generate_fixture_inventory.py`
   with real provenance, licence evidence, attribution, modifications, personal-data
   class, and redistribution status;
2. regenerate the inventory and commit it with the asset;
3. if the rights evidence is `UNKNOWN`, leave the row `pending-review`/`blocked` with a
   concrete `blocker` and owner — do not guess a licence and do not use the Apache-2.0
   code license as a data permission.

No test result in this repository claims legal clearance; an `allowed` row reflects a
recorded engineering/licensing decision, not legal advice.
