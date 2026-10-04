# P4 — Visual Journalism

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

Design **Dichiarazioni Pubbliche** as a world-class public-interest visual journalism product. The
global system is restrained, but each important verification can have **one evidence
visual** that explains its central factual issue.

This direction is inspired by the craft principles of excellent graphics desks and
visual-story teams, not by a magazine homepage or infographic decoration.

### Visual thesis

One record, one visual idea. The interface gives the evidence enough room to explain the
finding, then gets out of the way.

### Typography

- editorial display serif with strong screen readability, in the
  **Newsreader/Tiempos-like** family;
- compact grotesk such as **Source Sans 3 / Graphik-like** for UI, labels and body where
  appropriate;
- tabular sans/mono only inside data visuals and timestamps;
- headline scale may be expressive, but body copy remains normal and comfortable.

### Palette

- global shell: warm white `#FAF8F3`, ink `#151515`, quiet gray;
- global brand accent: deep cobalt `#264B8A`;
- each **record** may use one additional evidence accent chosen for the visualization,
  e.g. coral, teal, ochre — never chosen from a person's party/identity;
- status remains text-first and independent of story accent.

### Composition

- editorial layout can change with the evidence type while navigation/system grammar
  remains fixed;
- use full-width or breakout visual only when it explains the finding;
- lists remain lists; not every record gets a bespoke hero;
- whitespace and visual rhythm create hierarchy.

### Signature interaction

**One evidence visual per record**: a chart, annotated source excerpt, before/after,
timeline or media comparison that creates an immediate explanatory insight. It must
answer a factual question, not decorate the page.

### Motion

Only evidence-driven motion: a chart may animate from claimed value to observed value;
ContentAudit may synchronize selected claim moment; user can stop/skip, reduced motion
shows the final state. No page entrance choreography.

### Hard rejects

No infographic wall. No six charts because charts look good. No scrollytelling on every
page. No stock illustration. No gradient editorial hero. No magazine card grid. No fake
data. No outside case-study packaging in generated images.

Use fictional/neutral illustrative claims. If a chart is shown, numbers are placeholder
design data, not presented as real claims about a real political actor.

---

## HOME DESKTOP

Generate a full-bleed 16:10 **Dichiarazioni Pubbliche Home** in Visual Journalism style. UI only.

Keep the header and search highly conventional. Above the fold: compact statement of
purpose, search, then one strong **lead fact-check visual** taking roughly half the width:
a simple annotated comparison/timeline/media still whose takeaway is understandable at a
glance. Beside it, the checked statement, source/date and concise one-sentence finding.

Below the lead, show three recent fact-checks as plain rows — not three visual cards. Then
one `Sotto la lente` ContentAudit media item with a thin claim timeline. End with simple
Explore/Method paths.

The lead visual is the one dominant anchor. Do not fill the homepage with multiple charts
or imagery. The shell remains calm enough that a new lead visual can change week to week.

---

## EXPLORE DESKTOP

Generate full-bleed **Esplora** in Visual Journalism style.

Explore stays utilitarian: strong search, text tabs, filters on demand, result rows. Do
not force visual-story treatment into the archive. Where a result has a meaningful visual
artifact, show one tiny thumbnail/icon at far left; otherwise use text.

The page should prove that the expressive brand can also become quiet when retrieval is
the job. Use typography and a single accent, no card wall.

---

## FACT-CHECK DESKTOP

Generate a full-bleed desktop **Fact-check** in Visual Journalism style.

At top: original checked statement, source/origin/date, written state and concise answer.
Immediately after the answer, create **one large evidence visualization** tailored to a
numeric comparison: for example claimed value vs observed values across several comparable
countries/periods, with a clear explanatory headline and source note. The visual uses one
record accent and restrained labels; it is not a dashboard chart.

After the visual, a readable `Perché` explanation, primary source rows, original media
moment and secondary method/correction/history links. The visualization and text should
feel authored together.

Do not add a permanent sidebar full of widgets. One visual idea, one reading path.

---

## RECORD DESKTOP

Generate a full-bleed Person/Topic **Record** in Visual Journalism style, fictional
identity/content.

The archive itself remains neutral: identity/scope header, filters, chronological rows.
Introduce at most one useful aggregate **content navigation visual** — for example a
neutral histogram of statement volume by year/topic that does not encode correctness.
This visual is for navigation, not judging the person.

No supported-vs-false pie chart, no score. Individual rows retain their own written state.

---

## CONTENTAUDIT DESKTOP

Generate the strongest screen of this direction: a full-bleed **ContentAudit** for a
fictional long-form interview/podcast.

Large media player at top/left and an exceptionally clear visual timeline below it. The
timeline should be treated as an authored graphic: chapters, claim moments and selected
moment are obvious without excessive colors. At right or below, show one selected claim
with concise finding and 2–3 sources.

Below the fold visible in the screenshot, begin a chronological claim list. A small
overview strip may show where clusters of checkable claims occur, but it must not become a
score of the speaker.

This screen should make someone think: `I have never seen a fact-checked podcast presented
this clearly.`

---

## STUDIO SESSIONS DESKTOP

Generate **Verify Studio — Sessioni** in the same visual family but product-first. Simple
header, search, `+ Nuova verifica`, in-progress and recent rows. Use small media thumbnails
only when they help identify sessions.

No charts or visual-story treatment here. The design quality comes from typography,
spacing, state clarity and one compact progress phrase per row.

---

## STUDIO WORKSPACE DESKTOP

Generate full-bleed 16:10 **Verify Studio Workspace** in Visual Journalism style.

Three-column operator layout: media/transcript; claim queue; selected claim/evidence. The
selected claim right panel may contain one **working evidence visual** when helpful — e.g.
a small data comparison built from approved observations — but it is clearly an analysis
tool, not a final published graphic.

Use the same chart typography/source-note grammar as Public, creating continuity between
investigation and final communication. Show source citations immediately under the visual.

No KPI dashboard, no fourth activity column, no glowing AI analysis.

---

## HOME MOBILE

Generate the actual full-screen **390×844 mobile Home**, no device frame. Visual
Journalism direction.

Compact heading + search. One lead fact-check with a **single small but legible evidence
visual** and takeaway. Then three recent fact-check rows. One media feature below.

Do not attempt to miniaturize a desktop chart; choose a mobile-specific visual form with
large labels and one takeaway.

---

## FACT-CHECK MOBILE

Generate the actual full-screen **390×844 mobile Fact-check**, no hardware frame.

Claim/source/state/answer first. Then one vertically optimized evidence visual with direct
labels, no legend hunt, no tiny axes. `Perché` rationale and sources follow. Media/context
and method later.

The mobile visual should remain understandable at a glance and with increased text size.
