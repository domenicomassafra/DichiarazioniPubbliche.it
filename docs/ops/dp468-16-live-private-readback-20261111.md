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

## Selected literal source quote verification (11 November 2026)

The existing `dp331_senato_private_speech_readback.py` now accepts one
`--quote-pin ORDINAL:START:END:SHA256` for every `--ordinal` (up to three per
run). It requires the **current `PARSE_TEXT` private right** before and after
the persisted Capture read, independently selects the exact source turn,
and hashes the selected UTF-8 substring against the recorded pin. A changed
range, source, digest or revoked permission fails; the output includes only
range/hash and `VERIFIED_PRIVATE_SOURCE_ONLY`, never the quote body.

The updated script (SHA-256
`cc7796f1161d0610a5956cd01999c50eb5e64cb4b12a5f63e43fd78ef146d4fa`)
was copied to a **disposable MiniPC candidate path**, separately hashed and
executed using the existing user-systemd `runtime.env`, PostgreSQL Capture,
and immutable body store. Six bounded invocations covered the original batch:
`3`; `6,7,8`; `13,31,33`; `42,50,57`; `82,83,85`; `86,87,88`.

**16/16 selected literal hashes matched** their exact private source spans
and the [pinned manifest](dp468-senato-public-v3-source.md#new-first-batch-text-selection-10-november-2026-private-candidate-status).
Each invocation returned source SHA-256
`1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`,
`rights_status=CLEARED` for private uses through 23 November 2026,
`status=PRIVATE_HOLD`, `attribution_approved=false`, and
`publication_authorized=false`. The six transient runs exited successfully;
no model POST, public grant, PostgreSQL write or web release was made.

Example of the existing read-only path with the new pin check:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 \
  tools/dp331_senato_private_speech_readback.py \
  --ordinal 3 \
  --quote-pin 3:143:268:10e853dc569025edd00423b653bd68f85cc11de9e0a1d09fb49ac17e3948176d
```

This establishes the selected **wording/source match** only. Independent
speaker attribution, revocable public quotation clearance, the six GDPR
processing decisions, authenticated #413 model execution and the live #98
v3 correction/withdrawal readback remain separate gates.
