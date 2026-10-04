# P5 — Temporal Evidence Tape

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

Design the complete **Dichiarazioni Pubbliche** product around its most defensible differentiator:
statements and evidence exist **at moments in time**. Make chronology tangible without
turning the product into a graph database or a colorful politician score timeline.

### Visual thesis

Time is the quiet connective tissue. A restrained evidence tape lets users move from the
exact source moment to the finding, evidence reference dates, corrections and later
related statements.

### Typography

- UI/body: **IBM Plex Sans** or similar precise, humane sans;
- quotes/original statements: **IBM Plex Serif / Newsreader-like** serif;
- timestamps/dates/IDs: **IBM Plex Mono** with tabular numerals;
- strong date/time hierarchy without sacrificing claim text.

### Palette

- cool paper `#F6F7F8`;
- ink `#121820`;
- temporal blue `#2E5D9F`;
- warm signal `#D76842` for selected/attention state;
- steel `#7B8794` and pale gray for unselected rails;
- semantic finding color remains subtle/textual and separate from timeline identity.

### Geometry

- lines, ticks, rails and alignment carry the design;
- very few cards;
- selected items may use a pale background band;
- 2–4px radius at most for inputs/controls;
- timestamps use a fixed column or baseline where possible.

### Signature interaction

The **Evidence Tape** appears only when chronology matters. It can connect:

- exact source timestamp;
- claim statement time;
- evidence reference/publication date;
- verification/publication date;
- correction/reply date;
- reviewed later related statement.

It is a navigation/provenance rail, not a causal diagram. It never aggregates a person's
truthfulness.

### Motion

ContentAudit playback advances a cursor on the tape. Selecting a claim scrolls/jumps to
its exact media moment. Studio transcript selection moves the same temporal cursor. Public
Fact-check uses motion only when user actively explores chronology.

### Hard rejects

No node graph. No spaghetti connectors. No all-screen timeline. No red/green person
history. No score. No tiny chart ticks. No dashboard cards. No sci-fi/HUD style. No
case-study packaging outside the product.

Use fictional/neutral content; do not invent controversial claims for real public figures.

---

## HOME DESKTOP

Generate a full-bleed 16:10 **Dichiarazioni Pubbliche Home** in Temporal Evidence Tape style. UI only.

Header and search are conventional. Intro is compact. `Ultime verifiche` uses clean rows.
Give each row a small date/timestamp alignment mark at the left edge, creating a subtle
vertical temporal rhythm without drawing one giant timeline through the homepage.

The dominant featured section is `Sotto la lente`: one media item with a beautiful thin
horizontal Evidence Tape showing claim moments across its duration. A selected moment
shows timestamp, short checked statement and link to the finding.

Under it, simple Explore/Method paths. No hero photo, no KPI cards, no person rankings.

---

## EXPLORE DESKTOP

Generate full-bleed **Esplora** in Temporal Evidence Tape style.

Search first; result-type tabs; filters on demand. Results are chronological rows with a
fixed narrow date column and statement/source/state columns. A small `Vista: elenco / nel
tempo` switch may exist: the default is list; `nel tempo` shows a **neutral chronological
distribution** useful for filtering, not verdict proportions.

Selected date range on the neutral tape filters results. Avoid multi-colored verdict
scatterplots.

---

## FACT-CHECK DESKTOP

Generate full-bleed **Fact-check** in Temporal Evidence Tape style.

Top reading hierarchy remains claim/source/state/answer. Along one edge or directly below
the header, show a thin **record tape** with only meaningful points:

`statement 20 Sep 2024` -> `evidence reference 2024` -> `review 22 Sep 2024` -> optional
`correction 03 Oct 2024`.

The tape is quiet and secondary; the claim remains dominant. Rationale follows in a
comfortable column. Source rows include both publication date and reference period where
material, visually clarifying why time matters. Media moment uses the same timestamp
language. Corrections/later relations extend the tape lower down only if present.

No timeline for its own sake; four meaningful points maximum in the first viewport.

---

## RECORD DESKTOP

Generate a full-bleed fictional Person/Topic **Record** where the Temporal Evidence Tape
is especially useful.

Header is compact. Main stream shows chronological statements grouped by year/month.
There is a **neutral master time rail** with ticks and labels but no verdict colors. When
one individual row is selected, its state and reviewed relation to another statement may
be shown locally.

Filters let users narrow topic/date/media. The tape is navigation. Do not summarize the
person's history as true/false counts.

---

## CONTENTAUDIT DESKTOP

Generate the signature full-bleed **ContentAudit** in Temporal Evidence Tape style.

Large media player, source/title/date/duration. Directly beneath, a highly refined
horizontal tape spanning the media duration. Chapter boundaries are subtle. Checkable
claim markers use shape/selection differences; finding state is written in the associated
claim row rather than encoded by a rainbow of colors.

Below, a synchronized claim list. Selecting timestamp `12:42` visibly aligns player,
tape cursor and claim row. A selected claim reveals concise finding + source list in a
single side region or inline block.

This must look like a purpose-built fact-check interface for long media, not a normal
video page with colored dots added afterward.

---

## STUDIO SESSIONS DESKTOP

Generate full-bleed **Verify Studio — Sessioni** in Temporal Evidence Tape style.

Simple session list; source type/title; created/last-updated time; compact pipeline phrase.
In-progress rows may show a tiny linear progress **sequence of named stages**, not a
percentage meter: `Transcript -> Claim -> Fonti -> Verifica`. Blocked stages are written
clearly.

No analytics dashboard. No full timeline unless one session is previewed.

---

## STUDIO WORKSPACE DESKTOP

Generate a full-bleed 16:10 **Verify Studio Workspace** in Temporal Evidence Tape style.

Three columns:

LEFT — media and transcript. A fixed temporal gutter shows timestamps; selected transcript
range is connected to the media cursor.

CENTER — claim list ordered by source time. A narrow vertical tape through the timestamps
shows the sequence of claims without verdict-color scoring.

RIGHT — selected claim/evidence. Evidence rows show reference date/publication date where
relevant; a compact mini-tape can compare statement cutoff with evidence dates, making it
visually obvious when evidence would be "future" and therefore unusable for that check.

Top pipeline summary is compact text. The selected claim is the organizing unit. Use
blue/warm signal for selection/focus, not status performance.

This screen should make temporal provenance feel natural and powerful, not technical for
its own sake.

---

## HOME MOBILE

Generate the actual full-screen **390×844 mobile Home**, no phone frame, Temporal Evidence
Tape style.

Compact header/headline/search. Recent checks as rows with visible date hierarchy. One
ContentAudit feature shows a touch-friendly mini tape below its thumbnail. The tape has
few large markers, not microscopic points. Explore/Method links below.

No bottom app bar by default, no desktop timeline squeezed into the phone.

---

## FACT-CHECK MOBILE

Generate the actual full-screen **390×844 mobile Fact-check**, no device frame.

Linear claim/source/state/answer/rationale first. Insert a compact horizontal `Nel tempo`
strip only after the answer or where chronology materially explains the finding. Source
rows clearly distinguish `pubblicato` and `riferimento` dates. Media moment and
correction/history follow.

The temporal language should help comprehension without stealing vertical space from the
actual fact-check.
