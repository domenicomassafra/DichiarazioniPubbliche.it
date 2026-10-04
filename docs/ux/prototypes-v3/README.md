# Dichiarazioni Pubbliche — Prototype Prompt Packs v3

These are five materially different product-wide design directions derived from
`docs/33-ui-ux-deep-design-research-v3.md`.

They all implement the same information architecture from
`docs/32-public-ux-architecture-v2.md`. Differences are visual language, density,
composition and interaction emphasis — not feature scope.

## Directions

1. `01-civic-editorial.prompt.md`
2. `02-italian-modernist-ledger.prompt.md`
3. `03-quiet-research-index.prompt.md`
4. `04-visual-journalism.prompt.md`
5. `05-temporal-evidence-tape.prompt.md`

Historical generated visual outputs are indexed in
[`generated-receipts.md`](generated-receipts.md). They are non-canonical research
receipts, not implementation or product authority.

## How to use with GPT Image

Do **not** paste the whole file and ask for a design board. Pick one screen block at a
time.

Start with `HOME DESKTOP`, generate all five directions, then generate `FACT-CHECK
DESKTOP` for all five. Evaluate those ten images before generating the remaining screens.

Every file contains:

- a master art-direction contract;
- hard anti-slop rules;
- one prompt block for each major product surface;
- mobile prompts.

Images must show the product UI itself full-bleed, not phones on a desk, design-system
slides, annotations, mockup packaging or case-study presentation.

## Generation discipline

For the first round, use only these ten prompt blocks:

1. P1 Home desktop
2. P2 Home desktop
3. P3 Home desktop
4. P4 Home desktop
5. P5 Home desktop
6. P1 Fact-check desktop
7. P2 Fact-check desktop
8. P3 Fact-check desktop
9. P4 Fact-check desktop
10. P5 Fact-check desktop

Do not generate the whole product for a weak direction merely because its first image was
pretty. First ask whether the visual system survives both **retrieval/home** and
**evidence-heavy reading**.

### Reject before scoring if GPT Image does any of these

- presents the screens as a portfolio/case-study board instead of the actual product;
- invents dashboard KPI cards or statistic tiles;
- turns status into bright green/yellow/red pill texture;
- adds an AI orb, sparkle, chatbot or glowing agent metaphor;
- adds stock political portraits merely to fill space;
- shrinks body/metadata text below plausible product readability;
- creates a generic left SaaS sidebar when the prompt does not require one;
- uses 3 equal rounded feature cards to resolve an ambiguous area;
- changes the frozen UX-v2 information hierarchy to make the composition easier.

If a direction repeatedly triggers its named failure mode in
`docs/33-ui-ux-deep-design-research-v3.md`, reject the direction or tighten the prompt;
do not keep polishing an image that violates the product thesis.
