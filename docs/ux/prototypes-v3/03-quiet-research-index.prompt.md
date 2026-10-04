# P3 — Quiet Research Index

## IMAGE GENERATION OUTPUT CONTRACT — READ FIRST

This file is a **UI image-generation prompt pack**, not content to visualize.

For every generation request in this file, the output must be **only a straight-on
screenshot of the actual Dichiarazioni Pubbliche website or Verify Studio application** described by
that request.

Never render or summarize this prompt, a handoff, a Markdown document, repository paths,
Git status, tickets, architecture notes, research notes, design-spec annotations, palette
swatches, numbered briefing panels, an infographic, a moodboard, a Figma canvas, a case
study, a presentation slide, a browser/device mockup placed inside another scene, or any
other meta-design artifact.

The visible text in the generated image must be **only plausible product UI copy** that a
real Dichiarazioni Pubbliche user could see. Do not print instructions from this prompt into the image.

Treat the product as already designed and implemented. The task is to render one polished
production-quality screen from that product in this visual system, not to explain the
system.

## Master direction

Design the complete **Dichiarazioni Pubbliche** product as the best public research/reference tool for
checking statements — fast, legible, evidence-native and almost frictionless.

This direction deliberately moves away from magazine/newspaper cues. It should feel like
a product people trust because it is **clear, searchable and inspectable**, not because it
looks prestigious.

### Visual thesis

Search first. Claim second. Evidence exactly where it is needed. Almost no decorative
chrome.

Think of the product quality found in excellent research software and reference indexes,
but warmer and easier for the general public.

### Typography

- UI/body: **Source Sans 3** or similarly excellent neutral sans;
- checked/original statements: **Literata** or similarly robust book serif, used only to
  distinguish quoted/public wording;
- technical source IDs/timestamps: **IBM Plex Mono**, sparingly;
- highly readable 16–18px body;
- compact metadata through weight/spacing, not tiny font size.

### Palette

- paper white `#FCFCFA`;
- deep ink `#17202A`;
- cool navy `#375A78`;
- restrained teal `#2E7D6B` for links/selected evidence where appropriate;
- mist gray `#E8ECEF` / `#F4F6F7` for separators and selected rows;
- status colors muted and subordinate.

### Geometry

- 0–6px radius only for interactive fields/drawers;
- results, claims and sources are rows/lists;
- no shadows except overlays;
- tight but breathable vertical rhythm;
- filters and search are stronger than decorative branding.

### Signature interaction

**Inline evidence anchors.** A rationale sentence such as `Il dato disponibile per il
2024 è inferiore... [1]` has a small numbered source marker. Selecting it opens/highlights
the exact source item and relevant observation. Evidence is grouped by what it establishes
rather than pooled into a gallery.

### Search behavior

Search is not chat. It is a high-quality retrieval interface with clear query input,
scope, filters and result types. Advanced filters appear only when requested.

### Status

Compact word + small icon/marker. Avoid colorful badges as texture.

### Motion

Very little. Search/filter result updates crossfade or preserve position. Evidence drawer
appears with a brief 180–220ms transition. Studio state updates without theatrical loading.

### Hard rejects

No AI chat bubbles. No gradient. No "ask anything" magic. No research KPI tiles. No
academic paper aesthetic so dense that normal readers struggle. No nested filter sidebars.
No cards for individual sources. No case-study packaging around generated screens.

Use fictional/neutral claims and identities in mockups rather than assigning invented
statements to real political figures.

---

## HOME DESKTOP

Generate one full-bleed 16:10 desktop browser screenshot of **Dichiarazioni Pubbliche Home** in Quiet
Research Index style. Show only the website UI.

The first viewport is intentionally simple. Header: `Dichiarazioni Pubbliche`, `Fact-check`, `Esplora`,
`Metodo`, search icon. Center/left: concise headline `Verifica ciò che viene detto.` and
one short sentence. The strongest object is a large but plain **search field**:
`Cerca una dichiarazione, una persona, un tema…`.

Directly below, show `Ultime verifiche` as a compact search-result-like list, not feature
cards: date/topic, statement in Literata-like serif, source/origin, written finding state
and evidence link count. Four rows maximum.

After that, one `Sotto la lente` media item using a restrained thumbnail + a tiny claim
timeline, then a simple `Esplora` text row for Persone / Temi / Video e podcast and a
`Metodo` link.

The page should feel extremely useful within three seconds. No decorative hero image, no
brand manifesto panel, no KPI/statistics blocks.

---

## EXPLORE DESKTOP

Generate one full-bleed desktop screenshot of **Dichiarazioni Pubbliche — Esplora** in Quiet Research
Index style.

This is the direction's hero screen. Large search bar at top with clear query text. Under
it, simple result-type tabs and one `Filtri` button showing active count. When filters are
active, show a narrow removable-filter row; keep advanced controls hidden by default.

Main results occupy a calm central column roughly 850–1000px wide. Each result is one
scannable row with: result type, date, checked statement or entity name, source/origin,
topic, finding state and a small `3 fonti` or evidence affordance. Use bold query-match
highlighting sparingly.

A narrow right rail may show `Query` / `Ordinamento` / active scope on large screens, but
it must not compete with results. No images unless result is a media object. No facets
wall. No pagination dashboard; use simple pagination/load-more with clear state.

---

## FACT-CHECK DESKTOP

Generate one full-bleed desktop Fact-check in Quiet Research Index style.

At top of a readable centered column: original checked statement in Literata-like serif;
source/origin/date/timestamp immediately below; compact written finding state; then a
clear one-sentence answer.

The rationale is plain readable prose. Insert small inline numbered evidence anchors
`[1]`, `[2]`, `[3]` beside the exact statements they support. On a wide viewport, a narrow
right evidence rail shows the currently selected source: source name, date, what it
establishes, link. Other sources are listed below the rationale as simple rows grouped
under headings such as `Stabilisce il dato`, `Aggiunge contesto`, `Limita la conclusione`.

Show key data only as a clean table/inline comparison. Then original media moment. At the
bottom: simple text disclosures for method/provenance/corrections/history.

It should feel more like reading an excellent research memo than a news article, but still
be friendly to a normal citizen. No cards around each paragraph/source.

---

## RECORD DESKTOP

Generate a full-bleed Person or Topic **Record** in Quiet Research Index style using
fictional identity/content.

Header is compact and informational. Below it, a large `Cerca in questo record` field,
then text filters for date/topic/type. Main content is a chronological result list using
the same anatomy as Explore. A small neutral year index can remain sticky at left on wide
screens.

The visual system must make it obvious this is a **searchable record**, not a profile
scorecard. No aggregate verdict visualization, no count/KPI cards, no giant portrait.

---

## CONTENTAUDIT DESKTOP

Generate a full-bleed **ContentAudit** in Quiet Research Index style.

Top: media title/source/date/duration and media player. Under player, a simple timestamp
rail with claim markers. Below, a split but calm structure: left/center claim-moment list;
right selected-claim evidence panel.

Each claim row: timestamp, statement, compact state. Selecting a row updates the right
panel with one-sentence finding, 2–4 evidence items and exact source links. Do not expose
full transcript by default; offer `Mostra estratto` for the selected moment.

Use no dashboard metrics. The experience should resemble a high-end searchable research
record attached to media.

---

## STUDIO SESSIONS DESKTOP

Generate full-bleed **Verify Studio — Sessioni** in Quiet Research Index style.

Top header has product name, session search and `+ Nuova verifica`. Main page is a clean
work queue: `In corso`, `Recenti`. Rows show source type, title, last update, pipeline
phrase and blockers if any. Add quick text filters only if useful.

This should look like a serious research workspace, not a dashboard. No sidebar full of
modules; no analytics. Use a simple split layout only if a selected session preview is
shown.

---

## STUDIO WORKSPACE DESKTOP

Generate full-bleed 16:10 **Verify Studio Workspace** in Quiet Research Index style.

The layout is optimized for lookup and evidence tracing:

LEFT 28% — media/source and searchable transcript. Transcript lines are selectable
result-like rows with timestamp.

CENTER 27% — claim index with search/filter at top. Each claim row has timestamp,
statement, current workflow state and small count of found evidence.

RIGHT 45% — selected claim research view. Original wording, normalized claim, rationale
draft/state, then contextual evidence grouped by question/observation. Each evidence row
contains source, date, snippet/structured observation, retrieval/review state and link.

At top, one compact pipeline text summary and one blocker warning if present. Evidence
retrieval state and review approval must be visually distinct. Actions: `Approva fonte`,
`Rifiuta`, `Invia a verifica` or equivalent context-appropriate actions; publication is a
later separate phase.

No generic chat pane. No glowing agent status. No activity feed unless opened on demand.

---

## HOME MOBILE

Generate one actual **390×844 mobile webpage**, no phone frame. Quiet Research Index Home.

Top wordmark/search/menu. One compact headline. Full-width search input. Then three recent
results as clean rows with claim, date/source and written state. One media feature below.
Simple Explore and Method links. No bottom app bar by default. No card stack.

The mobile page should feel like a reference tool you can use quickly in a conversation.

---

## FACT-CHECK MOBILE

Generate one actual **390×844 mobile webpage**, no hardware mockup. Quiet Research Index
Fact-check.

Linear reading order: claim -> source/date -> written state -> one-sentence answer ->
rationale with inline `[1][2]` source markers -> key data if needed -> source rows ->
media moment -> method/corrections/history disclosures.

Selecting an evidence marker would conceptually open a full-height accessible source
sheet; represent only one small selected-evidence affordance if needed, not multiple
floating panels. Excellent text size and tap targets.
