# DP-214 replay identity gate — 2026-10-10

This is a read-only, metadata-only acceptance aid for a **future**
rights-authorized Garlasco corpus replay. It is not a publication
permission, source license, independent MiniPC attestation, or ticket
completion receipt.

The existing structural tracer could call two replays stable when
both had exactly 100 logical Content items and 30 baseline Claims,
even if individual Content identifiers had all changed. An explicit
RED fixture reproduced that replacement at equal counts.

The new \`dichiarazioni_pubbliche.garlasco_replay_identity\` tool
compares **exact Content, Claim and public Finding ID sets**, plus
immutable persisted Capture (ID, Content ID and body SHA-256) pairs.
Changes to existing Captures, disappearing identifiers and undeclared
new Capture identifiers fail closed. The two provided JSON snapshots
are strictly validated, bounded and parsed without duplicate keys.
The result includes independent before/after content hashes, not raw
captured bodies.

To audit two *separately collected, authoritative* read-only snapshots:

\`\`\`bash
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.garlasco_replay_identity \
  --before /private/verified-before.json \
  --after /private/verified-after.json
\`\`\`

The optional \`--new-capture-id\` supplies an exact **comparison
expectation**, never permission to fetch or create a Capture; actual
rights/capture authorization stays with the governing store policy.

\`tests/test_garlasco_replay_identity.py\` proves RED-to-GREEN for
equal-count Content or public Finding substitution, old Capture
removal/mutation, undeclared new Capture, unexpected Content
reference, duplicate identifiers, duplicate JSON keys, oversized
files and stable reordered snapshots. Eight focused tests pass.

**Outstanding acceptance:** The authoritative MiniPC remains
18 included Contents, all with rights UNKNOWN, and lacks a
rights-cleared 100-item corpus and actual Discovery/Capture replay.
Neither the test fixtures nor two caller-supplied JSON files
can establish DP-214 AC-214.6 or close DP-214/DP-215.
