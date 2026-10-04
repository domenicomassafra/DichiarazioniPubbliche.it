# DP-401 — Static-first hosting/deploy contract for the public projection

Status: DONE
Milestone: M4 public product/API
Depends on: DP-105 for closure; fixture-backed prototyping is permitted earlier by `PLAN.md`

## Problem

The backend already produces a fail-closed JSON/JSON-LD/HTML public projection, but there
was no real public frontend or explicit static build boundary consuming that projection.

## Outcome

Provide a frontend build that:

- reads only a supported public projection at build time;
- pre-renders the public product to static HTML/assets;
- does not call an LLM or operational database in the public request path;
- can be moved behind a CDN/static host without changing the domain model;
- keeps interactive behavior bounded to client islands that receive public-safe data.

## Current implementation slice

`web/` now uses Astro static output. The build-time loader accepts
`DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` and validates the current `dichiarazioni-pubbliche-public-v2` contract.
Development may use a clearly labeled fictional projection fixture.

Current public routes include Home, Explore, Fact-check, Person Record, Method and an
isolated ContentAudit UX fixture. Verify Studio routes are also present as private UX
fixtures but are not part of the public hosting boundary.

## Non-goals for this slice

- closing DP-105 public-schema v1;
- production domain/CDN selection;
- public authentication;
- replacing the existing Python projection security boundary;
- treating demo ContentAudit/Studio fixtures as stable data contracts.

## Acceptance criteria

- `npm run check` passes;
- `npm run build` produces static output;
- the same build passes with an explicit `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH`;
- frontend code contains no PostgreSQL/OmniRoute/provider access;
- fictional fallback content is visibly marked as demo content;
- existing Python projection/regression tests remain green;
- hosting/deploy details and MiniPC/CDN runtime proof are added before DONE.

## Validation / proof

Development receipt — Mac, 2026-09-23:

- `npm run check`: 0 errors, 0 warnings, 0 hints;
- static build succeeds both with the clearly labeled demo projection and with an explicit
  `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH`;
- current build emits 16 static pages across Home, Explore, Fact-check, Record, Method,
  ContentAudit and Verify Studio fixture routes;
- local preview HTTP smoke returned `200` for every current route family;
- existing deterministic backend suite remains green: 190 tests;
- frontend source contains no PostgreSQL, OmniRoute, provider-key or operational database
  access.

This Mac receipt is development proof only; runtime closure is recorded below.

## Tailnet preview receipt — 2026-09-24

- The static build is deployed under `/home/udodo/src/DichiarazioniPubbliche.it/web/dist` on
  MiniPC.
- `dichiarazioni-pubbliche-web.service` binds the same-origin static/read adapter to MiniPC loopback
  only.
- Tailscale Serve publishes the loopback service over HTTPS inside the tailnet; no Funnel
  or public-internet exposure is enabled.
- Acceptance: Astro check reports zero diagnostics, the 16-page static build succeeds, and
  the MiniPC URL returns HTTP 200 through Tailscale Serve.
- This remains a tailnet preview, not a public-internet release.

## Closure receipt — 2026-09-27

- DP-105 is DONE and the production projection is `dichiarazioni-pubbliche-public-v2`.
- The MiniPC mirror was synchronized from authoritative `main` without deleting
  runtime-local data or dependencies.
- `npm ci` repaired a stale optional Rolldown binding in the MiniPC dependency tree;
  `npm run check:design`, `npm run check`, and a production-projection
  `npm run build` then passed.
- The production projection currently has zero public dossiers, so the production build
  correctly emitted only the six non-record routes rather than demo records.
- `dichiarazioni-pubbliche-web.service` now serves the static site, `/api/v1/*`, and `/llms.txt`
  from one loopback origin. Live MiniPC checks returned HTTP 200 for `/`, `/metodo/`,
  `/api/v1/health`, `/api/v1/openapi.json`, and `/llms.txt`.
- Tailscale Serve remains the tailnet transport. No Funnel/public-internet exposure or
  production launch is claimed; that belongs to the launch/release tickets.
