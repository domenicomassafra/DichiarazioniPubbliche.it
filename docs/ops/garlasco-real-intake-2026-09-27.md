# Garlasco real-data intake — 2026-09-27

Status: runtime-proven end-to-end corpus; two low-risk documentary findings public.

## Scope

First real-data batch for the Garlasco topic, limited to public statements by:

- Selvaggia Lucarelli;
- Roberta Bruzzone.

The batch is intentionally claim-level and does not encode a person-level truth,
reliability, credibility, or political score.

## Runtime authority

The records were inserted additively into the MiniPC PostgreSQL database `dichiarazioni_pubbliche`.
No raw transcript, media body, provider credential, or database dump was added to Git.

Current production readback after the second intake, DP-110/DP-111 rollout, deterministic
verification pass, and first publication pass:

- `person`: 2;
- Garlasco `atomic_claim`: 12 (6 Lucarelli, 6 Bruzzone);
- `evidence`: 17;
- `evidence_observation`: 13, of which 9 are `APPROVED`;
- approved claim/evidence links: 9;
- `inference_candidate`: 6;
- `claim_text_provenance`: 10, all `APPROVED`;
- check-worthy claims: 9/9 with a deterministic `verification_run` and `finding`;
- `finding`: 9 total: 2 `PUBLISH`, 7 `NEEDS_MORE_EVIDENCE`;
- public projection: 2 dossiers, 0 omitted.

The production projection currently returns:

- `dossier_count = 2`;
- `omitted_count = 0`.

The only published findings are deliberately low-risk documentary propositions:

1. Lucarelli's statement that Alberto Stasi received a 24-year sentence reduced to 16
   through the abbreviated-trial reduction. Verification is anchored to a SHA-256-pinned
   mirror of the Court of Assise of Appeal judgment.
2. Lucarelli's statement that Chiara Poggi's fixed home computer was not used after
   10 August 2007 before the homicide. Verification is anchored to the captured direct
   statement of court-appointed computer expert Daniele Occhetti and is expressly scoped
   to the computer-use timeline; it makes no inference about perpetrator or motive.

All other factual findings remain private/fail-closed.

## Reasoned inference layer added later the same day

DP-110 added a private `InferenceCandidate` layer so the project can record conclusions
that arise from several premises without pretending they are direct quotations or direct
evidence.

For the Sempio-line DNA material, two separate candidates now exist in the production
database:

1. a lineage-level inference: the reported Y signal is compatible with the Sempio
   paternal line, with qualitative support stored as `MODERATE` and the scientific
   limitations retained;
2. an individual-source hypothesis: Andrea Sempio is one possible individual source,
   but the Y result does not identify him alone. This record is explicitly
   `IDENTITY_ATTRIBUTION`, `INDETERMINATE`, and publication-blocked, with competing
   hypotheses and disconfirmers stored alongside it.

This allows common-sense/abductive reasoning to be represented explicitly while
preserving the difference between a plausible hypothesis and an identified fact.

The same contextual fact may cut in more than one direction and must be recorded that
way. Sempio's documented frequent access to the Poggi house makes him more contextually
relevant than an abstract patrilineal relative, while also making innocent prior or
secondary transfer a live alternative. DP-110 therefore requires explicit
`countervailing_factors` for high-risk inference candidates instead of allowing the
reasoner to count only evidence favorable to one conclusion.

## Claim set

### Selvaggia Lucarelli

1. The colour of fingerprint 33 did not itself demonstrate blood and was attributed to
   the ninhydrin reaction used to reveal the trace.
2. Alberto Stasi received a 24-year sentence reduced to 16 years through the reduction
   attached to the abbreviated-trial procedure.
3. The statement that the alternative lines of inquiry did not amount, in her view, to
   a serious lead is stored as `VALUE_JUDGMENT` with `check_worthy = false`.
4. The reported statement by Stasi that he had left Chiara "in front of a computer".
5. The claim that Chiara's fixed home computer had not been powered on after 10 August
   before the murder.
6. The proposed conclusion that the computer wording proves Stasi contradicted himself
   and lied. The factual inconsistency can be investigated, but the intentional-lie
   conclusion remains held by the no-intent policy.

### Roberta Bruzzone

1. The disputed nail material was described as Y-chromosome material without autosomal
   markers and as compatible on at least 13 loci with the Sempio paternal line.
2. After about 19 hours of use of Alberto Stasi's shoes, no blood traces released by the
   shoes were reported on the vehicle mats.
3. The statement that the final conviction of Alberto Stasi is, in her view, well
   founded is stored as `VALUE_JUDGMENT` with `check_worthy = false`.
4. The statement that the Y-DNA compatibility is not individually decisive and that
   secondary transfer is possible, while described as improbable.
5. The statement that the blood tests on fingerprint 33 were negative.
6. The statement that experts consulted by Bruzzone saw at most six or seven matching
   minutiae on fingerprint 33.

## Second-batch inference notes

- The computer claim does not by itself establish that Stasi's phrase was false merely
  because Chiara's fixed home computer was off: opposing 2026 computer analyses both
  place Chiara on Stasi's laptop that evening while disputing what she did or viewed.
  The resulting inference explicitly preserves alternative temporal/device readings and
  does not infer deliberate lying.
- The wording that the fingerprint-33 blood tests were simply "negative" is more
  compressed than the technical reconstruction currently stored: the Combur result is
  reported as uncertain while OBTI, the more specific human-blood test, is reported
  negative. The private inference records this as a wording overstatement rather than a
  person-level verdict.
- The minutiae count remains a live expert-method dispute in the stored evidence: the
  prosecution communication reports 15, while Bruzzone reports consulted experts at a
  maximum of six or seven. No media-side count is promoted automatically to fact.

## Verification outcomes

Every check-worthy claim now has one deterministic verification/finding record. The
current claim-level state is:

- `SUPPORTED / PUBLISH`: sentence 24 years -> 16 years; Poggi desktop last use on
  10 August;
- `INSUFFICIENT_EVIDENCE / NEEDS_MORE_EVIDENCE`: Bruzzone Y-DNA/13-loci detail;
  Bruzzone shoe/mat claim; Bruzzone transfer-possibility claim; Bruzzone fingerprint-33
  blood-test wording; Bruzzone six/seven-minutiae claim; Lucarelli fingerprint-33
  reagent/blood claim; Lucarelli's reported Stasi-computer quotation;
- no finding by design for the two `VALUE_JUDGMENT` claims and the intent/motive
  hypothesis about whether Stasi lied.

The Stasi-computer claim was also normalized more conservatively after source review:
the database now preserves `avrebbe detto` and describes the proposed lie as Lucarelli's
hypothesis rather than an established intent fact.

## Evidence handling

Evidence is approved only when its concrete role has been reviewed. Approval does not
mean `authoritative = true`: several media/expert reports are approved as traceable
context while deterministic verification still returns `NO_AUTHORITATIVE_EVIDENCE`.
Later evidence is explicitly stored as an `UPDATE` when it post-dates the statement
cutoff instead of being silently backdated into the evidence available at statement time.

In particular:

- contemporaneous material on fingerprint 33 records the ninhydrin/reagent explanation;
- a later Stasi-defence consultancy claiming sweat plus blood is retained as a later,
  contested update;
- the later court-appointed DNA work is retained as an update describing compatibility
  with the Sempio paternal line together with the reported scientific limitations;
- the 2014 walking-test report is linked as context to the shoe/mat claim and is not
  automatically converted into a contradiction verdict.

The evidence-capture audit on 2026-09-27 backfilled valid SHA-256 hashes for 10 previously
unhashed Garlasco web sources. One historical Cassazione mirror remained unreachable to
the capture job and is still explicitly unhashed; it is not used by either public finding.

## LLM provenance

The normalized claim candidates were extracted/curated in this ChatGPT session with
`gpt-5.6-sol` and stored with extraction version `chatgpt-curated-garlasco-v1`.

The model is not stored as an evidence source and produced no finding. URLs and factual
evidence relations were separately researched and recorded as evidence candidates.

## Written-source provenance closure

DP-111 removed the architecture defect that forced all source attribution through timed
transcript segments. Written sources now use deterministic `claim_text_provenance`
records containing an exact quote SHA-256, optional document hash/character position,
attribution method, and explicit review provenance. No fake `0:00` timestamp is needed.

Ten real Garlasco claims now have exact published-quote hashes and approved text
attribution. The quote bodies remain outside the database/public projection. These
approvals establish **who said the quoted proposition in the checked source**; they do
not approve its truth and do not create a finding.

The remaining non-public findings stay private where available evidence is indirect,
post-statement, methodologically disputed, or lacks the authoritative support required by
the deterministic verifier. Written attribution never bypasses the separate evidence,
observation, verification, and finding-publication gates.
