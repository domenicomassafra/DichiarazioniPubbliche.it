# Dichiarazioni Pubbliche web frontend

This directory contains the real public frontend plus shared design/Studio prototype
foundations for Dichiarazioni Pubbliche.

## Architecture

- **Astro 7**, static output by default;
- React is used only for bounded interactive islands (Explore filtering, Content
  selection, and currently-unrouted Studio prototype components);
- fonts are self-hosted from npm packages;
- the public frontend consumes only the fail-closed `dichiarazioni-pubbliche-public-v2` projection;
- there are no LLM calls, provider calls, database credentials, or operational-table reads
  in the public request path.

This matches the repository architecture: public HTML is pre-rendered from an approved
projection and can be served from a static host/CDN.

## Development

```bash
cd web
npm install
npm run check
npm run dev
```

Development does not silently fall back to synthetic data. To use
`src/data/demo-projection.json`, opt in explicitly with
`DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1`. The fixture contains fictional content only.

## Build from an explicit public projection

Generate or provide an `index.json` produced by
`dichiarazioni_pubbliche.public_projection.write_public_bundle`, then:

```bash
cd web
DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH=/absolute/path/to/index.json npm run build
```

The build fails closed when `DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH` is missing. Synthetic
demo data is available only for an explicit local demo build:

```bash
DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build
```

Do not set `DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1` in a deployed/public build.
Configured public builds reject the repository's known demo record IDs and dataset
fingerprint even when the fixture is copied under another filename. When demo mode
is explicitly enabled, the generated pages and sitemap remain non-indexable.
All public builds validate the dossier count and fingerprint, including older v2
projections without a first-class Content collection.
Run `npm run check:projection-boundary` for isolated regression builds of both cases
and an intentionally empty public projection shape. This test fixture is not
editorially approved content and must never be deployed.
Public builds exclude the Studio route and discard otherwise-unreferenced
Studio hydration chunks; the independent informational-preview audit verifies
that no private Studio JS is shipped.

The build fails closed when:

- `schema_version` is not `dichiarazioni-pubbliche-public-v2`;
- `dossiers` is not an array;
- the projection does not explicitly set `methodology.aggregate_person_score` to `false`.

This guard is not a replacement for backend publication gates. It prevents the frontend
from silently accepting a different read-model contract.

## Current implementation routes

These are the routes implemented by the current frontend baseline. They intentionally
remain listed here until DP-422 performs the canonical v3 route migration; they are not
the product-architecture authority.

- `/` — Home;
- `/esplora/` — public search/filter interface;
- `/fact-check/<finding>/` — one published finding version;
- `/record/<person>/` — person record using the shared Record grammar;
- `/contenuti/intervista-servizi-pubblici/` — ContentAudit UX fixture while the public
  schema is still being expanded;
- `/metodo/` — methodology document surface;

The canonical target route families are `/dichiarazioni/{slug}/`, `/persone/{slug}/`,
`/temi/{slug}/`, `/contenuti/{slug}/` and `/tracce/{id}/`, plus Home, Explore and Method.
See `docs/35-public-product-architecture-v3.md` for redirect policy and supporting trust
pages.

The ContentAudit fixture data are intentionally isolated from the public projection and
are visibly demo-only until their stable contract exists. Studio components/fixtures in
`src/components/StudioWorkspaceClient.tsx`, `src/data/studio.ts`, and
`prototypes/verify-studio/` are design/prototype evidence only: there are currently no
live `/studio/*` routes under `src/pages`.

## Design authority

Visual implementation follows:

1. `PRODUCT.md`;
2. `docs/35-public-product-architecture-v3.md`;
3. `DESIGN.md`;
4. `docs/ux/design-source-registry-v1.md`.

`docs/32-public-ux-architecture-v2.md` and older generated reference images are retained
as design history, not implementation authority. The maintained v3 visual mockups live in
`prototypes/final-hybrid/`.
