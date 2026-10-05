# Dichiarazioni Pubbliche — Public Marketing & Brand Context

Date: 2026-10-05
Status: canonical public-facing marketing context for the v4 redesign
Owner ticket: DP-423

This document is a bounded synthesis of existing product, naming, UX and competitive
research. It does not change product policy, add public routes, or authorize claims that
are not supported by the public record. When it conflicts with `PRODUCT.md`,
`docs/35-public-product-architecture-v3.md`, or `DESIGN.md`, those canonical documents
win.

## 1. Brand promise

**Dichiarazioni Pubbliche is a verifiable memory of public statements.**

The product preserves what a public figure said, where and when it was said, the source
that supports the attribution, the evidence relevant to a checkable claim, and the later
history of review, correction, reply, clarification or change.

The shortest approved public description is:

> Dichiarazioni pubbliche, fonti, contesto, verifiche, cambi e correzioni in un record
> consultabile e versionato.

The longitudinal brand line remains:

> La parola lascia una traccia.

The promise is **inspectability**, not omniscience: the reader should be able to follow the
record back to its wording, source, evidence and history instead of being asked to trust a
score, a logo, or an AI-generated conclusion.

## 2. Primary public audiences

### Citizens and readers

They want to understand what was actually said, whether a statement has been reviewed,
what evidence supports the published finding, and what changed later.

### Journalists, researchers and fact-checkers

They need stable, citable records with original wording, provenance, chronology,
corrections and machine-readable paths back to the source.

### Developers and agents

They need stable URLs, structured public data, JSON/JSON-LD/OpenAPI and deterministic
public records that remain usable without a live LLM in the request path.

### Public figures and representatives

They need a visible, versioned correction and right-of-reply path that does not silently
rewrite the historical record.

Maintainers are an important product constituency, but their primary surface is the
private/operator system and project documentation rather than the public Home page.

## 3. Jobs and trigger situations

The public product should make these jobs obvious without requiring internal vocabulary.

| Trigger | User job | Best public path |
|---|---|---|
| “Ho visto questa frase condivisa: è davvero stata detta?” | inspect exact wording, speaker, date and source | Statement |
| “Cosa sappiamo di questa affermazione?” | read the concise finding, rationale and evidence trail | Statement |
| “Voglio tornare al contesto originale” | open the original video/audio/text at the published locator | Statement -> Content/source |
| “Cosa ha detto questa persona nel tempo?” | inspect a chronology without a reliability score | Person |
| “Cosa è stato dichiarato su questo tema?” | inspect a topic-centred dossier of statements, traces and sources | Topic |
| “Questa posizione è cambiata?” | follow a reviewed longitudinal thread without inferring intent | Trace |
| “Ricordo solo parte del nome/frase/fonte” | search and progressively refine the public record | Home search -> Explore |
| “Come fate a decidere cosa pubblicare?” | inspect method, provenance, uncertainty and automation boundaries | Method |
| “Avete corretto un errore?” | inspect append-only corrections/re-analysis/replies | Corrections |
| “Posso usare i dati?” | find stable machine-readable interfaces and licensing | Data & API |

## 4. Primary conversion and secondary trust paths

### Primary conversion

The public site's primary conversion is **successful discovery of a useful public
record**. On Home this means starting a search or entering Explore and reaching the right
Statement, Person, Topic, Content or Trace record.

It is deliberately **not** signup, account creation, newsletter subscription, a chatbot
session, a “generate” action, or a paid conversion.

### Trust paths

Trust is earned through evidence and reversibility of the reading path. The main trust
paths are:

1. exact wording -> speaker/date/source -> original source/locator;
2. concise finding -> rationale -> evidence/source list;
3. published record -> version/correction/reply history;
4. record -> Method for policy, uncertainty and automation boundaries;
5. site -> Corrections for public error handling;
6. site -> Data & API / Project for machine-readable transparency, governance and
   open-source context.

Method and utility documents support the main task. They must not compete with search or
the canonical Statement in the first viewport.

## 5. Differentiation

The product should not market itself as another binary true/false badge, AI assistant, or
political scorecard. Its strongest combined differentiation is:

**source-linked public statements + preserved wording/context + reviewable evidence +
versioned corrections + longitudinal change over time.**

That combination matters because:

- the exact original wording remains distinct from any normalized claim;
- evidence is one interaction away rather than hidden behind an editorial conclusion;
- a Statement is a stable shareable record, not merely an article about a fact-check;
- Trace can show clarification, update, correction or contradiction candidates without
  converting chronology into an accusation of intent;
- corrections and replies append history instead of erasing it;
- public records remain usable when model providers are offline because the public path
  reads only precomputed approved projection data;
- stable URLs and structured data make the record citable by humans, search engines,
  researchers and agents.

## 6. Proof hierarchy

Marketing copy must prefer proof that is inherent to the product. No testimonials,
traffic numbers, accuracy percentages or adoption metrics may be invented to make the
site feel established.

### Strongest proof types

1. **Original source proof** — exact wording, publisher/content, date and a real locator.
2. **Attribution provenance** — enough approved provenance to support who said what.
3. **Evidence proof** — linked authoritative evidence and the observations used in the
   published verification.
4. **Reasoning proof** — concise rationale and explicit uncertainty/limitations.
5. **History proof** — corrections, replies, re-analysis and versioned material changes.
6. **Longitudinal proof** — reviewed related statements in chronological order.
7. **Method proof** — published rules that explain publication, uncertainty and
   automation boundaries.
8. **Technical openness proof** — stable structured data, API documentation and
   open-source project artifacts where actually available.

Generated mockups, model output, internal candidates, private transcripts and generic
“AI-powered” claims are not proof.

## 7. Core objections and the product response

### “State decidendo voi chi dice la verità?”

The product publishes bounded findings about statements and evidence. It does not score a
person's truthfulness, ideology, competence or political fitness, and it never recommends
a political choice.

### “E se una contraddizione fosse solo un cambio di posizione?”

Trace presents reviewed relations and chronology. A contradiction or position change is
not proof of deception or intent.

### “E se l'AI allucinasse una fonte o una frase?”

Public records require approved provenance and validated source/evidence paths. Generic
model output is not evidence, verification, or publication. Uncertainty fails closed.

### “State togliendo una frase dal contesto?”

The canonical reading path keeps original wording, source/date and the original
content/locator close to the published finding. Source context is a first-class path, not
a footnote.

### “Come correggete un errore?”

Material changes are versioned. Corrections, re-analysis and approved replies are
append-only public history rather than silent rewrites.

### “Serve un account?”

No account is required for the public v1 reading/search experience. Login,
personalization, follows, bookmarks and feeds are deliberately deferred.

### “È un sito solo di politica?”

No. The product is about public-interest statements by public figures. Politics is one
domain among others and must not become the organizing visual or taxonomy principle.

## 8. Anti-fit and non-goals

Dichiarazioni Pubbliche is not for users looking for:

- a leaderboard of “most truthful” or “most false” people;
- partisan persuasion or voting recommendations;
- outrage, gotcha headlines or courtroom-style accusations;
- a breaking-news feed optimized for velocity over provenance;
- a social network, comments, followers or personalized engagement loops;
- an AI oracle/chatbot that generates a live verdict on demand;
- private-person dossiers or irrelevant private-life profiling;
- a general-purpose web search engine;
- a dashboard of vanity metrics, trend scores or synthetic activity.

These exclusions are part of the positioning, not missing features to hide.

## 9. Voice and copy rules

The voice is:

- **documentary, not accusatory**;
- **precise, not moralizing**;
- **clear, not bureaucratic**;
- **transparent about uncertainty**;
- **source-first**;
- **neutral toward people, parties and ideological camps**;
- **plain enough for a first-time reader without erasing necessary distinctions**.

### Prefer

- exact verbs: “ha dichiarato”, “la fonte mostra”, “la verifica conclude”, “resta
  irrisolto”, “è stato corretto”;
- dates, source names and concrete evidence before abstract authority claims;
- “verifica”, “dichiarazione”, “fonte”, “contesto”, “traccia”, “correzione” in public
  prose;
- uncertainty stated as a real result when the evidence does not close the question.

### Avoid

- “scopriamo chi mente”, “la verità sulla politica”, “smascherato”, “inchiodato”,
  “bugiardo” or similar intent-laden language;
- raw internal vocabulary (`finding`, `ContentAudit`, relation IDs, pipeline stages) in
  primary reader copy;
- repeated “AI-powered”, “smart”, “intelligent” or model-brand claims;
- stronger headlines than the evidence supports;
- social-proof language without real evidence.

## 10. Home message hierarchy

Home should resolve four questions in this order:

1. **What is this?** A verifiable, source-linked record of public statements.
2. **What can I do now?** Search the record.
3. **What will I find?** Exact statements, sources, checks and traces over time.
4. **Why should I trust the process?** Follow the source/evidence path or open Method.

The first viewport should therefore contain one concise explanation, one dominant search
entry, and restrained real-record proof. It should not add a signup hero, feature grid,
testimonial strip, KPI wall, newsletter wall or generic AI illustration.

## 11. Evidence we do not yet have

The following must remain marked as unknown until measured or researched. They must not
be converted into marketing claims:

- no validated customer/user-interview language for the new v4 Home positioning;
- no public adoption, traffic, retention, citation or usage numbers approved for social
  proof;
- no approved accuracy percentage or “better than competitors” benchmark for public
  marketing;
- no completed brand-recall study for the Segno or the line “La parola lascia una
  traccia”;
- no completed v4 usability study proving the final Home/Statement/Trace composition;
- no final accessibility/performance/SEO acceptance for the v4 implementation (DP-410
  remains the gate);
- no trademark/legal clearance implied by the product naming decision.

These are evidence gaps, not permission to fill the page with invented substitutes.

## 12. Decision test for future public copy

Before a new headline, CTA or proof block is accepted, it should pass all of these:

1. Does it help a reader discover or inspect a public record?
2. Is every factual/product claim supported by current product behavior or project
   evidence?
3. Does it preserve statement-level neutrality rather than scoring a person?
4. Can the reader follow the claim back to source, evidence, method or history?
5. Does it avoid turning AI into the product promise?
6. Does it avoid adding a new user job or route that the canonical IA does not authorize?

If not, the copy does not belong in the v4 public redesign.

## Source synthesis

This context consolidates, without superseding:

- `PRODUCT.md`;
- `DESIGN.md`;
- `docs/11-product-positioning-marketing.md`;
- `docs/21-brand-naming-v0.md`;
- `docs/30-competitive-ux-research-v1.md`;
- `docs/31-implementable-ia-design-spec-v1.md`;
- `docs/35-public-product-architecture-v3.md`;
- `docs/36-public-redesign-v4.md`.
