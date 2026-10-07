# DP-403 — OpenAPI, examples, and API versioning/deprecation policy

Status: DONE

Milestone: M4 — public product/API
Depends on: DP-402, DP-105

## Problem

DP-402 defines the read-only HTTP behavior, but consumers need a machine-readable
description, concrete examples, and a compatibility promise. Documentation that drifts
from the routes or the public schema would create a second, unsafe contract.

The current operational projection is `dichiarazioni-pubbliche-public-v2`; DP-105 has not yet ratified
the stable public v1 compatibility decision. This ticket therefore specifies the
publication and compatibility workflow without silently treating either identifier as
final.

## Outcome

Publish and validate an OpenAPI document that describes the DP-402 read-only API, plus
versioned examples and a written deprecation policy. The document is a description of
the DP-105 public contract, never a replacement for it.

## Contract gate

DP-105 must close the schema/resource-manifest decision before this document is called
stable. Until then:

- fixtures may exercise draft OpenAPI objects locally;
- no public URL, stable SDK, or compatibility promise may be published;
- the document must state the unresolved contract version rather than hiding the v1/v2
  mismatch;
- an implementation may not add fields directly to OpenAPI to make an unstable projection
  appear complete.

## Scope

### OpenAPI document

- Use OpenAPI 3.1.0 as the document baseline; a later OpenAPI version requires an explicit compatibility decision;
- serve the document at the DP-402 manifest-linked location, provisionally
  `/api/v1/openapi.json`;
- use `$ref` components for all DP-105 resource, assessment, provenance, correction,
  reply, relation, and ContentAudit shapes;
- describe only `GET` and `HEAD`; write operations, Studio routes, intake, and admin
  operations are not present;
- declare public reads as unauthenticated (`security: []`) and do not imply a cookie,
  token, or session contract;
- document the bounded error envelope and every status from DP-402;
- document pagination, cursor invalidation, ETag/freshness semantics, and canonical links;
- include examples from the same approved projection fixtures used by the API contract
  tests.

The OpenAPI document must not contain database table names, internal worker states,
provider/model names, raw transcript/evidence bodies, secrets, or unreviewed operational
records. A fictional example must be labeled as fictional and must not be presented as a
claim about a real person.

### Examples

Examples must cover at least:

- one published finding version with approved provenance identifiers;
- one unresolved or needs-more-evidence finding without fabricating a stronger verdict;
- one empty collection;
- one corrected finding with an append-only correction link;
- one public right of reply with its own publication state;
- one reviewed longitudinal relation;
- one ContentAudit with bounded claim moments;
- one `404`, one `400`, and one `503` transport error.

Every example must validate against the same schema as the live response. Examples must
not contain raw transcript text, evidence excerpts, private role data, or provider
receipts.

### Versioning and deprecation policy

- The URL major version is the compatibility boundary (`/api/v1`);
- within a major version, adding an optional field or a new explicitly documented
  endpoint is backward-compatible;
- renaming a field, changing its meaning, making an optional field required, removing a
  field, changing identifier semantics, or changing an assessment/relation meaning is
  breaking and requires a new major version;
- new enum values are not silently added when an existing consumer could treat them as a
  safety or policy decision; the DP-105 vocabulary owns that decision;
- a deprecation must identify the replacement, the first deprecation date, and a sunset
  date no earlier than 90 days later;
- deprecated endpoints must emit `Deprecation` and `Sunset` headers and remain readable
  until the announced sunset;
- the OpenAPI document, examples, changelog, and DP-105 compatibility note must be updated
  in the same change;
- no endpoint may be removed silently because a static host stopped serving a file.

### Documentation boundaries

The OpenAPI document is a reference. It must link to, rather than duplicate, the public
method and correction/reply policy. It must not prescribe a frontend layout, an LLM
prompt, an operational database query, or a hosting vendor.

## Non-goals

- a client SDK, MCP server, agent skill, or paid API tier;
- code generation for a specific language as a release commitment;
- an OpenAPI document for private Studio or future admin operations;
- a second public schema independent of DP-105;
- an API key, user account, rate-limit product, or authentication system;
- a live query endpoint, semantic search, or vector retrieval;
- translating generated mockup labels into public domain vocabulary;
- choosing a CDN, domain, or external hosting provider.

## Dependencies and gates

- **DP-105:** hard schema, vocabulary, compatibility, and deprecation vocabulary gate;
- **DP-402:** hard transport and route owner;
- **DP-401:** hosting/deployment gate for serving the document and its examples;
- **DP-404:** downstream machine-readable discovery document; it must link to the same
  OpenAPI resource;
- **ADR 0001/0002:** public projection remains the sole data boundary and no LLM is
  available in the request path.

## Acceptance criteria

- [x] `AC-403.1`: Given the DP-105-approved schema and DP-402 route table, when the
  OpenAPI document is generated, then every route, status, parameter, header, and schema
  reference matches the implementation without a second field vocabulary.
- [x] `AC-403.2`: Given the documented examples, when each response example is validated
  against the referenced DP-105 schema, then valid examples pass and intentionally
  invalid examples fail for the documented reason.
- [x] `AC-403.3`: Given a consumer reads the document, when it inspects security and
  methods, then it sees read-only public operations only and no implied write/auth
  contract.
- [x] `AC-403.4`: Given an additive optional change, when compatibility is assessed, then
  it is classified as non-breaking and does not require a new major version; given a
  semantic or required-field change, then it is classified as breaking and requires a
  new major version.
- [x] `AC-403.5`: Given a deprecation, when a client requests the old endpoint during the
  announced window, then the response remains readable and includes the required
  `Deprecation` and `Sunset` headers plus a documented replacement.
- [x] `AC-403.6`: Given a schema or route fixture, when the document is inspected, then it
  contains no raw transcript/evidence body, private data, provider receipt, person score,
  unreviewed correction/reply, or real-person fictional example.
- [x] `AC-403.7`: Given the DP-105 v1/v2 decision is unresolved, when the document is
  built, then the build succeeds only in fixture mode or fails with a clear contract gate;
  it cannot publish a falsely stable document.
- [x] `AC-403.8`: Given the OpenAPI document and examples, when the collision/dependency
  audit runs, then DP-402 remains the route owner, DP-105 remains the schema owner, and
  no duplicate endpoint contract is introduced.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

Then run a local, pinned OpenAPI/schema validator and a fixture comparison that proves:
the served document matches the generated document; every example validates; every route
has an implemented read-only test; and all deprecation fixtures produce the documented
headers. The validator may be a contributor-only local tool; this ticket does not require
a new runtime service.

Runtime completion requires the document and a representative route to be fetched from
the MiniPC deployment mirror through the DP-401 adapter. Record the URL, response
validator, schema version, and a sample of safe response headers.

## Documentation, data, and migration impact

- The canonical API reference and OpenAPI document are generated from the DP-105
  compatibility contract;
- update the API examples and deprecation log when a public schema version changes;
- no database migration is introduced by this ticket;
- do not edit `PLAN.md`; sequencing remains owned there;
- DP-404 must consume this document rather than hand-maintaining a conflicting list.

## Completion receipt

Implementation slice completed on the development checkout on 2026-09-27:

- `poc/dichiarazioni_pubbliche/openapi.py` generates the OpenAPI 3.1 document from the
  implemented read-only route/contract vocabulary;
- `docs/api/openapi.v1.json` is the checked reference artifact and
  `tests/test_public_api.py` verifies route/method parity, errors, examples,
  publication guarantees, and deprecation semantics;
- DP-105 is DONE; the document identifies the actual
  `dichiarazioni-pubbliche-public-v2` projection contract instead of concealing the historical
  v1/v2 discrepancy.

Runtime closure completed on 2026-09-27:

- the generated route table and checked OpenAPI artifact now use canonical same-origin
  `/api/v1` URLs with no legacy `/v1` split;
- `/api/v1/openapi.json` is generated from the same route/contract code the server
  executes and is served by the MiniPC adapter with HTTP 200;
- API/socket tests and the full repository suite are green.

The artifact remains DRAFT until release ratification. Ticket completion does not mean
the API has been publicly announced or released.
