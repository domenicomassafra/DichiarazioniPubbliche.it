# DP-313: official Curia judgment, private procedural readback (2026-10-25)

This bounded readback exercises the existing `procedural_document_roles`
contract on one genuine first-party judgment. It does not create source grants,
capture records, evidence, claims, a review approval or a public projection.

## Source and rights

- Source: Court of Justice of the European Union, Eighth Chamber, judgment of
  **25 June 2026**, case **C-622/24 P** (VT v European Commission),
  **ECLI:EU:C:2026:519**, Italian procedural language.
- First-party document: <https://juris.curia.europa.eu/juris/document/document.jsf?docid=312911&doclang=IT>.
  Observed on 2026-10-25 via HTTPS 200 with a bounded single-document
  download on Mac Studio. The case header, operative order and date were
  inspected against the official original (no media republication).
- Copyright authority: <https://curia.europa.eu/site/jcms/qua1_6625/>,
  observed 2026-10-25. Curia says its original case law may be reproduced
  with source acknowledgement; third-party works need separate permission.
  Attribution for this bounded analysis: **Court of Justice of the European
  Union, C-622/24 P, ECLI:EU:C:2026:519**. The original wording was not
  modified; the script normalizes only HTML whitespace for selectors.
  This specific reproduction permission is **not** a DP registry CURRENT
  `EXTRACT_CANDIDATES` grant or clearance of protected personal information.
- Party **VT** is anonymized in the official record. Privacy identity,
  authenticity review, source currentness, registered downstream uses, and
  third-party material remain unresolved. All derived observations are
  `PRIVATE_HOLD`; rights and publication authority are explicitly false.

## Reproduce on Mac Studio

Fetch only this pinned judicial source to an ephemeral file (never commit its
full body); the receipt is generated completely offline:

```sh
curl -fsSL --max-time 15 --max-filesize 500000 \
  -o /tmp/dp313-curia-312911-20261025.html \
  'https://juris.curia.europa.eu/juris/document/document.jsf?docid=312911&doclang=IT'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 \
  tools/dp313_curia_private_readback.py \
  --html /tmp/dp313-curia-312911-20261025.html
```

2026-10-25 observed receipt: **exit 0**, `PRIVATE_HOLD`,
`source_sha256=1bcb37cfb1d9f6c949dbe0b57fdb391ad9f5ba89102ba48271c53a25f40a72ae`;
three spans held; `extraction_authorized=false`,
`publication_authorized=false`, `NOT_EVALUATED` for all underlying facts.
Two HTTPS downloads had *different raw HTML hashes* because of volatile
session markup, but identical normalized judgment hashes. The tool pins the
latter and rejects changes. Character offsets are in the normalized official
HTML body, not physical page numbers or independently verified OCR.

Distinct exact-offset observations:

1. VT's application seeking annulment: party's procedural request, not
   the Court's own factual endorsement.
2. The operative order annulling the earlier General Court judgment:
   Court disposition, **not** acquittal or guilt finding.
3. The description of the earlier decision *not* to register VT:
   prior decision quoted by the Court; negative polarity, attribution to
   the EPSO board still unverified.

The third span is explicitly held for institutional quoted-author verification
and negative-phrase review. Anonymous-person privacy and unreviewed source
currentness hold the first two. The tool does not infer finality, real-person
identity, factual guilt, or evidence independence. It does not connect this
document to a persistent Capture/Passage/Statement/claim or a MiniPC consumer
database. Rights, privacy, OCR alternatives, version/appeal invalidation,
cross-source independence, and conditional revalidation remain necessary for
original **AC-313.1–6** end-to-end acceptance.

## Existing components reused

The readback uses `procedural_document_roles.evaluate_procedural_document`
and existing role/status/negation/privacy guards without a new database schema,
parser dependency or publishing path. The official Curia copyright notice
covers case-law reproduction with attribution; it is not a license for a third
party's photograph or an authorization for a paid model operation.
