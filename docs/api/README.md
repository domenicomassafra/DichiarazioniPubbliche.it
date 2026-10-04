# Dichiarazioni Pubbliche public API (contract v1, DRAFT)

Status: contract `v1` over the `dichiarazioni-pubbliche-public-v2` public projection.
Contract status: **DRAFT** — served and cacheable, with same-origin MiniPC
runtime proof complete; stable-v1 compatibility/release ratification remains open.

## What this is

A read-only, cacheable HTTP surface over the Dichiarazioni Pubbliche public projection. The
projection is a fail-closed, sanitized, finding-versioned read model produced by
the publication pipeline. This API reads it and nothing else.

## Run it

```bash
export DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH=/path/to/projection/index.json
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.public_api --port 8787
```

`DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` is the same variable the static web build uses.
Point both at the same bundle and the API and the static site cannot diverge.

## Guarantees

- **No LLM, provider, or database in the request path.** Reads stay available
  with every model provider offline.
- **Read-only.** `GET` and `HEAD` only. `POST`, `PUT`, `PATCH`, `DELETE`, and
  method-override requests return `405` with `Allow: GET, HEAD`.
- **The publication gate is never re-implemented here.** A finding is served
  because it is already in the projection. A dossier that is not PUBLISH,
  DISPUTED, CORRECTED, or RETRACTED is not in the bundle, so it is not served.
- **Fail closed.** A missing, stale, tampered, or contract-incompatible
  projection returns `503` on every endpoint: no partial data, no placeholder.
- **Cacheable.** `ETag`, `Last-Modified`, and `Cache-Control` on every response;
  a matching `If-None-Match` returns `304`.
- **No private data.** No raw transcript body, no evidence body, no provider
  receipt, no secret, no private reply, no person score, no ranking.

## Endpoints

| Method | Path | Meaning |
|---|---|---|
| GET, HEAD | `/api/v1/health` | Liveness, projection fingerprint, vocabulary versions |
| GET, HEAD | `/api/v1/schema` | Public contract descriptor: vocabularies, bounds, guarantees |
| GET, HEAD | `/api/v1/findings` | Bounded, deterministic collection of published finding versions |
| GET, HEAD | `/api/v1/findings/{{finding_id}}` | One immutable published finding version |
| GET, HEAD | `/api/v1/records/{{slug}}` | One public record (statement) and its published findings |
| GET, HEAD | `/api/v1/topics` | Topic facets present in the projection |
| GET, HEAD | `/api/v1/people` | Public figures present in the projection |
| GET, HEAD | `/api/v1/openapi.json` | This API as an OpenAPI 3.1 document |
| GET, HEAD | `/api/v1/index.json` | The full fail-closed projection bundle |

## Collection contract

- `limit`: default `25`, maximum `100`. Out of range is a `400`.
- `cursor`: opaque continuation from `meta.next_cursor`. Version-checked and bound
  to the request's filter set; reusing one with different filters is a `400`.
- Order: `published_at` descending, `finding_id` ascending as a stable
  tie-breaker. Deterministic for a given dataset fingerprint.
- Filters, all optional, all comma-separated and AND-combined: `topic`
  (claim-type code), `assessment`, `status`, `person` (speaker id), `content`
  (content id), `published_from`, `published_to` (ISO 8601 with an explicit
  timezone).
- An empty collection is `200` with `data: []`. It never fabricates a record.
- An unknown or malformed parameter is a typed `400`, never a silent empty page.

## Examples

```bash
curl -sS http://127.0.0.1:8787/api/v1/health

curl -sS 'http://127.0.0.1:8787/api/v1/findings?limit=2&assessment=SUPPORTED'

curl -sS 'http://127.0.0.1:8787/api/v1/findings/finding:fictional:1'

curl -sS http://127.0.0.1:8787/api/v1/topics

curl -sSI http://127.0.0.1:8787/api/v1/openapi.json
```

Revalidate instead of refetching:

```bash
etag=$(curl -sSI http://127.0.0.1:8787/api/v1/findings \
  | sed -n 's/^[Ee][Tt]ag: //p' | tr -d '\r')
curl -sS -o /dev/null -w '%{{http_code}}\n' \
  -H "If-None-Match: $etag" http://127.0.0.1:8787/api/v1/findings
# 304
```

## Errors

```json
{{"error": {{"code": "MACHINE_READABLE_CODE", "message": "Short public explanation", "request_id": "opaque"}}}}
```

| Condition | Status | Code |
|---|---:|---|
| Malformed query or unknown parameter | 400 | `INVALID_QUERY`, `UNSUPPORTED_PARAMETER`, `INVALID_PARAMETER_VALUE` |
| Invalid or cross-filter cursor | 400 | `INVALID_CURSOR` |
| Write method or method override | 405 | `METHOD_NOT_ALLOWED` (with `Allow: GET, HEAD`) |
| Unknown, private, or non-projectable resource | 404 | `RESOURCE_NOT_FOUND` |
| Projection missing, invalid, stale, incompatible | 503 | `PUBLIC_PROJECTION_UNAVAILABLE` |
| Unexpected failure | 500 | `INTERNAL_ERROR` |

Error responses are `Cache-Control: no-store` and never contain a stack trace, a
SQL fragment, or any hint that an operational record exists.

## Rate limits

No authentication and no rate-limit enforcement ship in this deployment. The
contract reserves `429 RATE_LIMITED` with a `Retry-After` header for a future
release (DP-508); clients should handle it defensively and must not read its
absence as unlimited throughput. The intended shape is a CDN-cached static read
served to infrequent, revalidating clients.

## Versioning and deprecation

`/api/v1` is the compatibility boundary. Adding an optional field or a new documented
endpoint is compatible. Renaming a field, changing its meaning, making an optional
field required, removing a field, changing identifier semantics, or changing an
assessment, relation, or publication-status meaning is breaking and requires a
new major version. A deprecation names its replacement, a first deprecation date,
and a sunset date at least 90 days later; the endpoint stays readable and emits
`Deprecation` and `Sunset` until then. Nothing is removed silently.

## Contract artifacts

- `docs/api/openapi.v1.json` — the generated OpenAPI 3.1 document.
- `docs/api/llms.txt` — the generated agent-facing discovery document.
- `poc/dichiarazioni_pubbliche/openapi.py` — the generator, so all three agree.

```bash
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.openapi --docs-dir docs/api
```
