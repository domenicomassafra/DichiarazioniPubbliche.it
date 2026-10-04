# DP-204 — First live remote-ASR receipt and fallback acceptance

Status: BLOCKED  
Milestone: M2  
Blocked by: configured Groq credential

## Outcome

Prove the existing remote-ASR adapter on a bounded real sample, record a paid/live
receipt, and validate that transcription disagreement propagates to publication holds.

## Acceptance criteria

- credential is injected outside Git;
- bounded audio/sample and spend cap;
- receipt records provider/model/request/cost metadata;
- numeric/name/date/negation disagreement remains fail-closed;
- no full-library ASR fan-out is triggered by this canary;
- MiniPC runtime proof.
