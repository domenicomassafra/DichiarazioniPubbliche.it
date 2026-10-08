# Garlasco pilot — real DB readback and incomplete 18-item seed

**Date:** 2026-10-08. **Authority:** MiniPC `dichiarazioni_pubbliche`
PostgreSQL, read-only. No database or public projection writes.

## Safe and reproducible invocation

`poc/dichiarazioni_pubbliche/garlasco_pilot_inventory.py` reads exactly
three fixed queries over the persisted historical Garlasco Atomic Claims,
Content and supporting tables. Connection uses the existing read-only
PostgreSQL session mode and query timeout of the Studio local DB bridge.
It returns only counts, known blocker codes and a material-sensitive seed
SHA-256. It excludes raw source URLs, quote bodies, private transcripts,
unpublished claim text and arbitrary database metadata from stdout.

Run from the project root on the MiniPC:

```bash
PGDATABASE=dichiarazioni_pubbliche PYTHONPATH=poc \
  python3 -m dichiarazioni_pubbliche.garlasco_pilot_inventory \
  --verify-baseline-search
```

For a **new** private operator seed file (explicit opt-in), use
`install -d -m 700 ~/.local/state/dichiarazioni-pubbliche/garlasco-pilot`
and `--write-private-draft /home/udodo/.local/state/dichiarazioni-pubbliche/garlasco-pilot/garlasco-existing-content-seed-20261008.json`.
An existing destination is never overwritten. The export is not an
approved full manifest: the exact 18 URLs belong to existing Content
records but `discovery_ref` stays empty, `source_family` stays
`UNCLASSIFIED`, rights are `UNKNOWN`, and the file explicitly blocks
ingestion.

## Observed MiniPC evidence

| Proof | Current count / state |
|---|---:|
| Historical Garlasco Atomic Claims | 30 |
| Distinct historical claim IDs | 30 |
| Claims with exact persisted Content link | 30/30 |
| Private indexed self-retrieval with exact claim+Content binding, top 20 | **30/30** |
| Garlasco benchmark top-5 queries | **13/13 (100%)** |
| Measured benchmark p95 | **51.904ms** |
| Distinct existing Content IDs | 18 |
| Existing Content items with unresolved rights | 18/18 |
| Historical approved quote-attribution records | 28 |
| Existing Source Intelligence profiles for these contents | 0 |
| `research:garlasco` collection records/members | 0 / 0 |
| Research discovery hits for all sources | 0 |
| Captures / passages for these contents | 0 / 0 |
| Statement / Claim Candidates for these contents | 0 / 0 |
| Collection Coverage Needs | 0 |
| Current PUBLISH Findings | 2 (pre-existing; unchanged) |
| Missing logical items to the bounded 100-item pilot | **82** |

The seed has SHA-256
`6b6ea81195c0c7278ad3452b7fb00735b4658d696e2fd9f950bed70365b373c0`.
The private 18-item draft is stored on the MiniPC at
`/home/udodo/.local/state/dichiarazioni-pubbliche/garlasco-pilot/garlasco-existing-content-seed-20261008.json`
with file mode **0600**, outside Git and public static assets. It is
not a secret credential but can contain source URLs that are never
copied into public exports without review.

## Still failing, not waived

- Real, deduplicated discovery provenance for a bounded **100**
  selected logical items across the five required source families.
- Verified rights/access/retention for capture and passage creation;
  approved speaker/source attribution is not evidence-body licensing.
- Persisted collection, source profiles/roles/scopes, approved source
  suitability, immutable capture/hash and exact selectors.
- Safe duplicate/derivation, entity/candidate/cluster review and
  source-specific Coverage Needs.
- Collection-scoped recall, idempotent replay, persisted MiniPC
  post-ingestion count stability and actual private/public leak proof.

**Acceptance:** AC-214.3 only is now supported, not DP-214 DONE.
No 100-item fake manifest or public release is implied.

## Six public discovery leads, excluded from acceptance counts

`config/garlasco-public-discovery-leads.v1.json` contains **six**
new URL candidates found on public broadcaster, podcast and news
pages during the 2026-10-08 public research pass, plus one official
Pavia prosecutor website **source locator only**, which cannot
count as a case Content item. The six candidates include an authored
podcast episode, a broadcaster interview, a broadcaster news clip,
secondary agency coverage, a third-party reproduction of a
prosecutorial press statement, and reporting on a lawyers' statement.

MiniPC exact-URL deduplication against the current Garlasco Content
table found **0/6 already stored**. This is discovery research
only: none has a persisted DP-209 run/hit, reviewed speaker/source
identity, immutable capture, provenance hash, source rights clearance
or private intake permit. The candidates are **not** inserted into
the corpus and **do not reduce the 82 unfilled accepted logical-item
positions**. Their role classifications are *proposals*, including
one possible derivative of an official statement that is not itself
an official first-party document.
