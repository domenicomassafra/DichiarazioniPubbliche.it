# DP-214/215 Wave 22 — public-source identity and 100-item feasibility

Date: 2026-10-10. Scope: operator-visible public-page **metadata** and
authoritative MiniPC **read-only** PostgreSQL aggregates. This receipt gives
no capture, body-retention, model-use, quotation, or publication permission.
The six historical URL hints remain in their original candidate-only file.
Source identities and dates below describe what the publisher's public page
showed on this date, not legal proof of authorship, authenticity, truth, or
independence of every statement within a work.

## Verified public-page leads

| Candidate and published page | Displayed date and publisher | Provisional source family and origin decision |
|---|---|---|
| [Burnout ep.16 on Apple Podcasts](https://podcasts.apple.com/it/podcast/burnout-ep-16-garlasco-ha-una-regia/id1772323196?i=1000747146238) | 2026-01-29; Vale Tutto Podcast / Selvaggia Lucarelli via Apple | `VIDEO_PODCAST`. Apple is the distribution listing; it explicitly links to [the creator's own episode page](https://selvaggialucarelli.substack.com/p/burnout-ep16-garlasco-ha-una-regia), also dated 2026-01-29. One logical episode, not two items. |
| [Quarto Grado interview clip on Mediaset Infinity](https://mediasetinfinity.mediaset.it/video/quartogrado/caso-garlasco-lintervista-a-roberta-bruzzone_F314087301028C11) | `20 mar` on video page; 2026-03-20 broadcast date backed by [Mediaset's dated programme announcement](https://mediasetinfinity.mediaset.it/news/mediasetinfinity/quartogrado/quarto-grado-anticipazioni-20-marzo_SE000000000019_t2JZcuKP7GIze8dLxA1LcvQ) | `VIDEO_PODCAST`. Own broadcaster/programme page. **Broadcast date does not establish first upload time.** Mediaset's page terms expressly bar automated scraping and generative-AI training use; rights remain `UNKNOWN` and no acquisition is proposed. |
| [FarWest clip on RaiPlay](https://www.raiplay.it/video/2026/04/Cappa-Garlasco-tra-nuovi-rilievi-e-audio-sospetti---FarWest---21042026-13577568-35e2-4786-b6f6-b0b2e3044ab8.html) | Episode dated 2026-04-21; FarWest / RAI | `VIDEO_PODCAST`. Broadcaster's own episode listing, 5 minutes; no separate statement-attribution proof. |
| [ANSA Garlasco article](https://www.ansa.it/lombardia/notizie/2026/05/07/procura-di-pavia-chiude-le-indagini-su-garlasco-chiara-uccisa-da-sempio_5838528d-4418-49e3-8047-613fa7b0a63e.html) | 2026-05-07 18:48; Redazione ANSA | `SECONDARY_REPORTING`. An original newsroom report **about** judicial proceedings, not an authentic court document. Article explicitly marks reproduction restricted. |
| [Il Ticino report and reproduced statement](https://ilticino.it/2026/09/28/dlelitto-di-garlasco-notificato-dalla-procura-di-pavia-lavviso-di-chiusura-delle-indagini/) | 2026-09-28; Alessandro Repossi, Il Ticino | `DUPLICATE_DERIVATION` *proposal*: article explicitly says it reproduces the Procura communiqué. A corresponding first-party [official 28 September PDF](https://procura-pavia.giustizia.it/resources/cms/documents/Comunicato_Stampa_28.09.2026.pdf) is listed by the [Procura's Comunicati Stampa page](https://procura-pavia.giustizia.it/it/comunicati_stampa.page). The first page visibly matches the document's nature/opening; exact full-text equivalence and derivation approval remain to review. |
| [Chi l'ha visto? newsroom page](https://www.chilhavisto.rai.it/dl/clv/News/ContentItem-bbe55c13-870b-42f8-9eb3-3300927e12a0.html) | `Pavia, 8/5/2026` dateline; RAI / Chi l'ha visto? | `SECONDARY_REPORTING`. News piece containing a statement attributed to the **lawyers for the Poggi family**. No original first-party lawyers' publication was located/independently bound. Do not classify this as a Procura statement or as approved original quotation. |
| [La Nazione interview with Roberta Bruzzone](https://www.lanazione.it/cronaca/bruzzone-qjyn2h3v) | Page dated 2026-05-07; Gianluca Barni, La Nazione | `DIRECT_INTERVIEW_ARTICLE`: identifiable interviewing newspaper and byline. The body starts with a May 8 Montecatini dateline; this is distinct from the site's May 7 date. Publication and capture rights remain separate. |
| [Procura di Pavia communiqué PDF](https://procura-pavia.giustizia.it/resources/cms/documents/Comunicato_Stampa_28.09.2026.pdf) | 2026-09-28; Procura della Repubblica presso il Tribunale di Pavia, directly via [.giustizia.it official listing](https://procura-pavia.giustizia.it/it/comunicati_stampa.page) | `OFFICIAL_PROCEDURAL`: **real first-party procedural source** (3-page PDF). Original locator confirmed by following the official listing and visually reading its first page. Neither the PDF's statements nor a person implicated by an investigation should be treated as adjudicated guilt. |

The 8 URLs are independent *candidate locators*, but that is not a finding
that they are 8 independent evidentiary sources or 8 new unique Content rows
compared with the historical 18. The Il Ticino republication and original
Procura communiqué must retain two source records if captured later, with a
reviewable derivation relation to avoid independence inflation. Apple's
listing and its creator webpage represent **one logical episode**, likewise
not two pilot items. The source-of-statement identity in the Chi l'ha visto?
piece remains an explicit follow-up.

## Runnable, zero-acquisition preview

The pinned observations, owners, dates, evidence-page URLs and rights flags
are in `config/garlasco-source-feasibility-wave22.v1.json`; the original six
unreviewed URLs are bound by exact ID, URL and provisional source family to
`config/garlasco-public-discovery-leads.v1.json`.

Local preview, no network or DB connection:

```bash
python3 tools/preview_garlasco_public_sources_wave22.py
```

MiniPC actual *read-only* snapshot piped to the local offline preview, with
no output artifact or source-body retention:

```bash
set -o pipefail
ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes minipc \
  'psql -X -qAt -d dichiarazioni_pubbliche -v ON_ERROR_STOP=1' \
  < tools/read_garlasco_source_feasibility_wave22.sql \
  | python3 tools/preview_garlasco_public_sources_wave22.py --snapshot-json -
```

The SQL begins `BEGIN READ ONLY`, performs a single collection-scoped
aggregate SELECT and ends in `ROLLBACK`. There are no public/body requests,
new Discovery Hits, license guesses or database mutations. It counts raw
Discovery Hit rows, **not** pre-certified accepted provenance.

Actual MiniPC proof 2026-10-10: `research:garlasco` `PAUSED`, 18 included
historical Content, **18/18 `UNKNOWN`** rights, 0 capture-authorized,
30 historical Atomic Claims, 0 Discovery Hit rows, 0 Capture, 0 Passage,
0 Statement Candidate, 0 Claim Candidate. A separate `BEGIN READ ONLY`/
`ROLLBACK` exact-URL check against **all** `content_item.canonical_url` rows
returned **0/8 exact URL collisions** for the eight pinned candidate URLs.
This increases confidence in their usefulness as new links, but it cannot
prove semantic uniqueness, permission or successful capture. The offline plan
reports:

| Planning measure | Actual |
|---|---:|
| Existing leads whose public page metadata was checked | 6 |
| New public page candidates checked (La Nazione + official PDF) | 2 |
| Candidate URL count, NOT accepted Content | 8 |
| Families represented as provisional candidate labels | 5 / 5 |
| `DIRECT_INTERVIEW_ARTICLE` / `VIDEO_PODCAST` | 1 / 3 |
| `OFFICIAL_PROCEDURAL` / `SECONDARY_REPORTING` / `DUPLICATE_DERIVATION` | 1 / 2 / 1 |
| Unresolved first-party origin locators among the eight | 1 |
| Included historical Content / target | 18 / 100 |
| Still missing actually included Content | **82** |
| Hypothetical upper bound if 8 *new, semantically distinct, reviewable* URLs all qualify | 26 / 100 |
| Still missing in that optimistic scenario, **before dedup** | **74** |
| Capture rights, claim promotion, publication proven | **0** |

The estimate 26/100 is explicitly an **upper bound**: it may fall after
cross-checking the new URLs against existing records, equivalence and rights.
No automatic source acceptance is inferred from an `origin_verified` flag:
that flag means a public issuer/creator locator was observed, **not** that
durable DB provenance or exact full-text derivation review exists.

## Concrete next dependency decisions

1. Obtain case-specific source-use decisions, privacy relevance and permitted
   modes for the two broadcaster pages, one podcast, the interview and the
   article/mirror documents; all remain `UNKNOWN` regardless of public access.
   Mediaset's explicit automated-collection restrictions need particular
   legal/owner attention before any capture. No paid/model operations follow
   from this metadata check.
2. Record actual DP-209 versioned manifest/query/run/hit/attempt provenance
   only after independent operator authorization. Bind Apple to its creator
   page as one logical episode; propose Il Ticino → official PDF as a
   **reviewable** derived-from edge, not approved independent evidence;
   locate the original lawyer statement for the Rai news item.
3. Expand by **at least 74 further new, unique, approved** Contents even in
   the maximally favorable 8-lead scenario, while preserving all 18 historical
   rights holds. Verify each family, duplicates, exact time/owner/source
   identity and practical access before a real 100-item Capture/Passage run.

**Acceptance status unchanged:** DP-214.1/.2/.4–.8 and DP-215.9 remain
open. This wave materially identifies a first-party procedural document and
provides a reproducible, fail-closed metadata source inventory. It does not
persist Discovery provenance, grant source rights or close the 100-item pilot.
