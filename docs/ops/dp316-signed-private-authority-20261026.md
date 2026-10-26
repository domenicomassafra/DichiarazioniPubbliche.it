# DP-316 — signed private machine authority, cutover and observed HOLD (2026-10-26)

## Current scope and trust anchor

`machine_authority_signed_v1.verify_signed_authority` is an **opt-in
private verifier**. Receipt v2 requires two Ed25519 signatures: an independent
adjudicator signs the record/evidence/decision payload, then a separate machine
authority signs the complete receipt including that adjudicator signature. The
two keys must be separately registered, have distinct public keys, actors and
roles, and bind the same policy/rights hashes but independent source roots.
Both signatures use a canonical JSON representation. The verifier reads a
trusted, 0600 locally owned key registry **outside the database and repository**;
its SHA-256 must come from independently managed operator deployment
configuration. A registry digest supplied by a candidate, receipt or database
is not a trust anchor. The verifier obtains current time internally; callers
cannot backdate receipt/key/rights expiry. No production issuer, private key,
trusted live registry or signing credential was generated or installed here.

The pin, registry status, actor/role, signer validity interval and permitted
source root, rights and qualified-policy digests must agree. The receipt
must bind the exact record/version, release reference, every DP-316 snapshot
material and DP-320 structural fence fingerprint, gold/privacy/rights/policy
hashes, issuance time, a cited HTTPS rights URL, dated expiry and
`PRIVATE_REVIEW` permitted use. Generator, challenger, adjudicator and
authority issuer must have four distinct run IDs and actor IDs; the first
three must have independent source roots. Changed lineage, expired rights,
missing gold, incomplete challenger, revoked key, wrong file permissions and
forged/malformed signatures HOLD. Underlying live source and gold adjudication
must still be independently established before any legitimate receipt issuance.

Two valid signatures yield `PRIVATE_SIGNATURE_VERIFIED`,
`private_signature_verified=true` and
`independent_adjudication_verified=true`, which is an **authenticated private
reference only**. Until source evidence, qualified policy, independent gold
and live epoch have also been proven by a trusted decision service, all
`machine_signoff`, `publication_authority` and `dispatch_authorized`
properties remain false. Legacy DP-310/311 review is unchanged; this receipt cannot substitute
for legacy approval. No model output, digest or self-declared reviewer acquires
public authority. The default registry mode `LEGACY` holds all machine
receipts. A specific versioned registry `MACHINE_V1`, pinned via trusted
deployment configuration, enables only this private verification. To roll
back, restore a separately pinned `LEGACY` registry and independently verify
the new SHA before use; any earlier machine receipt then HOLDs. There is no
live cutover or modification to the production review/public projection code.

The trusted registry format is:

```json
{
  "version": "dp316-registry-v2",
  "mode": "LEGACY",
  "keys": []
}
```

Every future key has exactly `key_id`, `actor_id`, `role`,
`public_key_hex`, `valid_from`, `expires_at`, `revoked`,
`source_root`, `qualified_policy_sha256` and `rights_sha256`.
Roles are exactly `MACHINE_AUTHORITY` or `INDEPENDENT_ADJUDICATOR`;
the two keys and public-key bytes must be distinct. No production example key
is bundled. The registry is intentionally source-specific. Never place
private signing material or rights decisions in the public projection.

## Existing integration limits

- The DP-316 structural preflight is still a HOLD for live authority.
  The signed private verification is **not wired to a production signer,
  PostgreSQL eligibility persistence, or the public read layer**.
- DP-320 isolated SQLite exercises transactional revoke, fencing and
  reader invalidation (including interleaving tests), but a production
  PostgreSQL commit/read adapter, CDN invalidation, registry-key epoch
  binding and atomic live cutover remain absent. Therefore this change
  cannot assert AC-316.5 or promote a result.
- No blind adjudicated representative legal/high-risk holdout has been
  accepted. The authentic private input below is **not** independent
  machine-verdict gold. Gold coverage denominator: 0 externally admitted
  legal/high-risk cases out of 1 authentic official statement examined
  here; no false-person/verdict rate can be calculated from that denominator.
- Unavailable operational rights/policy/root registry, independence
  proofs, release scope and gold mean `HOLD / NO-GO`, not GO-PUBLIC.
  No nightly or 24-hour performance evidence has been invented.

## Real-source private result observed on two reachable hosts

Official source: [European Commission, 2025-03-04 press statement](https://cyprus.representation.ec.europa.eu/news/press-statement-president-von-der-leyen-defence-package-2025-03-04_en).
Rights notice: [Commission legal notice](https://commission.europa.eu/legal-notice_en)
(`CC BY 4.0` for EU-owned site content, with attribution, third-party and
identifiable-person exceptions). The checks below use only private evidence
classification, not public reuse. The statement is a public-policy numeric
case, **not** an independently adjudicated LEGAL-status case.

At 2026-10-26 17:23:57 UTC on MiniPC and 17:27:35 UTC on Mac Studio,
the installed/existing `tools/dp314_claim_verification_canary.py` fetched
the two genuine HTTPS documents. On both:
- Official statement HTML: 91,749 bytes, SHA-256
  `e6a18b7eff1f41ccb0e60c65a4ab72956acc39e52651d321ac269fbdcd7cba2a`.
- EU legal notice: 154,018 bytes, SHA-256
  `e3a1ec9d19e6b1208b37f6d7af5c9a850665a86a4fbfef76948718c6f671070a`.
- Source excerpt: 80 characters, SHA-256
  `00b847d22e757f42d88e5b37b236d557817fe3150efde94fa48be910a53dc70f`.
- Five bounded classification evaluations: 1 `VERIFIABLE`, 1 `FALSE`,
  1 `NOT_VERIFIABLE`, 2 `HELD` (one rights, one counter-case).
  These are **operator-supplied stances**, not an accepted gold benchmark.
  Every result had `verdict=null`, `private_only=true`,
  `publication_authority=false`.

MiniPC readback on 2026-10-26: `dichiarazioni-pubbliche-web.service=active`;
`GET http://127.0.0.1:18090/api/v1/health` returned
`status=ok`, `contract_status=DRAFT`, `dossier_count=0`;
public HTTPS `/ ` returned HTTP 200. No consumer install was done from the
work-in-progress branch; installed predecessor
`machine_authority_preflight_v1.py` SHA-256
`cff509a837030855640d4a62ff2735d80d2e3789aad53c3186a7a0572b06c4eb`.
There is no real DP-316 eligible record ID or public correction/rollback
available to read back. The observed source ID is
`evidence:ec-press-2025-03-04`; publication remains HELD by design.

## Reuse and validation

The implementation reuses `pyca/cryptography` already declared in the
repository's `account` extra and DP-316/DP-320 data models. Its opt-in
`machine-authority` extra keeps the stdlib-only default unchanged. The
Ed25519 API is from [official pyca documentation](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
Upstream `pyca/cryptography`: 7,827 GitHub stars at 2026-10-26 readback;
49.0.0 tested locally, latest PyPI release 50.0.2 on 2026-09-30; SPDX
`Apache-2.0 OR BSD-3-Clause` per PyPI (repository licence enum itself
showed NOASSERTION). Existing compatible account bound is `>=45,<50`,
so no update to third-party code or licence change was made.

Studio test seam: the private `verify_signed_authority` entry point.
`uv run --no-project --with cryptography==49.0.0 python -m unittest
discover -s tests -p 'test_dp316_*.py' -q` inside the resource guard:
38 tests (16 preflight + 13 dual-signed + 9 cutover), exit 0 on 2026-10-26. A missing crypto backend yields HOLD in production; the CI job explicitly
installs the existing account extra so opt-in cryptographic tests execute. Test and CI receipts after the PR are in
the issue comment. There is deliberately no new receipt, canary, telemetry
window or public release switch.


## Versioned cutover and production boundary

The machine_authority_cutover_v1 selector records the policy selection
contract (LEGACY_ONLY, DUAL_READ, MACHINE_V1) without ever granting public
authority. LEGACY_ONLY ignores machine receipts; DUAL_READ keeps the DP-310/311
legacy path selected and treats a missing, stale, mismatched or non-signoff
machine receipt as a shadow HOLD; MACHINE_V1 never falls back to a legacy
review event. An explicit rollback from DUAL_READ or MACHINE_V1 requires a
versioned rollback reference and selects only the current legacy path.

ProductionProjectionRevalidator defaults to LEGACY_ONLY with no machine
receipt loader. A caller may inject a private verifier callback for shadow
comparison, but no such callback or host-local receipt store is configured in
the MiniPC runtime. MACHINE_V1 is deliberately fail-closed in the production
revalidator: it returns HOLD until the DP-320 transactional persistence and
final public-read epoch fence are integrated. The cutover result itself always
has publication_authority=false. No live mode switch, private key or trusted
registry was installed; the MiniPC consumer remains DRAFT with zero public
dossiers. These are explicit remaining AC blockers, not claims of completed
live cutover.
