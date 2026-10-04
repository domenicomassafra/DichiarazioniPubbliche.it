# DP-402 — Stable read-only HTTP API over the public schema

Status: DONE

Milestone: M4 — public product/API
Depends on: DP-105, DP-401

## Problem

The backend already emits a bounded, finding-versioned public projection, but consumers do
not yet have a stable HTTP contract. A database-backed route, a static file convention, or
an ad-hoc frontend fetch would each create a different public surface and could bypass
the publication gate.

The current runtime emits `dichiarazioni-pubbliche-public-v2`. DP-105 is still `READY` and still calls
the compatibility contract public schema v1. The v1/v2 decision is not implicit: it must
be recorded before this ticket can be implemented against a public route.

## Outcome

Provide a cacheable, read-only HTTP interface for the public projection. The interface
must:

- expose the public resources selected by the DP-105 manifest;
- preserve the exact public schema and finding-version semantics;
- work with a static bundle or a thin static-host read adapter;
- make no PostgreSQL, provider, operational filesystem, or LLM call in the public request path;
- fail closed when the projection is missing, stale, tampered, or incompatible.

## Contract gate

Before implementation starts, DP-105 must close the following decisions in its public
compatibility contract and the ticket must be updated to point at the resulting contract:

1. whether `dichiarazioni-pubbliche-public-v2` is the implementation of stable v1 or must be adapted to
   a separately named v1 contract;
2. the resource manifest, stable identifiers, required/optional fields, and list ordering;
3. the compatibility treatment of the legacy `public_role` field versus dated Role
   Intervals;
4. the exact correction, right-of-reply, relation, and ContentAudit projections;
5. whether a resource not present in the projection is `404`, an empty list, or omitted.

Until that gate closes, fixture-only route prototyping is allowed, but no route may be
called stable, public, or DONE, and no compatibility claim may be made.

## Scope

### Public HTTP surface

The v1 base path is `/api/v1`. The resource names below are the required logical surface;
DP-105 may ratify the final manifest, but it must not leave a resource ambiguous:

| Method | Route | Meaning |
|---|---|---|
| `GET`, `HEAD` | `/api/v1/manifest` | Contract version, generation metadata, and links to public resources. |
| `GET`, `HEAD` | `/api/v1/findings/{finding_id}` | One immutable published finding version. |
| `GET`, `HEAD` | `/api/v1/findings` | Bounded, deterministic finding collection. |
| `GET`, `HEAD` | `/api/v1/persons/{person_id}` | Public Person record and its published finding references. |
| `GET`, `HEAD` | `/api/v1/topics/{topic_id}` | Public Topic record and its published finding references. |
| `GET`, `HEAD` | `/api/v1/contents/{content_id}` | Public ContentAudit resource and published claim moments. |
| `GET`, `HEAD` | `/api/v1/relations/{relation_id}` | One reviewed longitudinal relation group. |

The exact URL spelling and aliases must be recorded in the DP-105 manifest. A resource
must never be resolved by an untrusted display name when a stable identifier exists.

The API is read-only. `POST`, `PUT`, `PATCH`, `DELETE`, and method override requests must
be rejected without reaching an operational write path.

### Transport contract

- JSON is the default representation; JSON-LD remains available only where DP-105 defines
  it and must reference the same finding version;
- the transport envelope is `data` plus bounded `meta`; resource fields are copied from
  the DP-105 contract without database-shaped additions;
- `meta` may contain contract version, generation timestamp, dataset fingerprint,
  pagination cursor, and canonical links only;
- `data` is one resource object or an array, never a mixed error/resource response;
- identifiers are opaque strings and are not parsed as database IDs;
- dates are ISO 8601 with an explicit timezone; timestamps displayed by the frontend must
  not be reconstructed from a locale-dependent string;
- the API never returns raw transcript text, canonical transcript text, evidence bodies,
  provider receipts, secrets, internal errors, review drafts, or private replies.

The envelope above is a transport decision for this ticket and must be ratified together
with the DP-105 schema before code is written. If DP-105 selects a different envelope,
update this specification and its contract tests before implementation; do not layer an
ad-hoc compatibility wrapper in a route.

### Collections and pagination

The collection contract must be deterministic and bounded:

- default `limit` is 25 and the maximum is 100;
- `cursor` is opaque, signed only if the selected host requires it, and never contains a
  raw SQL expression or a client-controlled sort instruction;
- default order is newest publication time first, with stable finding ID as the tie-breaker;
- sort fields are an allowlist defined by DP-105, not arbitrary field paths;
- a cursor from another contract version is rejected rather than silently reinterpreted;
- a collection with no public records returns `200` with `data: []` and no invented
  placeholder record;
- a detail ID that is unknown, private, unsafe, or no longer projectable returns the same
  externally visible `404` response.

Arbitrary full-text search is not part of this ticket. It is the bounded artifact defined
by DP-409.

### Cache and freshness

- Every response must expose an ETag or an equivalent validator derived from the public
  projection fingerprint;
- cache validators must change when a finding version, correction, reply, or other
  public field changes;
- a stale or invalid projection must not be served as fresh merely because a browser
  cache exists;
- `HEAD` must have the same status, headers, and freshness policy as `GET` without a body;
- the host may serve static files or a thin read adapter, but the host choice is outside
  this ticket.

### Errors and observability

The error envelope is stable and transport-only:

```json
{
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "Short public explanation",
    "request_id": "opaque-request-id"
  }
}
```

Required mappings:

| Condition | Status | Public behavior |
|---|---:|---|
| Malformed path/query or unsupported parameter | `400` | Explain the invalid request without echoing secrets. |
| Unsupported `Accept` value | `406` | Return the same bounded error envelope. |
| Unknown/private/non-projectable resource | `404` | Do not reveal whether an operational row exists. |
| Write method or unsafe method override | `405` | Include `Allow: GET, HEAD`; do not invoke a write path. |
| Projection missing, invalid, stale, or contract-incompatible | `503` | Fail closed; do not return partial or fabricated data. |
| Unexpected server failure | `500` | Return a generic message and request ID only. |

Every response must include a request ID suitable for correlation. Logs may record route,
status, duration, and request ID; they must not record raw query text, transcript text,
evidence bodies, credentials, or provider prompts. No error response may include a stack
trace or SQL fragment.

## Non-goals

- public writes, intake, authentication, authorization, CSRF, or account management;
- an admin API or a Studio HTTP mutation surface;
- arbitrary SQL, database browsing, or operational-table pagination;
- full-text, semantic, vector, or LLM search (DP-409 owns the bounded static index);
- a public submission form for a new verification;
- choosing a CDN, domain, cache vendor, or external hosting product;
- a new database, search service, queue, or worker for the read path;
- changing DP-105's public schema from a route or frontend type;
- exposing omitted/private records to explain a `404`.

## Dependencies and gates

- **DP-105:** hard data-contract and compatibility gate; must be closed before stable
  route implementation;
- **DP-401:** hard deployment gate for the selected static/read adapter; Mac build proof
  alone is not public-runtime proof;
- **DP-403:** downstream OpenAPI and deprecation contract; it must describe this interface,
  not replace it;
- **DP-409:** downstream search/index contract; it must not add a second public data
  contract;
- **PRODUCT/CONTEXT/ARCHITECTURE and ADR 0001/0002:** the projection remains the only
  public read boundary and remains usable while providers are offline.

## Acceptance criteria

- [ ] `AC-402.1`: Given the DP-105-approved public projection, when a client requests an
  allowed `GET` or `HEAD` resource, then the response is generated from the projection
  only and contains the stable finding/resource identifiers required by DP-105.
- [ ] `AC-402.2`: Given a valid collection request without a cursor, when more than one
  record matches, then the response is bounded, deterministically ordered, and includes a
  continuation cursor only when more records exist.
- [ ] `AC-402.3`: Given an empty public collection, when the client requests it, then the
  API returns `200`, an empty array, and no fabricated record or private omission detail.
- [ ] `AC-402.4`: Given an unknown, private, unsafe, stale, or tampered resource, when it
  is requested, then the response fails closed and never exposes operational existence,
  raw content, or provenance gaps.
- [ ] `AC-402.5`: Given a write method, unsafe method override, malformed query, unsupported
  media type, or invalid cursor, when the request is made, then the documented status and
  bounded error envelope are returned without reaching a write or database mutation.
- [ ] `AC-402.6`: Given any public response, when it is inspected, then it contains no raw
  transcript, canonical transcript body, evidence excerpt/body, provider receipt, secret,
  person score, ranking, or unreviewed reply/correction.
- [ ] `AC-402.7`: Given a projection fingerprint changes, when a client revalidates a
  cached response, then the validator changes for every affected finding version and
  correction/reply history.
- [ ] `AC-402.8`: Given all model and evidence providers are offline, when the same
  approved projection is served, then reads remain available and do not invoke a provider
  or LLM.
- [ ] `AC-402.9`: Given the DP-105 contract is not yet ratified, when an implementation
  branch starts, then the branch contains a recorded contract decision and does not claim
  stable v1 or public readiness.
- [ ] `AC-402.10`: Given the route contract and examples, when the collision/dependency
  audit runs, then no duplicate ticket ID, route owner, schema owner, or dependency cycle
  is present.

## Validation / proof

The implementation receipt must include:

```bash
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
cd web && npm run check && npm run build
cd .. && git diff --check
```

In addition, provide a deterministic API contract fixture matrix covering: valid detail,
valid collection, empty collection, unknown ID, unsafe ID, unsupported method, invalid
query, invalid cursor, missing projection, incompatible schema, and tampered/stale
projection. The fixture output must be compared with the DP-105 schema and the documented
error envelope.

Runtime-affecting completion requires a read-only smoke test from the MiniPC deployment
mirror and the selected DP-401 static/read adapter. A Mac build is development evidence
only. The receipt must record the projection fingerprint, HTTP status samples, cache
validator behavior, and proof that no LLM/provider/PostgreSQL access occurred in the
public request path.

## Documentation, data, and migration impact

- Add or update the public API reference and examples only after DP-105 ratifies the
  transport envelope and resource manifest;
- update the static-host route/rewrite documentation owned by DP-401 if the selected
  adapter requires rewrites;
- do not add a migration for public reads; if DP-105 changes the public schema, its
  migration and compatibility proof remain the source of truth;
- do not change `PLAN.md` from this ticket; its existing M4 ordering remains authoritative.

## Completion receipt

Implementation slice completed on the development checkout on 2026-09-27:

- `poc/dichiarazioni_pubbliche/public_api.py` implements the bounded read-only route
  contract over the approved public projection only;
- collection filtering, deterministic pagination, ETag/HEAD behavior, typed errors,
  method rejection, projection/schema validation, and private/non-projectable omission
  are covered by `tests/test_public_api.py`;
- DP-105 is now DONE and the implementation consumes its authoritative
  `dichiarazioni-pubbliche-public-v2` contract rather than inventing a v1 downgrade;
- 62 focused API tests pass, the complete branch Python suite passes, Astro check is
  clean, the static frontend build succeeds, and `git diff --check` is clean.

Runtime closure completed on 2026-09-27:

- the bundled stdlib adapter now exposes the canonical same-origin `/api/v1` path and
  may serve the Astro static directory from the same process;
- a socket-level regression test covers real GET/HEAD, ETag revalidation, write-method
  rejection, same-origin static content, `llms.txt`, and unsupported `Accept`;
- the MiniPC service uses only the pre-built public projection and static files; it binds
  to `127.0.0.1:18090` and does not open PostgreSQL/provider/LLM access in the request
  path;
- live MiniPC smoke: health 200, HEAD 200, ETag revalidation 304, POST 405,
  unsupported `Accept` 406, old `/v1` path 404, OpenAPI 200.

The implementation ticket is DONE. The contract remains marked DRAFT until the release
process ratifies/announces it; DONE here is not a public deployment or compatibility
announcement.
