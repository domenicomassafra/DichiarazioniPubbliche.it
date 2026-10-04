# Operations runbook

The health digest is private operator telemetry. It contains aggregate queue/source/provider/provenance counts, blocker categories, SLO evaluations, and deduplicated actions. It must not contain transcript text, evidence bodies, prompts, credentials, or private reply text.

Use the blocker taxonomy in `poc/dichiarazioni_pubbliche/ops/taxonomy.py` rather than improvising recovery actions. Repeated instances of the same cause collapse into one action row. `SLO_BREACH`, exhausted dead-letter work, or other explicitly paging conditions are escalation signals; expected credential/provider blocks remain visible without being converted into fabricated success.

Operator rules:

- fix the named cause, not the symptom;
- never switch model/provider merely to turn a blocked lane green;
- never lower validation/publication gates;
- never hand-edit canonical transcript/evidence/finding state to clear a queue;
- never treat `UNKNOWN` as healthy;
- never publish from an incomplete restore or stale/tampered projection;
- record runtime-affecting acceptance on the MiniPC.

The private digest is extended by `poc/dichiarazioni_pubbliche/health_digest.py`; SLOs live in `ops/slo.py`; taxonomy/actions live in `ops/taxonomy.py`. DP-505 remains in progress until this behavior is exercised against the MiniPC runtime and an incident owner/contact path is accepted.
