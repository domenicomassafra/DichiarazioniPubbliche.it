# P1 — Civic Editorial

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

Design **Dichiarazioni Pubbliche**, an Italian fact-checking and public-evidence product, as if a top
independent-publication design team and a top public-service UX team collaborated on it.

The product must feel calm, rigorous, humane and highly readable — **not governmental,
not legalistic, not a newspaper clone and not SaaS**.

### Visual thesis

The interface feels like a beautifully edited evidence publication: typography,
whitespace, rules and source marginalia create trust. The claim is the main object. The
verdict is secondary. Evidence feels close to the sentence it supports.

### Typography

- display/claim serif: **Newsreader** or a similarly readable contemporary editorial
  serif, not fashion-magazine high contrast;
- UI/body: **Public Sans** or similar humanist/grotesk sans;
- timestamps/source reference numerals: restrained **IBM Plex Mono**, used sparingly;
- body 17–19px desktop equivalent, generous leading;
- long-form text measure 60–70 characters;
- no tiny 11–12px gray metadata except truly secondary legal/technical IDs.

### Palette

- warm ivory background `#F7F4EC`;
- near-black ink `#151515`;
- cobalt brand/link accent `#2456A6`;
- graphite secondary `#666864`;
- very pale blue/stone surfaces only where containment is necessary;
- finding colors are muted secondary cues, never the main composition.

### Geometry

- square or nearly square corners, 0–4px radius;
- 1px rules and strong alignment instead of shadows;
- almost no floating cards;
- one dominant reading column plus optional marginal/source rail;
- source/media objects may have bounded containers because they are genuinely discrete.

### Signature interaction

Use **evidence marginalia**: tiny numbered evidence markers appear beside a sentence or
observation; selecting one highlights the corresponding source row. This should feel like
excellent scholarly/editorial annotation, not footnote clutter.

### Status language

Write the state explicitly: `Supportata`, `Imprecisa`, `Contraddetta`, `Non risolta`,
`Servono altre prove`. Use a subtle text marker or short underline/block, not giant candy
pills.

### Imagery

Use photographs/video frames only when they are the actual source context. No stock
photos, monuments, courthouse imagery, gavels, seals or decorative politicians.

### Motion

Almost static Public UI. 150–220ms state/focus transitions. ContentAudit may animate a
timeline marker as playback moves. Studio may softly reveal newly persisted evidence.

### Hard rejects

No gradients. No glow. No glassmorphism. No generic dashboard cards. No KPI wall. No
decorative icon circles. No `AI` label as a brand device. No giant hero photo. No phone
mockup or presentation board. No external annotations. No fake user testimonials. No
person truth score.

### Content safety for mockups

Use realistic **illustrative** Italian content shapes. Do not attribute invented factual
claims to a real public figure. If a named person is visually needed, use neutral labels
such as `Figura pubblica` or use a clearly fictional name. The goal is UI, not political
content.

---

## HOME DESKTOP — paste this block into GPT Image

Generate one full-bleed straight-on desktop browser screenshot, 16:10, of the **Dichiarazioni Pubbliche
public homepage** in the Civic Editorial direction above. Show only the website UI; no
device frame, desk, Figma canvas, case-study labels, arrows, palette swatches or design
presentation around it.

Header is restrained: `Dichiarazioni Pubbliche` at left; `Fact-check`, `Esplora`, `Metodo`; search icon
at right. No login/signup unless truly necessary. Under the header, a type-led opening —
not a marketing hero — with headline `Verifica ciò che viene detto.` and one short line:
`Fact-checking di dichiarazioni, video, podcast e articoli. Con le fonti.`

Place one clear search field immediately below: `Cerca una verifica`. It searches existing
published records; do not make it look like an AI chat box.

Then show `Ultime verifiche` as **four editorial rows separated by fine rules**, not cards.
Each row: date/topic in small text, checked statement in readable serif, optional origin,
subtle finding-state text at right, chevron/link. The rows should scan like a carefully
edited index.

After the rows, one `Sotto la lente` featured ContentAudit: a real-looking media thumbnail
on the left and title/source/duration on the right, with a thin claim-moment timeline
under it. This is the only visually bounded feature block.

At the bottom of the viewport, show simple text links for `Esplora il record — Persone ·
Temi · Video e podcast` and `Come verifichiamo`.

Use warm ivory, near-black, cobalt links, Newsreader-like serif and Public-Sans-like UI.
Prioritize typography, whitespace and key lines. The page should still look premium if all
shadows are removed. Avoid symmetrical feature grids and verdict-colored cards.

---

## EXPLORE DESKTOP

Generate one full-bleed desktop browser screenshot of **Dichiarazioni Pubbliche — Esplora** using the
Civic Editorial system. No presentation packaging.

The top contains a page title `Esplora` and a large but editorially restrained search
input: `Cerca dichiarazioni, persone, temi, video…`. Immediately below are text tabs
`Tutto · Fact-check · Persone · Temi · Video e podcast`, with one simple active underline.

Show a compact controls row: `Filtri (2)` and `Più recenti`. Do not expose a permanent
wall of filters. Main results are a **single-column index/list** with generous white space
and rules. Each fact-check result shows date/topic, checked statement, speaker/origin,
source, one-line finding state and a source/evidence count or affordance. Person/topic
results use a different but equally simple list anatomy, not cards.

At wide desktop, a narrow right margin may show active filter chips or a small search
scope note, but the result list remains dominant. No photos unless the result is media.
Use typographic hierarchy rather than containers.

---

## FACT-CHECK DESKTOP

Generate one full-bleed desktop browser screenshot of a single **Dichiarazioni Pubbliche fact-check
detail** in Civic Editorial style. It must feel like an evidence-backed reading page, not
a dashboard.

Use a centered 680–760px main reading column with a narrow source marginalia rail. At top:
topic/date; a large serif original checked statement in quotation marks; origin/speaker,
role, source and timestamp; then a restrained text state such as `IMPRECISA` with a short
cobalt/ochre rule, not a giant pill.

Immediately below, a concise answer in slightly larger sans text: `La crescita è positiva,
ma il confronto dichiarato non è sostenuto dai dati disponibili.` This is visually the
second most important thing after the claim.

Then sections in a linear flow: `Perché`, a short readable rationale; `I numeri chiave`
only if needed, using a very simple table or horizontal comparison without dashboard
chrome; `Fonti` as clean source rows; `Momento originale` as one media clip; then subdued
links/disclosures for `Contesto e limiti`, `Metodo e provenienza`, `Correzioni e repliche`,
`Nel tempo`.

Place tiny numbered evidence markers beside rationale sentences and matching numbers in
the source rail/list. No evidence-card grid. No left navigation sidebar. No visual person
score.

---

## RECORD DESKTOP — Person or Topic

Generate one full-bleed desktop browser screenshot of an **Dichiarazioni Pubbliche Person Record** using
the Civic Editorial system. Use a fictional/neutral public figure identity; do not invent
claims for a real politician.

Header area is modest: name in serif, current public role in sans, one role-history link.
No giant portrait; if an avatar exists it is small and documentary.

Below: text navigation `Verifiche · Nel tempo · Media`. The main body is a chronological
stream of checked statements as editorial rows. Each row includes date, topic, statement,
source and state. Finding colors are subtle and belong only to the row. A neutral date
rail at left may group years/months but must not become a red/green performance graph.

Filters are compact and secondary. No KPI cards, no `X% true`, no count dashboard, no
"most false" summary. The page should feel like an archive a journalist or citizen can
scan comfortably.

---

## CONTENTAUDIT DESKTOP

Generate one full-bleed desktop browser screenshot of an **Dichiarazioni Pubbliche ContentAudit** for a
fictional Italian TV interview or podcast, Civic Editorial style.

Top: content title, source, publication date, duration. Then a wide media player occupying
the natural content width. Directly underneath: one thin timeline with 8–12 small claim
markers. Selected marker is cobalt; others remain neutral with tiny semantic ticks.

Below, title `Affermazioni verificate` and a single-column timeline/index of claim moments:
timestamp in restrained mono at left, checked statement in serif/sans, finding state in
small text at right. Selecting a row should conceptually reveal a concise finding/source
detail inline or in a restrained side sheet — do not show full transcript + all evidence
simultaneously.

The page should be unusually elegant for a media fact-check: media first, time second,
claims third. No dashboard panels.

---

## STUDIO SESSIONS DESKTOP

Generate one full-bleed desktop application screenshot of **Dichiarazioni Pubbliche Verify Studio —
Sessioni** in the same brand family but slightly cooler/denser. No admin-dashboard KPI
blocks.

Simple application header: `Dichiarazioni Pubbliche · Verify Studio`; `Sessioni`; primary action
`+ Nuova verifica`. Below, one search input and two headings: `In corso`, `Recenti`.

Sessions are plain rows, not cards: source icon/type, content title, started/updated time,
pipeline phrase (`Trascrizione completata · 8 claim · fonti 3/8`) and a restrained status
at right. Use rules and grouping. An empty-state example may appear subtly if useful.

No weekly insights, no accuracy percentages, no template gallery, no leaderboard, no
source-trust score.

---

## STUDIO WORKSPACE DESKTOP

Generate one full-bleed 16:10 desktop application screenshot of **Dichiarazioni Pubbliche Verify Studio
— Workspace** in Civic Editorial style. This is the only intentionally dense screen.

Use three purposeful columns without floating dashboard cards:

LEFT 30% — media/source at top, synchronized transcript below. Transcript lines have
timestamps and clear selected line; text itself is the navigation surface.

CENTER 25% — `Claim rilevate`: compact queue rows with timestamp, exact short statement,
state such as `Da verificare`, `Fonti trovate`, `In revisione`. One selected claim.

RIGHT 45% — selected claim workspace with original wording, normalized claim, concise
evidence observations and source rows grouped contextually by what they establish. Show a
clear distinction between `recuperata`, `approvata`, `verifica` and `revisione` states.

Top has one compact text pipeline summary: `Trascrizione ✓ · 14 claim · Fonti 8/14 ·
Verificate 5/14`. Detailed provider state is not a permanent panel.

Bottom/right actions: `Metti in attesa`, `Invia a revisione`. Publication is not a bright
primary action on an analysis screen. Use ivory/white surfaces, dark text, cobalt focus
and fine rules. No glowing AI, no activity feed, no fourth pipeline column.

---

## HOME MOBILE

Generate one full-screen **390×844 mobile web UI** for Dichiarazioni Pubbliche Home, Civic Editorial.
Show only the actual page — no iPhone hardware frame.

Header: wordmark, search, menu. Then compact headline and one-line description, followed
by a full-width search input. Show three recent fact-check **rows** with readable claim
text; state appears as small written text, not bright pills. Then one media feature with
thumbnail and a tiny timeline. End viewport with `Esplora` text links and `Metodo`.

No bottom tab bar unless functionally essential. No desktop sidebars stacked vertically.
Touch targets are generous, text is not tiny, and whitespace remains intentional.

---

## FACT-CHECK MOBILE

Generate one full-screen **390×844 mobile web UI** for one Dichiarazioni Pubbliche fact-check in Civic
Editorial style. No device frame.

Linear order: topic/date -> large readable checked statement -> origin/source/timestamp ->
written finding state -> one-sentence answer -> `Perché` rationale -> two or three key
numbers if material -> visible source rows -> original media moment. Secondary method,
limits and corrections appear after primary evidence as simple disclosures/links.

Use a 17–18px equivalent body, excellent line height, no tiny side-by-side desktop
fragments, no horizontal scrolling, no sticky status bar stealing space.
