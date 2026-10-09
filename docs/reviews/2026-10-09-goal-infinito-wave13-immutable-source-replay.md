# GOAL INFINITO — Wave 13: immutable source, challenger replay, archive chronology

Date: 2026-10-09. Published baseline: `b292665`, Wave 12 GitHub
CI `37977393187` **SUCCESS**. Sole publisher PRIME;
three distinct file-owner lanes, existing orphan legacy Content
UI draft and the untracked original handoff preserved.

## DP-214→215 immutable bytes and Passage selector binding

Reproduction: shift a persisted `TEXT_POSITION` selector start/end
by one while leaving the associated Passage text, text hash,
Capture ID and span length unchanged. Previously pure
Candidate extraction returned COMPLETED and, on a later replay,
`CANDIDATE_REPLAYED` without verifying the parent source
string. The source-only root-free fixture adapter remains
non-authoritative; the real CLI now explicitly requires an
approved *existing* private storage root before creating any
DB/provider client.

The operator-bound `preflight_candidate_batch` fetches an
exact joined persisted Capture/Passage snapshot and checks
Content/Capture/Passage IDs, text hash, source hash/ref,
parser method/version, captured decoding policy, private
Passage text and selector. It opens the body store in true
read-only mode (no mkdir/chmod), bounds the actual file read
against the Capture response size policy, verifies original
body SHA and calls `verify_passage_roundtrip` on the canonical
parser output. The authorization guard is reused before
provider call, replay and commit. Missing legacy charset/
parser/bytes, a shifted/forged selector, stale source hash
or missing/invalid body all block without conferring model
or publication permission. Two PRIME-owned regression tests
verify the read-only SQL shape/decoder policy and safe body
store opening; worker fixtures exercise actual local bytes.

## DP-229 material countercase identity

The `countercase-v1` hash could stay fixed when two evidence
IDs kept the same aggregate relation/rationale/lineage sets
but exchanged their individual assignments. The v2 hash now
includes canonical sorted per-evidence bindings. Reordering
without material change keeps the ID; changing a binding
changes the ID and invalidates old review relevance.
No external challenger provider or waiver authorization.

## DP-419 archive transition chronology

After Wave 12's receipt completeness check, the private
inspector now additionally refuses archive SUCCEEDED/FAILED
when an aware completion timestamp predates its requested
timestamp (including equivalent offsets). It never emits
private receipt or body fields. This remains private
metadata-only evidence.

## Validation and release boundary

Combined private Candidate, CLI, Capture, extraction,
challenger, Studio Capture and local API focused suite:
**138/138 PASS**. Python compileall and Git diff checks
PASS. The frozen full integrated suite subsequently passed
**2093/2093 Python tests** (478.096 s), the 100-table restore
drill and deterministic benchmark **5/5**. Ticket repository
contract PASS, compileall/diff checks PASS, and launch preflight
remained **NO-GO/41**, receipt SHA-256
`890103b989d86e2ad2a112c943aa57d1f0e52e24a50ddd14d64ff42cc3bf7399`.
The run took longer than earlier suites because disposable
PostgreSQL fixture setup/cleanup was slow; it ultimately returned
exit code 0, not a timeout or interrupted test. The matching
git commit and CI still require separate verification.
All acceptance criteria needing genuine Garlasco sources,
individual rights, live model, human review, real MiniPC
canary or signed release authority remain open. Backlog
unchanged: **86 DONE, 24 IN PROGRESS, 6 BLOCKED,
9 FUTURE = 39 open; NO-GO/41**.
