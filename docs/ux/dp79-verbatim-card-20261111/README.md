# DP-436 — rendered card as the fifth verbatim surface (11 November 2026)

Gate: `web/scripts/check-dp436-verbatim-card-parity.mjs` (CI step "DP436 rendered
card as fifth verbatim surface", job `web`).

The merged gate `check-dp436-cross-consumer-verbatim-parity.mjs` compares four
machine surfaces (search index, API v3, JSON-LD, N-Triples). The card a reader
actually sees, `VerbatimStatementRecord.astro`, was only ever compared with the
API payload it renders from, never with the index, linked data and N-Triples
bytes of the same governed release. A card that escapes, decodes, trims or
normalizes an approved span could therefore diverge from every other surface
with no test failing. The new gate closes that hole:

- renders the real Astro component in an isolated scratch site for ONE governed
  release (no route, no publication, no demo projection);
- extracts the quotation from the produced HTML, decodes one level of character
  references and requires the exact approved bytes;
- covers `&`, `<`, `>`, `"`, `'`, a tab, a line break and edge spaces inside an
  approved span, and refuses raw metacharacters in the markup;
- requires the card's `data-dataset-sha256` to be the governed release
  fingerprint;
- withdrawal: the withdrawn Statement disappears from all four machine
  surfaces, its pinned detail reader answers `404 RESOURCE_NOT_FOUND`, and the
  stale card no longer builds under the new release pins (`FINGERPRINT`),
  while the surviving cards keep agreeing with every surface.

Non-vacuity was proven by mutation: changing the component's text node to
`{statement.original_text.trim()}` makes the gate fail with
`card changed the approved bytes` (`actual` = tampered bytes, `expected` =
approved bytes). The mutation was reverted and is not part of this change.

## Local receipt (`~/Code/.worktrees/DichiarazioniPubbliche.it-79`, MateBook)

```
node --experimental-strip-types scripts/check-dp436-verbatim-card-parity.mjs
DP-436 rendered-card parity PASS (card = 5th surface, 3 statements, exact bytes
including metacharacters/whitespace, withdrawal refuses the stale card,
fingerprint 98949a1f33bb)
```

Fixture: the independent DP-439 governed release (`tests/test_dp439_person_topic_v3.py`,
`published()`), fingerprint
`98949a1f33bba00101d42c71bc7bdfd6cb8be4799359aa6bb689c05c07fa64fa`; special-bytes
release `995631c293401c0c43418287ff87d1bdf791d3c67762f1625deeadd3b963c156`.
Approved span used for the special case:
`A & B < C > D "E" 'F'\tseconda riga\n  fine  `.

## Screenshots (isolated local build, not a product route)

`card-full-1280.png` — card for the governed release Statement, exact quote,
speaker, date, source link, locator and language.
`card-special-bytes-1280.png` — same component for the approved span above:
metacharacters are displayed literally (escaping never changes the words).

Observation for the design owner, not a defect of this gate: the DOM text is
byte-exact (`textContent` keeps tab, line break and edge spaces) while the
rendered text inside `white-space: normal` collapses them
(`innerText` = `A & B < C > D "E" 'F' seconda riga fine`). Two spans that differ
only in whitespace render identically, although their `quote_sha256`, locator
and bytes differ. Preserving that visually is a typography decision owned by the
design work (#84/#349), so the card CSS is deliberately unchanged here.

## Limits

Synthetic fixture only: it grants no right, approves no source and publishes
nothing. The authentic-case proof (AC-436.2) still needs one genuine `INCLUDED`
Statement with current revocable rights (#468/#413) and a public v3 release with
correction/withdrawal (#98/#544); the installed MiniPC consumer stays
`public-v2/DRAFT` with zero dossiers and `/api/v3/statements` 404.
