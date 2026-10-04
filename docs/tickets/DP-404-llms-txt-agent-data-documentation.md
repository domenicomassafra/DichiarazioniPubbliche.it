# DP-404 — `llms.txt` and agent-oriented public data documentation

Status: DONE

Milestone: M4 — public product/API
Depends on: DP-403, DP-402, DP-105

## Problem

Agents and developers need a concise, durable map of the public record surface. Copying
the website or OpenAPI document into an unstructured prompt creates stale guidance,
encourages unsafe interpretation, and can blur the difference between retrieval,
verification, review, and publication.

The current operational contract is `dichiarazioni-pubbliche-public-v2`, while DP-105 has not ratified
the stable public v1 compatibility decision. The discovery document must not conceal that
gate.

## Outcome

Publish a generated, plain-text `llms.txt` at the public site root, plus a small set of
linked canonical references, so an agent can discover the read-only record, understand
its semantics, and use the API without receiving private data or instructions to bypass
review.

`llms.txt` is documentation, not a chatbot endpoint, not an ingestion interface, and not
an authority that can publish a finding.

## Contract gate

DP-105 and DP-403 must close before the document is served as stable. Until then:

- it may be generated in fixture mode with a visible `DRAFT`/contract-gate marker;
- it must state the current contract identifier without claiming v1 compatibility;
- it must not be linked as a stable public contract from production;
- no URL in it may bypass the fail-closed public projection.

## Scope

### Document shape

Serve `/llms.txt` as UTF-8 plain text with a bounded, stable section order:

1. product purpose and public-scope statement;
2. public surfaces and canonical links;
3. public contract and API discovery links;
4. domain vocabulary and the retrieval → approval → verification → publication boundary;
5. provenance, temporal, correction, and right-of-reply semantics;
6. representative, clearly fictional request/response shapes;
7. limits, unsupported states, and safe failure behavior;
8. method, corrections, and accessibility links;
9. contract version, generation date, and document fingerprint.

The document must use canonical domain terms from `CONTEXT.md`. It must explain that
`retrieved evidence != approved evidence`, `verified claim != published finding`, and
`contradiction != proof of intent`. It must not describe a person score, ranking, or
political recommendation.

### Links and examples

Every link must point to a versioned, public-safe artifact owned by DP-105, DP-403, or the relevant existing canonical policy document:

- the DP-402 manifest;
- the DP-403 OpenAPI document;
- the public method and correction/reply policy;
- the public schema/examples;
- the public search/index documentation, once DP-409 exists.

Examples must be short, deterministic, and labeled as fictional. They may show a
published finding, an unresolved state, a correction link, and an empty result. They
must not contain raw transcript/evidence bodies, provider prompts, credentials, private
replies, or a real-person claim invented for the document.

The document must not instruct an agent to:

- call an LLM to decide whether a statement is true;
- infer speaker identity from voice, face, or appearance;
- approve evidence, publish a finding, or submit a reply;
- treat a candidate relation as a published accusation;
- use a generic model-generated URL or query as evidence.

### Freshness and failure behavior

- The document is generated from the same contract metadata as OpenAPI and the public
  examples, not hand-edited independently;
- a broken internal link, unknown contract version, unsafe URL, or changed fingerprint
  fails the documentation build;
- a missing projection produces no public stable document rather than an empty document
  that implies no records exist;
- an empty public dataset may be described as an empty current dataset, but the document
  must not claim that no private or held records exist;
- the file is served with a cache validator derived from its content and is replaced
  atomically with the API/schema release.

## Non-goals

- an LLM, chatbot, prompt endpoint, MCP server, or autonomous agent;
- a paid, authenticated, realtime, or bulk API;
- a second copy of the OpenAPI schema or a new public database;
- an instruction set for bypassing human review or publication policy;
- whole-website crawling, private search, or generalized web search;
- publishing raw transcript/evidence content or private corrections/replies;
- a final hosting/CDN choice;
- an SDK or generated client (those remain post-v1 unless separately approved).

## Dependencies and gates

- **DP-105:** hard public schema and safety vocabulary owner;
- **DP-402:** route and error behavior owner;
- **DP-403:** OpenAPI and versioning owner;
- **DP-401:** static hosting/rewrite gate;
- **DP-409:** optional downstream search-index documentation, not a prerequisite for the
  initial document;
- **PRODUCT/ADR 0001/0002:** no LLM request path and no projection bypass.

## Acceptance criteria

- [ ] `AC-404.1`: Given the approved DP-105 contract and DP-403 OpenAPI document, when
  `llms.txt` is generated, then its links, version, vocabulary, and examples agree with
  those sources and contain no conflicting field names or routes.
- [ ] `AC-404.2`: Given an agent reads the document, when it follows the links, then it
  can reach the manifest, schema/examples, method, and correction/reply policy without
  credentials or a private host.
- [ ] `AC-404.3`: Given any example, when it is parsed, then it is explicitly fictional
  and cannot be mistaken for a real claim, a published verdict, or an instruction to
  publish.
- [ ] `AC-404.4`: Given the document is inspected for safety, then it contains no raw
  transcript, evidence body, provider prompt, secret, person score, ranking, political
  recommendation, biometric instruction, or unreviewed reply/correction.
- [ ] `AC-404.5`: Given a contract, link, or fingerprint changes, when the documentation
  build runs, then it either updates the document atomically or fails closed; it never
  leaves a stale stable document reachable.
- [ ] `AC-404.6`: Given an empty projection, when the document is generated, then it
  describes the empty public dataset without claiming that private/held records do not
  exist.
- [ ] `AC-404.7`: Given all providers are offline, when the public documentation is read,
  then it remains useful and does not require a live model or a private operational
  database.
- [ ] `AC-404.8`: Given the collision/dependency audit runs, then DP-403 owns OpenAPI,
  DP-404 owns discovery text, and no second API/schema contract is introduced.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

Then run a deterministic documentation check that:

- parses the generated text as UTF-8;
- validates every relative and absolute public link;
- compares the contract version and fingerprint to DP-105/DP-403 outputs;
- rejects forbidden private/provider/LLM/score terms;
- checks the fictional-example marker and bounded document length.

Runtime completion requires fetching `/llms.txt` through the DP-401 adapter on MiniPC and
recording its status, content type, cache validator, and link-check receipt. Mac output is
development evidence only.

## Documentation, data, and migration impact

- `llms.txt` is generated from the public contract and OpenAPI examples; do not maintain
  a second hand-written API list;
- update the discovery document in the same release as any contract or route change;
- no database migration is introduced;
- do not edit `PLAN.md`; DP-404 remains in the existing M4 sequence;
- if DP-409 later adds a static search artifact, add one link to this document rather
  than embedding search behavior here.

## Completion receipt

Implementation slice completed on the development checkout on 2026-09-27:

- added `docs/api/llms.txt` and `docs/api/README.md`;
- the API contract tests verify bounded UTF-8 content, contract/version wording,
  fictional examples, safe semantic boundaries, and public-route links;
- the document contains no raw transcript/evidence body, provider prompt, secret,
  person score/ranking, political recommendation, biometric instruction, or
  unreviewed reply/correction.

Runtime closure completed on 2026-09-27:

- `/llms.txt` is generated from the same projection/route contract as OpenAPI and is
  served by the same MiniPC process as the static site and API;
- MiniPC read-back returned HTTP 200 with `text/plain; charset=utf-8`, an ETag, and
  ETag revalidation returned 304;
- the document links the canonical `/api/v1` routes and no longer claims MiniPC
  read-path proof is outstanding.

The discovery document remains explicitly DRAFT until release ratification; no public
launch is claimed by this ticket.
