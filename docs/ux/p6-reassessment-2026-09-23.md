# P6 reassessment — why the first hybrid still felt too busy

Date: 2026-09-23

## Conclusion

The uncertainty about P6 is justified. The problem is not primarily typography or color.
It is **simultaneous visual ambition**.

The full corpus repeatedly says:

- screen job before styling;
- subtraction is the default;
- Home has exactly four jobs;
- Public uses typography, whitespace and lists before containers;
- primary rationale and evidence stay close and readable;
- timelines/visualizations exist only when they explain something;
- Studio can be dense, Public should not become a newsroom/dashboard workspace.

The P6 generation followed many individual rules but violated the higher-order rule by
showing too many valid ideas together.

## What the first P6 got right

- strong editorial typography;
- recognizable cobalt/ink/paper identity;
- restrained geometry;
- no generic SaaS card wall;
- a useful recent-check ledger;
- ContentAudit and Workspace can clearly benefit from media/time synchronization.

## What it got wrong

### 1. It confused system capability with simultaneous visibility

Dichiarazioni Pubbliche can support charts, source rails, timelines, media, provenance and dense rows.
That does not mean a single screen should display all of them.

### 2. P4 and P5 leaked into ordinary Public pages

Visual Journalism and Temporal Evidence Tape are strongest when the content demands them.
Making them globally visible turns a useful signature into visual noise.

### 3. The Home became too demonstrative

The Home should explain, search, show recent checks and feature one ContentAudit. The
generated hybrid tried too hard to demonstrate the design system itself.

### 4. Status treatment remained too visually repetitive

Even muted pills become a texture when repeated row after row. Status should be readable,
but the claim text and source relationship should dominate.

### 5. The system underused P3's strongest lesson

P3 was originally framed as the fastest serious way to find a claim and inspect evidence.
Its search/result/evidence-adjacency model aligns unusually well with UX v2. It should be
the interaction baseline, even if its exact visual aesthetic is too academic by itself.

## Revised model

```text
PUBLIC DEFAULT
P3 interaction clarity
  + P2 typographic/Italian identity

SPECIALIST MODULES
P4 evidence visual       only when it explains the finding
P5 evidence tape         only when chronology changes understanding

PRIVATE STUDIO
P3 information tracing
  + P2 grid discipline
  + P5 synchronization
  + P4 working visual only when useful
```

## New visual acceptance gates

Reject a Public generation if any of these is true:

1. the first viewport has more than one dominant visual anchor;
2. a user must visually decode the design system before finding the claim/search/result;
3. a timeline appears where chronology is not the user task;
4. a chart appears where prose or a two-number comparison would explain the fact better;
5. status pills become more visually salient than claim text;
6. more than one large image/video object appears before the core task is clear;
7. decorative slogans/marginalia are used to make the layout feel designed;
8. removing all icons makes the page hierarchy collapse;
9. removing all status colors makes the page incomprehensible;
10. Home no longer feels primarily like an entry point to a searchable public record.

## Next prototype

The next image should **not** be another broad hybrid showcase. Generate one screen only:

**Home desktop — P6.2 Calm Evidence Index**

Requirements:

- restrained header;
- compact purpose statement;
- search is the strongest interaction;
- recent checks appear before the feature;
- four rows maximum;
- status is text-first and quieter than the checked statement;
- one featured ContentAudit after the rows;
- no chart;
- no visible timeline unless it can remain a tiny secondary affordance;
- no decorative institutional image;
- no side slogans;
- no footer feature grid in the first viewport;
- large areas of intentional whitespace;
- distinctive typography/alignment should carry the brand.

Only after this Home feels obviously calmer should Fact-check and ContentAudit be regenerated.
