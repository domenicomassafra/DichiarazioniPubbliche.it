# DP-468 — Real private readback of the 16 selected Senato interventions

On 11 November 2026, the existing MiniPC
`tools/dp331_senato_private_speech_readback.py` ran through a user systemd
transient unit with the installed runtime `EnvironmentFile`. It read the
**actual persisted PostgreSQL Capture and private rights registry** without
modifying either store or making an upstream model request.

Six bounded runs used explicit ordinal groups `3,6,7`; `8,13,31`;
`33,42,50`; `57,82,83`; `85,86,87`; `88`. Each process exited successfully.
The returned `utterer_candidate` for each of the 16 interventions matched the
corresponding official `TLCPerson` URI ID recorded in the
[source selection](dp468-senato-public-v3-source.md#new-first-batch-text-selection-10-november-2026-private-candidate-status).
Every group independently returned source SHA-256
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`.

All six returned `rights_status=CLEARED` for **private** uses, with
`rights_expires_at=2026-11-23T21:53:43.934666+00:00`. Every observation
returned `decision=HOLD`, `attribution_approved=false`, and
`publication_authorized=false`. Every document-level response was
`PRIVATE_HOLD` with `publication_authorized=false`.

The official `TLCPerson` URI supplies one source signal, not a second
independently authenticated speaker identity signal. This readback proves
current private source/role linkage only. Before any public release, the
system still needs a passage-bound public quotation grant, six approved GDPR
families, a witnessed upstream editorial review under owner decision 49,
and a functioning public v3 correction/withdrawal/CDN readback.

**Disposition: PRIVATE_HOLD / NO-GO.** No public grant, review authority,
release pin, model completion or public API route was enabled by these reads.
