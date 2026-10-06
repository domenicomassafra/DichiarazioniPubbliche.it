# DP-306 — Italy/EU legal research closure register

Status: **OPEN — BLOCKING for public launch**
Register version: `legal-closure-v1`
Last evidence collection: 2026-09-26
Owner of this register: product owner (technical register only)

## What this document is, and is not

This is a **research and decision-control register**, per `GOVERNANCE.md` and the
DP-306 ticket. It records:

- each launch-sensitive question;
- the official primary sources that were **actually retrieved and read** for it;
- the status of each question;
- the safe default that applies while it is open.

It is **not** legal advice, a legal opinion, or an assurance of compliance. No row
in this register is `DECIDED`. A row may only become `DECIDED` when the named
qualified reviewer and the product owner accept a dated disposition (P-306-02).
An agent or maintainer can organise evidence but **cannot** supply the legal
conclusion (P-306-02, B-306-04).

Per P-306-01 (no implicit closure): the absence of an answer is never permission.
Every question below is currently `OPEN` or `BLOCKING`.

## Status vocabulary

| Status | Meaning |
|---|---|
| `OPEN` | Question is unanswered; safe default applies. |
| `EVIDENCE_COLLECTED` | Official primary sources retrieved and read; no decision yet. |
| `DECIDED` | Qualified reviewer **and** owner accepted a dated decision. **None today.** |
| `DEFERRED` | Deliberately postponed with a recorded rationale. |
| `BLOCKED` | A prerequisite (qualified reviewer, deployment assumption) is missing. |

## Evidence retrieval method and its limits

Retrieval was performed on **2026-09-26** from this workspace using direct HTTPS
requests to official publishers. For each row marked *retrieved*, the exact URL and
the document identifier from the Official Journal header were confirmed by reading
the returned document.

**Honest limits of this session, stated up front:**

1. Only English-language consolidated texts on EUR-Lex were retrieved. The
   authentic Italian consolidated version of each instrument was **not** read.
2. Italian national portals (`normattiva.it`, `gazzettaufficiale.it`,
   `garanteprivacy.it`, `agcom.it`) were reachable at HTTP level, but their
   article-level text is rendered client-side and was **not** obtained in this
   session. No Italian article number is asserted anywhere below.
3. No Garante or AGCOM measure was read. They are listed as `UNVERIFIED` targets,
   not as evidence.
4. Locating the applicable instrument is **not** deciding whether, when, or how it
   applies to this product. Applicability depends on the deployment model, which is
   an owner decision (Q-306-16). Nothing below is a legal conclusion.

## Verified primary sources (retrieved and read 2026-09-26)

| Ref | Instrument | URL retrieved | OJ identifier observed | Provisions read |
|---|---|---|---|---|
| S1 | Regulation (EU) 2016/679 (GDPR) | `https://www.eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679` | `L_2016119EN.01000101.xml`, OJ L 119, 4.5.2016 | Art. 2(2)(c); Art. 5(1)(f); Art. 6(1); Art. 9(1); Art. 9(2)(j); Art. 10; Art. 15(1); Art. 17(1); Art. 21(1); Art. 85(1)–(2); Art. 89(1); Recitals 26 and 47 |
| S2 | Directive (EU) 2019/790 (CDSM) | `https://www.eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32019L0790` | `L_2019130EN.01009201.xml`, OJ L 130, 17.5.2019 | Art. 3; Art. 4; Recitals 18 and 44 |
| S3 | Directive 2001/29/EC (InfoSoc) | `https://www.eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A32001L0029` | Directive 2001/29/EC | Art. 5(3)(a); Art. 5(3)(c) |
| S4 | Regulation (EU) 2022/2065 (DSA) | `https://www.eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A32022R2065` | `L_2022277EN.01000101.xml`, OJ L 277, 27.10.2022 | Art. 3 definitions; Art. 16; Art. 17 |
| S5 | Regulation (EU) 2024/1689 (AI Act) | `https://www.eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A32024L1689` | `L_202401689EN.000101.fmx.xml`, OJ L series 2024/1689, 12.7.2024 | Art. 4; Art. 50(1); Art. 50(2); Art. 50(4) |

### Verified text of the load-bearing provisions

These are short verbatim fragments actually read from the documents above. They are
included so a qualified reviewer does not have to re-find them, and **not** as an
interpretation.

**S1 — GDPR Art. 85(1)** (the central provision for a journalistic public record):
> "Member States shall by law reconcile the right to the protection of personal data
> pursuant to this Regulation with the right to freedom of expression and
> information, including processing for journalistic purposes and the purposes of
> academic, artistic or literary expression."

**S1 — GDPR Art. 85(2)** (opening):
> "For processing carried out for journalistic purposes or the purpose of academic
> artistic or literary expression, Member States shall provide for exemptions or
> derogations from Chapter II (principles), Chapter III (rights of the data
> subject), Chapter IV (controller and processor), Chapter V (transfer of personal
> data to third countries or international organisations), Chapter VI (independent
> supervisory authorities) …"

**S1 — GDPR Art. 9(1)**:
> "Processing of personal data revealing racial or ethnic origin, political
> opinions, religious or philosophical beliefs, or trade union membership, and the
> processing of genetic data, biometric data for the purpose of uniquely identifying
> a natural person, data concerning health or data concerning a natural person's sex
> life or sexual orientation shall be prohibited."

**S1 — GDPR Art. 9(2)(j)**:
> "processing is necessary for archiving purposes in the public interest, scientific
> or historical research purposes or statistical purposes in accordance with
> Article 89(1) based on Union or Member State law which shall be proportionate to
> the aim pursued, respect the essence of the right to data protection and provide
> for suitable and specific measures to safeguard the fundamental rights and the
> interests of the data subject"

**S1 — GDPR Art. 89(1)**:
> "Processing for archiving purposes in the public interest, scientific or historical
> research purposes or statistical purposes, shall be subject to appropriate
> safeguards, in accordance with this Regulation, for the rights and freedoms of the
> data subject."

**S1 — GDPR Art. 2(2)(c)** (read for accuracy; it is *not* the journalism exclusion):
> "by a natural person in the course of a purely personal or household activity"

> **Correction to a common assumption.** GDPR Art. 2(2) does **not** exempt
> journalism. The journalisitic-purpose route is Art. 85 (Member-State
> reconciliation) and Art. 9(2)(j)/Art. 89(1) (archiving in the public interest,
> conditioned on Union or Member State law). Art. 2(2)(c) is the purely
> personal/household activity exclusion. This distinction is the single most
> important correction in this register.

**S1 — GDPR Art. 6(1)** (opening):
> "Processing shall be lawful only if and to the extent that at least one of the
> following applies:"

**S1 — GDPR Art. 5(1)(f)**:
> "processed in a manner that ensures appropriate security of the personal data,
> including protection against unauthorised or unlawful processing and against
> accidental loss, destruction or damage, using appropriate technical or
> organisational measures ('integrity and confidentiality')."

**S1 — GDPR Art. 17(1)** (opening):
> "The data subject shall have the right to obtain from the controller the erasure of
> personal data concerning him or her without undue delay …"

**S1 — GDPR Art. 21(1)**:
> "The data subject shall have the right to object, on grounds relating to his or her
> particular situation, at any time to processing of personal data concerning him or
> her which is based on point (e) or (f) of Article 6(1) …"

**S3 — InfoSoc Art. 5(3)(a)** (the general quotation/illustration exception):
> "use for the sole purpose of illustration for teaching or scientific research, as
> long as the source, including the author's name, is indicated, unless this turns
> out to be impossible and to the extent justified by the non-commercial purpose to
> be achieved"

**S3 — InfoSoc Art. 5(3)(c)** (press exception; the article is a *may* provision):
> "Member States may provide for exceptions or limitations to the rights provided for
> in Articles 2 and 3 in the following cases: … (c) reproduction by the press,
> communication to the public or making available of published articles on current
> economic, political or religious topics or of broadcast works or other
> subject-matter …"

**S2 — CDSM Art. 3 heading / Art. 4 heading** (read to avoid a wrong assumption):
> "Article 3 Text and data mining for the purposes of scientific research"
> "Article 4 Exception or limitation for text and data mining"

> **Correction to a second assumption.** CDSM Art. 3/4 are the **text-and-data-mining**
> provisions. They are *not* a public quotation exception. The quotation/press
> exception is in Directive 2001/29/EC Art. 5(3). Any DP-305 design that leans on
> CDSM for quotation is leaning on the wrong instrument.

**S4 — DSA Art. 17** (statement of reasons; applies to *hosting* providers):
> "Providers of hosting services shall provide a clear and specific statement of
> reasons to any affected recipients of the service …"

**S5 — AI Act Art. 50(2)** (provider-side synthetic content marking):
> "Providers of AI systems, including general-purpose AI systems, generating
> synthetic audio, image, video or text content, shall ensure that the outputs of the
> AI system are marked in a machine-readable format and detectable as artificially
> generated or manipulated."

**S5 — AI Act Art. 50(4)** (deployer-side deep fake disclosure):
> "Deployers of an AI system that generates or manipulates image, audio or video
> content constituting a deep fake, shall disclose that the content has been
> artificially generated or manipulated."

**S5 — AI Act Art. 4** (AI literacy):
> "Providers and deployers of AI systems shall take measures to ensure, to their best
> extent, a sufficient level of AI literacy of their staff and other persons dealing
> with the operation and use of AI systems on their behalf …"

### Applicability is NOT decided here

The presence of these instruments in a register is not a finding that they apply.
Whether the DSA applies depends on whether the service is a "platform" / hosting
provider; whether the AI Act Art. 50(2) marking duty reaches *this* project depends
on whether it is a **provider** of a system generating synthetic content (it consumes
provider output, which is a different role). **Both are BLOCKING open questions
below, and both are recorded as unresolved.**

## Closure table

`E` = evidence retrieved and read (see S1–S5). `UNVERIFIED` = not retrieved, not
asserted. Launch impact: `BLOCKER` (no public launch), `SURFACE_BLOCKER` (only the
named surface is held).

| Q-306 | Topic | Evidence | Status | Owner / authority | Affected surface | Safe default while open | Launch impact |
|---|---|---|---|---|---|---|---|
| Q-306-01 (DP-301) | Editorial/publication role and wording for a claim-level `FACTUALLY_FALSE` assessment; when extra notice is required | S1 Art. 85(1)–(2) (text verified); **Italian implementing law UNVERIFIED** | `OPEN` | Qualified Italy/EU counsel + product owner | Findings, JSON-LD, API, UI, notices | Neutral claim-level wording; no intent language (enforced in code) | `BLOCKER` |
| Q-306-02 (DP-301) | Whether any intentionality/deception assessment could ever exist, and at what threshold | — (product invariant answers the engineering question, not the legal one) | `OPEN` | Qualified counsel + owner | Verifier, schema, all public copy | No intentionality assessment; intent terms blocked in code | `BLOCKER` |
| Q-306-03 (DP-302) | Notice, lawful basis, consent/identity, retention, withdrawal for reply intake | S1 Art. 6(1), 15(1), 17(1), 21(1) (text verified); **Italian national provisions UNVERIFIED** | `OPEN` | Privacy counsel + owner | Intake, receipts, private store | Intake disabled in code (`INTAKE_ENABLED = False`) | `BLOCKER` |
| Q-306-04 (DP-302) | Whether replies create platform/UGC/intermediary obligations | S4 Art. 3, 16, 17 (text verified); **applicability UNDECIDED** | `BLOCKED` | Platform/editorial counsel | Intake, moderation, notices | Do not describe or operate as a hosting service | `BLOCKER` |
| Q-306-05 (DP-302) | Which abuse signals, cookies/device data, logs, retention are acceptable | S1 Art. 5(1)(f) (text verified); **profile UNVERIFIED** | `OPEN` | Privacy/security counsel + owner | Rate limits, logs, anti-abuse | Minimum data; no IP/device fingerprint collected in code; intake disabled | `BLOCKER` |
| Q-306-06 (DP-303) | Correction, retraction, notice, response, appeal duties per Finding type | S3 Art. 5(3)(c) (press exception text verified); **no determination** | `OPEN` | Editorial/qualified counsel + owner | Correction, takedown, appeal, notices | Private requests, append-only, no automated takedown | `BLOCKER` |
| Q-306-07 (DP-303) | Evidence, authority, independence, disclosure for appeal/takedown | — | `OPEN` | Owner + qualified counsel | Review queue, projection, audit | No deadline/outcome promise; separation recorded or exception logged | `BLOCKER` |
| Q-306-08 (DP-304) | Roles, lawful bases, journalistic/public-interest conditions, notices, data-subject rights per data class | S1 Art. 6(1), 9(1), 9(2)(j), 85, 89(1), Recitals 26/47 (text verified); **Italian national law UNVERIFIED** | `OPEN` | Privacy counsel + owner | Ingestion, Person, projection, API | Minimize, keep private; deny-by-default in code; no public launch | `BLOCKER` |
| Q-306-09 (DP-304) | Special handling for sensitive data, allegations, criminal matters, minors, victims, exact locations | S1 Art. 9(1), Art. 10 (text verified) | `OPEN` | Privacy/editorial counsel + owner | Claims, evidence, intake, public copy | Hold/quarantine in code; **no trait inference** | `BLOCKER` |
| Q-306-10 (DP-304) | Retention, deletion, restriction, legal hold, incident-notification rules | S1 Art. 17(1), 21(1) (text verified); **periods UNVERIFIED** | `OPEN` | Privacy/security counsel + owner | Storage, backups, rights requests, ops | `RETENTION_PERIODS_APPROVED = False`; no automatic deletion; only EPHEMERAL purge-eligible | `BLOCKER` |
| Q-306-11 (DP-305) | Quotation/excerpt rights, licences, attribution, source-specific permissions | S3 Art. 5(3)(a) and 5(3)(c) (text verified); S2 Art. 3/4 confirmed to be TDM not quotation | `OPEN` | IP/media counsel + owner | Transcript, excerpts, evidence, open data | `EXCERPT_PROFILE_APPROVED = False`; **no public excerpt ships** | `BLOCKER` |
| Q-306-12 (DP-305) | Platform/API terms, access controls, scraping restrictions per source | — | `OPEN` | IP/platform counsel + maintainer | Discovery, acquisition, source registry | Do not bypass or enable an unresolved source | `BLOCKER` |
| Q-306-13 (DP-305) | Disclosure/representation required for machine-generated transcripts and derived public data | S5 Art. 4, 50(1), 50(2), 50(4) (text verified); **role of this project UNDECIDED** | `OPEN` | AI/IP counsel + owner | Method fields, API, JSON-LD, notices | Bounded provenance/limitation fields only; no accuracy claim | `BLOCKER` |
| Q-306-14 (cross-cutting) | AI Act, DSA, ePrivacy/cookie, transparency, platform obligations for the chosen deployment | S4, S5 (text verified); **applicability analysis not done** | `BLOCKED` | Qualified technology/media counsel | Public site, intake, AI metadata, hosting | Do not claim compliance; block affected launch surface | `BLOCKER` |
| Q-306-15 (cross-cutting) | Terms, privacy notice, contact, complaint channel, security-incident process, possible registration/insurance | — | `OPEN` | Owner + qualified counsel | Website, intake, operations, launch | No public launch without an owned contact/runbook | `BLOCKER` |
| Q-306-16 (cross-cutting) | What material product/data/deployment change invalidates a prior decision | — | `OPEN` | Product owner + counsel | All M3/M4/M5 surfaces | Treat stale decisions as open and block the affected surface | `BLOCKER` |

**Summary: 16 rows — 0 `DECIDED`, 0 `CLOSED`, 2 `BLOCKED`, 14 `OPEN`, all 16 `BLOCKER`
launch impact.** Nothing in this register authorises public launch.

## Source-question crosswalk

DP-306 consolidates related qualified questions, but it must not make any source
question disappear. This is the one-to-one source-question crosswalk required by
AC-306.1: every `Q-301-*` through `Q-305-*` question appears exactly once below and
maps to one controlling `Q-306-*` row. Several source questions may share the same
controlling row when they require the same qualified decision.

| Source question | Controlling DP-306 row |
|---|---|
| Q-301-01 | Q-306-01 |
| Q-301-02 | Q-306-02 |
| Q-301-03 | Q-306-06 |
| Q-301-04 | Q-306-14 |
| Q-302-01 | Q-306-03 |
| Q-302-02 | Q-306-04 |
| Q-302-03 | Q-306-03 |
| Q-302-04 | Q-306-05 |
| Q-302-05 | Q-306-03 |
| Q-302-06 | Q-306-05 |
| Q-303-01 | Q-306-06 |
| Q-303-02 | Q-306-07 |
| Q-303-03 | Q-306-07 |
| Q-303-04 | Q-306-10 |
| Q-303-05 | Q-306-06 |
| Q-303-06 | Q-306-06 |
| Q-304-01 | Q-306-08 |
| Q-304-02 | Q-306-09 |
| Q-304-03 | Q-306-10 |
| Q-304-04 | Q-306-08 |
| Q-304-05 | Q-306-09 |
| Q-304-06 | Q-306-15 |
| Q-304-07 | Q-306-08 |
| Q-305-01 | Q-306-11 |
| Q-305-02 | Q-306-12 |
| Q-305-03 | Q-306-11 |
| Q-305-04 | Q-306-11 |
| Q-305-05 | Q-306-13 |
| Q-305-06 | Q-306-10 |
| Q-305-07 | Q-306-12 |

## Decision-control metadata

The closure table above records the evidence, status, authority, affected surface,
safe default, and launch impact. This companion table is keyed one-to-one by the same
`Q-306-*` ID and records the remaining closure-schema fields. It is part of the same
register, not a second checklist.

`UNSCHEDULED` means no calendar date has been invented before a qualified reviewer is
assigned. The affected surface remains blocked in the meantime. Once a reviewer is
assigned, the row must receive a dated review and next-review date before it can become
`DECIDED`.

| Q-306 | Jurisdiction / deployment context | Decision / condition today | Reviewer / review date | Linked ticket / policy | Re-review trigger | Next review |
|---|---|---|---|---|---|---|
| Q-306-01 | Italy/EU; public claim-level Findings, UI, API and structured metadata | No qualified decision; neutral claim-level wording only | UNASSIGNED — no qualified review date | DP-301; `intentionality-policy-v1` | Public wording, deployment role, jurisdiction or finding vocabulary review | UNSCHEDULED — external reviewer not assigned |
| Q-306-02 | Italy/EU; hypothetical intentionality capability, disabled in v1 | No qualified decision; capability remains prohibited | UNASSIGNED — no qualified review date | DP-301; `intentionality-policy-v1` | Proposal review for intent/deception semantics or a new assessment field | UNSCHEDULED — external reviewer not assigned |
| Q-306-03 | Italy/EU; disabled public right-of-reply intake and private receipt store | No qualified decision; public intake stays disabled | UNASSIGNED — no qualified review date | DP-302; `reply-intake-policy-v1` | Intake enablement review or identity, notice, retention or withdrawal change | UNSCHEDULED — external reviewer not assigned |
| Q-306-04 | Italy/EU; disabled reply/UGC intake; service role/applicability unresolved | BLOCKED pending deployment-role analysis and qualified review | UNASSIGNED — no qualified review date | DP-302; `reply-intake-policy-v1` | Hosting/UGC/service-role or moderation design review | UNSCHEDULED — external reviewer not assigned |
| Q-306-05 | Italy/EU; disabled intake anti-abuse, logs and rate/quota profile | No qualified privacy/security decision; minimum-data fallback applies | UNASSIGNED — no qualified review date | DP-302; `reply-intake-policy-v1` | Review any new abuse signal, cookie/device identifier, log field, challenge or retention profile | UNSCHEDULED — external reviewer not assigned |
| Q-306-06 | Italy/EU; correction, retraction, notice and appeal behavior for public Findings | No qualified decision; requests stay private and append-only | UNASSIGNED — no qualified review date | DP-303; `challenge-workflow-v1` | Workflow, public notice, response deadline or finding-vocabulary review | UNSCHEDULED — external reviewer not assigned |
| Q-306-07 | Italy/EU; private challenge review, public holds and appeal authority | No qualified decision; explicit review/separation remains required | UNASSIGNED — no qualified review date | DP-303; `challenge-workflow-v1` | Reviewer-role, independence, takedown authority or disclosure review | UNSCHEDULED — external reviewer not assigned |
| Q-306-08 | Italy/EU; public-interest/person processing across ingestion, projection and API | No qualified privacy decision; minimize and keep non-approved data private | UNASSIGNED — no qualified review date | DP-304; `privacy-minimization-v1` | Data-class, purpose, role, lawful-basis assumption, notice or rights-workflow review | UNSCHEDULED — external reviewer not assigned |
| Q-306-09 | Italy/EU; sensitive/high-risk personal data in claims, evidence, intake and public copy | No qualified decision; hold/quarantine with no trait inference | UNASSIGNED — no qualified review date | DP-304; `privacy-minimization-v1` | Sensitive-data, allegation/criminal/minor/victim/location handling review | UNSCHEDULED — external reviewer not assigned |
| Q-306-10 | Italy/EU; private retention, deletion/restriction, legal holds and backups | No qualified retention decision; no unapproved automatic purge | UNASSIGNED — no qualified review date | DP-304/DP-305; `privacy-minimization-v1`; DP-503 | Retention, rights-request, hold, backup or deletion-mechanism review | UNSCHEDULED — external reviewer not assigned |
| Q-306-11 | Italy/EU; public excerpts/transcripts/audio/video; profile disabled absent clearance | No qualified rights decision; no new public excerpt ships | UNASSIGNED — no qualified review date | DP-305; `excerpt-rights-v1` | Source-family, excerpt profile, licence, attribution or complaint-handling review | UNSCHEDULED — external reviewer not assigned |
| Q-306-12 | Platform/contract-specific plus Italy/EU; source acquisition and API/scraping controls | No qualified platform/terms decision; unresolved sources stay disabled | UNASSIGNED — no qualified review date | DP-305; DP-603 | Platform/API terms, access method, authentication, scraping or source-registry review | UNSCHEDULED — external reviewer not assigned |
| Q-306-13 | Italy/EU; machine-generated transcripts and derived public method metadata | No qualified disclosure decision; provenance/limitations only, no accuracy claim | UNASSIGNED — no qualified review date | DP-305; `excerpt-rights-v1` | ASR/provider role, transcript disclosure, synthetic-content handling or method-field review | UNSCHEDULED — external reviewer not assigned |
| Q-306-14 | Italy/EU; chosen public hosting/intake/AI deployment roles | BLOCKED pending deployment assumptions and applicability analysis | UNASSIGNED — no qualified review date | DP-301/DP-302; DP-702 | Hosting, intermediary role, public-intake, model-use or jurisdiction review | UNSCHEDULED — external reviewer not assigned |
| Q-306-15 | Italy/EU; public site/intake/operations documents, contacts and incident process | No qualified decision; no launch without owned contacts/runbooks | UNASSIGNED — no qualified review date | DP-304; DP-501/DP-702 | Terms/privacy/contact/complaint/security-process or deployment-owner review | UNSCHEDULED — external reviewer not assigned |
| Q-306-16 | All affected jurisdictions; every M3/M4/M5 product/data/deployment surface | No closure decision; material change reopens dependent rows | UNASSIGNED — no qualified review date | DP-306/DP-307; all linked M3/M4/M5 policies | Material source, data, product, model, public-copy, hosting or jurisdiction review | UNSCHEDULED — external reviewer not assigned |

No row above records legal advice or a legal conclusion. The qualified disposition,
assumptions, conditions, review date, accepted policy version, and next-review date are
external DP-307 inputs. Until they exist, the matching closure-table row remains
`OPEN`/`BLOCKED` and its safe default continues to apply.

A future `DECIDED` row must replace `UNASSIGNED`/`UNSCHEDULED` with the accepted
reviewer identity/role, review date, accepted policy version, conditions/assumptions,
and next-review date. Merely changing the status string is invalid.

## Explicitly NOT verified

Per the no-fabrication rule, the following are recorded as `UNVERIFIED` and carry no
article number, no quotation, and no conclusion:

| Target | URL contacted | Outcome | Why UNVERIFIED |
|---|---|---|---|
| Italian Codice della Privacy (D.Lgs. 196/2003) | `https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2003-06-30;196` | HTTP 200, landing page only | Article text is rendered client-side; the requested articles were not obtained |
| Italian Codice della Privacy (Gazzetta Ufficiale) | `https://www.gazzettaufficiale.it/eli/id/2003/07/31/003G0060/sg` | HTTP 200, shell page only | Same; no article text obtained |
| Garante per la protezione dei dati personali | `https://garanteprivacy.it/home` | HTTP 200, homepage | No specific measure or provision was read |
| AGCOM | `https://www.agcom.it/` | HTTP 200, homepage | No specific measure was read |
| Italian implementing law of GDPR Art. 85 | — | Not retrieved | This is the provision a qualified reviewer most needs; it must be read in the authentic Italian text |
| Garante guidance on journalism/public-interest archiving | — | Not retrieved | No EDPB/Garante document was read |
| EDPB guidance | — | Not retrieved | No EDPB document was read |

These gaps are **not** closed by this register. They are the first work item for
DP-307.

## Handoff to DP-307

Per E-306-06, the counsel-ready packet is: this register; the verified source texts
S1–S5; the 16 open/blocked questions; the safe default per row; the affected
surfaces; and the requested decisions. The single most important requested decision
is **the Italian implementation of GDPR Art. 85** (S1), because it determines whether
the neutral claim-level assessment model the code enforces is sufficient, and under
what conditions.

No privileged advice, personal data, or confidential content is present in this
repository document (B-306-06).
