# Public record review-event collision fence — 2026-10-10

Scope: private SQL writer integrity for a Finding, a right of reply, and
a correction. Changes are tested using synthetic records on disposable
PostgreSQL; no public deployment, rights grant, legal approval, operator
identity attestation or production write is made.

## Confirmed defect (RED before repair)

The three canonical writer methods
\`publish_finding_with_review\`,
\`publish_right_of_reply_with_review\` and
\`publish_correction_with_review\` updated a record's public-facing
state **before** attempting to append the associated \`review_event\`.
The event insert used \`ON CONFLICT (id) DO NOTHING\`. If its ID was
already assigned to an unrelated record, the append silently failed
while the public status change remained and the method returned true.
For a correction, the same defect could also mark the previous
Finding as CORRECTED without a matching correction review.

Two targeted real PostgreSQL RED fixtures proved the reply/correction
cases. Two additional RED fixtures used the **complete canonical**
database schema and a synthetic eligible claim, verified source
attribution, approved evidence and observation, verification run and
Finding to demonstrate the Finding failure and forged-actor replay.

## Repair

Each method now locks and checks its existing eligibility conditions,
inserts the exact APPROVED \`review_event\` first, and changes the
Finding/public visibility (and correction's previous Finding status)
**only** if the insert created an event. A replay with an existing
event is idempotent solely when entity ID, APPROVED action, actor,
reason and the already-public current state match exactly.

Unrelated event-ID collisions, altered actor/reason and stale
approval events cannot move a private/held record to public state.
The existing privacy/rights, reanalysis, source binding, verification
and high-risk DP-310 attestation/projection gates remain separate;
these legacy private SQL writers do not themselves authorize a release.

## Evidence and runtime limitations

- \`tests/test_public_review_event_collision_postgres.py\`: four
  disposable PostgreSQL cases (collision and good replay for reply/correction).
- \`tests/test_public_finding_review_collision_postgres.py\`: two cases
  on full canonical PostgreSQL schema (collision and exact replay for Finding).
- Baseline MiniPC **read-only** aggregate: 2 published Findings, 0 lacking
  an APPROVED Finding review event; zero public replies, zero public
  corrections, zero missing approval-event counts for either.
- No evidence of this specific unreceipted-publication discrepancy was
  found in the current readback. This is not a blanket compliance review
  or a claim that all publication preconditions are complete.

DP-302/DP-303 public intake is still disabled; DP-306/DP-307 legal and
rights decisions, DP-229 challenger runtime authority and DP-705 launch
remain outstanding. The source patch has not been deployed to the MiniPC.
