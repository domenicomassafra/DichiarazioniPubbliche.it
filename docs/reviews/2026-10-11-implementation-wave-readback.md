# 2026-10-11 — source-only implementation wave, evidence and remaining gates

Status: **partial source implementation verified locally, NOT a runtime/release acceptance**.
The owner separately authorized actual ticket implementation after closing the
2026-10-10 planning-only mandate. Source branch is `main`; production mirror,
providers, real source acquisition, public publication, DB migrations and push
were not authorized or performed in this run.

## Commits and bounded implementation

| Contract | Commit(s) | Narrow change delivered |
|---|---|---|
| DP-236 | `acf6541` | Exact reviewed source-family/private use/expiry/revocation guard, opt-in capture seam |
| DP-237 | `6bd8532` | Exact pinned written/page/media Capture/Passage locators, immutable source hash/version checks |
| DP-312 | `6404079` | Conservative private speech-act/context/quoted-speaker assessment without publication authority |
| DP-318 | `d01fb22` | Pure same-Person versus cross-Person relation scope/temporal/endorsement preflight |
| DP-435/437 | `2405049` | Optional public-v3 original-quote-only Statement projection, independent gates, nullable Finding |
| DP-436 | `4a7afbf`, `caa5c5c`, `ce60baf`, `d6fb004` | Optional JSON/RDF/JSON-LD plus isolated Astro verbatim renderer and backend→client parity |
| DP-429/439 | `df6fa42`, `5c72563`, `f8b2b6e`, `2f2dba4` | Public-v2-only verified Person × Topic intersection, no private facet or paraphrase-as-quote |
| DP-512 | `c6d55c7` | Cost estimate no longer falsely recorded as measured; local energy UNKNOWN preserved |
| DP-514 | `e2df061` | Owner-versioned EUR/month reservation preflight with DST/FX; disabled, no dispatch |
| Inventory/status | `5b8edb7` | Versioned privacy allowlist extended conditionally, historical test count unfrozen, ten ticket statuses reconciled |

## Verifications (local Mac, not MiniPC production)

- Initial integrated Python test run: **2492 tests**, 4 FAIL and 1 ERROR. All five were traced to the *known plan change* (one old hardcoded 125-ticket assertion) and *new v3 public schema allowlist* (four tests using stale privacy inventory).
- Regenerated the canonical `privacy-field-inventory.v1.json` with the provided `--generate` tool. Compared output: only one new `PUBLIC_STATEMENT_ALLOWED_KEYS` conditional group (21 fields), no DB schema change or public-authority grant. Targeted inventory tests **17/17 PASS**.
- Final integrated Python suite: **2499/2499 PASS** (`PYTHONPATH=poc python3 -m unittest discover -s tests -q`, **147.424 seconds**); deterministic benchmark **5/5 PASS**; compileall PASS.
- Web: search-index and v3 statement synthetic tests PASS; **backend→Astro v3 parity PASS**; `npm run check:design` PASS; Astro check **89 files, 0 errors/warnings/hints**; isolated production projection boundary PASS (renamed demo excluded, private Studio absent, public-empty sitemap correct, legacy v2 compatibility and drift rejection).
- Repository contract PASS and `report_ticket_status.py --json` reports exact file/PLAN agreement. `check_launch_preflight.py --expect-no-go` remains explicitly NO-GO for unclosed Q-306/legal/source/release artifacts.

## Invariants / not yet achieved

These first source modules are **not connected to real authorized source data**.
The v3 schema, API serialization and Astro component are opt-in/isolated.
They do not make new records available over a public URL, automatically
promote a candidate or grant independent publication consent. The old public
v2 source is still default and its previous no-private-body protections remain.

Important dependencies still open:

1. DP-236/317 actual source-specific lawful fetch/excerpt permits, legal/privacy
   Q-306/DP-307 dispositions, effective policy and source use records;
2. DP-312/313/314/316/321 reference accuracy/gold on authentic multilingual
   texts and procedural documents; the old human authority never auto-migrates;
3. DP-318 legacy callers still need authenticated `person_id` and v3 relation
   currentness; a private comparison alone does not prove position change;
4. DP-435/436/437/438/439/440 real source/rights-attested Statement→Person×Topic
   read model, original-language quote in ALL public consumers, cite-per-sentence
   summary and atomic correction/revoke/cache handling;
5. DP-512/514 real billed EUR/energy and durable per-owner cap/CAS, not merely a
   correct offline estimate and synthetic concurrency;
6. DP-443 real, rights-cleared source→capture→candidate→eligible fact/opinion→
   source-cited public reader→correction/rollback MiniPC acceptance, prerequisite
   to any large historical backfill or stable v1.

No owner redesign has been chosen. No public feed, Google member account or
remote privileged administration has been enabled. The 2026-10-10 planning
packet response remains a separate untracked terminal file by design.
