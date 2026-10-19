# WikibaseIntegrator — optional private entity proposal adapter (issue #159)

## Donor provenance and decision

- Source: <https://github.com/LeMyst/WikibaseIntegrator>.
- Licensed under MIT, copyright LeMyst and project contributors; upstream
  [LICENSE](https://github.com/LeMyst/WikibaseIntegrator/blob/v0.12.15/LICENSE).
- Adopt the **released package**, `WikibaseIntegrator==0.12.15` from the
  `wikidata-proposal` optional extra in `pyproject.toml`. No vendor/fork or
  copied donor code. Release `v0.12.15` was published 2025-12-21; tag object
  `0016ce91d931e1b5900f7b9dbdadcca2c8bf2984`, resolved commit
  `d81571765506da0a36c526b29cd59209fad4f45d`.
- Audit on 2026-10-19: upstream default branch `master`, HEAD
  `25ced366538309a17d156711c8de066a225c95b1`; last repository push
  2026-10-19. Its modern dependency set includes `requests`, so this is never
  installed with the stdlib-only contributor/public profile. The installed
  package carries its own original MIT license. The local adapter is Apache-2.0.
- Alternative: hand-written `requests` MediaWiki access would duplicate the
  donor's entity search, parsing, rate-handling and API compatibility logic;
  direct SPARQL or external inference is out of scope. Retained integration:
  `wbi_helpers.search_entities` and `WikibaseIntegrator.item.get` (read-only).

## Operational contract

The module `poc/dichiarazioni_pubbliche/wikidata_proposal_adapter.py` exports
`WikidataProposalAdapter`; it is **disabled by default**, independent of
`candidate_extraction` and the public projection, and has no API route or
automatic identity binding. It accepts only the pre-existing local ID, up to
five pre-extracted local aliases, the local source SHA-256, expected entity
type, optional relevant time, and a reviewed Wikidata role QID or topic type
QIDs. Do not send raw source bodies, excerpts, private documents, full names
outside reviewed aliases, or unrelated metadata to the external API.

Before `enabled=True`, the operator must separately obtain:

1. A **current** `SourceUseDecision` from
   `private_capture_rights.evaluate_source_use(..., use="DISCOVER_METADATA")`
   for the exact source artifact. `PERMITTED`, record ID and decision hash
   are required; missing, stale and denied records fail closed.
2. An explicit, independently reviewed `EgressApproval` bound to that
   source SHA-256, with `host="www.wikidata.org"`,
   `purpose="PRIVATE_ENTITY_PROPOSAL"`, reviewer reference and unexpired UTC
   expiry. Constructing the record is not proof of a rights review: the
   caller must obtain it from its operator-controlled authorization workflow.
3. The `WikibaseIntegrator` optional extra installed by the operator and an
   identifying `user_agent` stating the project and a contact URL/address.

Network access is exactly to `https://www.wikidata.org/w/api.php`, anonymous
search and item reads only. Calls use `allow_redirects=False` so a 3xx redirect
cannot silently move the request to a different host/private address; the
operator's outbound network/firewall policy must also allowlist the intended
Wikidata endpoint. There are maximum five results per alias; a full result
page causes HOLD because the returned set may be truncated and omonyms unseen.
There is no unbounded pagination and only one API attempt per read,
three-second connect/read timeouts (configurable 0–10 s), and spacing between
reads. Adapter invocations have a rate gate; bounded in-memory LRU holds at
most 32 successful proposals for up to 120 seconds by default. An authorization
is checked *again before consulting the cache*; revoked/expired approvals
never return a proposal. Provider, timeout, malformed, inconclusive,
homonymous or rights conflicts become `HOLD`; no raw provider error is logged.

Only exact label/alias and verified `P31` class QIDs are considered. Person
proposals additionally require matching `P39` held position and **bounded**
`P580`/`P582` dates containing the statement/reference date. Organization
date filtering uses Wikidata inception `P571` and optional dissolution `P576`.
Topics require explicit locally reviewed type QIDs. Incomplete or malformed
claims produce HOLD; no Wikidata QID is interpreted as a local authority.

## Receipt, review and data rights

The result is a structured `WikidataProposal(local_entity_id, qid, receipt)`
with Wikidata URL, positive entity revision (`lastrevid`), actual observation
time, source SHA-256, source-use decision fingerprint and adapter version. The
`.to_resolution_candidate(content_id=...)` method yields only a local
`EntityResolutionCandidateRecord` with `status=CANDIDATE`, no automatic link,
publication permission, reviewer identity or approval. The local repository
and its existing review/currentness gate remain the authority; QIDs are
optional evidence hints. A candidate with unresolved homonyms yields HOLD
even if one result looks plausible.

Wikidata item metadata are accessed under Wikimedia's API/usage policy and
Wikidata's CC0 structured-data terms; the external rights/egress permission is
still mandatory for the particular locally sourced alias, and no fetched
record is automatically republished. No real third-party dataset or artifact
is checked into the repository; tests use synthetic offline fixtures only.

## Reproducible checks

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_wikidata_proposal_adapter -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_knowledge_repository -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_contributor_acceptance.py
```

The local alias baseline `propose_alias_matches` is compared in the new tests:
both return **unapproved** candidates pointing at the original local ID.
Negative examples reject wrong person type/role/period, same-name entities,
malformed records, revoked/absent source rights, absent egress and timeout.
