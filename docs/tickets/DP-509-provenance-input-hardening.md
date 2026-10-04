# DP-509 — Harden claim/ASR/verification provenance inputs

Status: DONE  
Milestone: M5  

## Problem

Post-governance review found three fail-open/secret-retention edges:

- claim extraction accepted coercible non-integer segment indices and truthy non-boolean
  fields;
- Groq 4xx exceptions could retain an upstream response body containing sensitive URLs or
  tokens;
- verification enqueue/worker execution could accept a payload `statement_date` that
  disagreed with the canonical claim date.

## Outcome

Make those boundaries strict and fail closed without changing provider/model policy,
database schema or public projection semantics.

## Implemented

Runtime commit:

`778134b Harden provenance checks and UX contract`

- `claim_runtime.py` requires actual integer segment indices and boolean fields;
- `remote_asr.py` no longer embeds Groq 4xx response bodies in exceptions;
- `review_admin.py` rejects statement-date override at enqueue time;
- `worker_daemon.py` blocks tampered statement-date payloads at execution time;
- five focused regression tests added.

## Acceptance receipt — 2026-09-23

Mac source authority:

- compileall: PASS;
- unit/regression suite: 190/190 PASS;
- deterministic benchmark: 5/5 PASS;
- `git diff --check`: PASS.

MiniPC runtime authority:

- deployment mirror changed-file SHA-256 values match Mac for `claim_runtime.py`,
  `remote_asr.py`, `review_admin.py`, and `worker_daemon.py`;
- compileall: PASS;
- unit/regression suite on mirror: 190/190 PASS;
- deterministic benchmark on mirror: 5/5 PASS;
- `dichiarazioni-pubbliche-source-poll.service`, `dichiarazioni-pubbliche-worker.service`, and
  `dichiarazioni-pubbliche-health.service` latest observed runs: `Result=success`, exit 0;
- queue remained unchanged:
  - `CLAIM_EXTRACT | BLOCKED | 11`;
  - `TRANSCRIPT_ACQUIRE_ASR | BLOCKED | 9`;
  - `TRANSCRIPT_ACQUIRE_CAPTION | COMPLETED | 11`;
  - `TRANSCRIPT_CANONICALIZE | COMPLETED | 11`;
  - `TRANSCRIPT_RESOLVE_PLATFORM | COMPLETED | 20`.

No migration was required.
