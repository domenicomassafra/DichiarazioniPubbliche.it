# DP-420 — Garlasco Studio operator acceptance

Scope: issue #342 / historical #74. This is a **private, read-only acceptance**
of task completion in the installed Studio. It cannot authorize sources,
extraction, model dispatch, public projection, or deployment. The source rights
and publication gates of `PRODUCT.md` and `AGENTS.md` continue to apply.

## Frozen task matrix

`tests/fixtures/studio-garlasco-usability-v1.json` lists **20** concrete tasks:
13 query/navigation exercises tied one-to-one to the pinned
`tests/fixtures/corpus-search-benchmark-v1.json` gold and 7 operator flows for
Collection → Source → Capture → Passage → Candidate, near duplicates,
cluster/veto, and coverage gaps. The 13 historical lexical results are genuine
indexed baseline data, **not** proof of Capture, Passage, candidate, quote
accuracy, or usability. Prompts deliberately distinguish reported allegations
and predictions from established facts.

Each task needs an independently observed real Studio session. The six required
modalities are wide desktop, keyboard-only navigation, 200% zoom, narrow
viewport, reduced motion, and a screen reader. The visual pass assesses task
clarity and critical runtime defects; visual redesign is deferred under the
owner's 25 October decision (#84, #324, #349). Each private UI observation
records its elapsed **time to the original source** in milliseconds, the number
of UI actions, navigation errors and evidence SHA-256. Six actions is the
maximum accepted for source retrieval. Unsupported paths are HOLD, and a
critical observed defect is FAIL. No action may read raw data through a DB
shell in place of completing the operator task.

## Reproduce on the authorized runtime

On Mac Studio, under the resource guard:

```sh
python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_studio_operator_search tests.test_studio_usability_acceptance -q
```

On the MiniPC, after installation and from its real consumer mirror, query
PostgreSQL read-only:

```sh
PGDATABASE=dichiarazioni_pubbliche PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.garlasco_pilot_inventory --verify-baseline-search
PGDATABASE=dichiarazioni_pubbliche PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.studio_usability_acceptance
```

The second command emits a **metadata-only** JSON report. Exit 0 means all
20 task observations, six modality observations and the frozen search gold are
recorded and satisfy their gates; exit 1 is an actual failure; exit 2 is HOLD
or unavailable data. `search_cases_passed` and `search_p95_ms` are measured by
the existing real PostgreSQL benchmark. `operator_time_to_source_p95_ms`,
`operator_timed_tasks` and `operator_navigation_errors` describe recorded
operator observations. An empty observation set always leaves all 20 tasks
and all six accessibility modalities in HOLD, even when 13/13 retrieval passes.
The readiness counts include every `INCLUDED` Content in `research:garlasco`,
including newly captured sources that lack a historical baseline Atomic Claim;
the baseline inventory remains a distinct historical metric.

## Record operator measurements privately

Use Studio's actual authenticated loopback API/UI against the installed
consumer. The operator token provisioning instruction remains in "Prove
personali" #300; temporary agent-only read-only proof does not establish the
owner's persistent Studio access. Make a private JSON file owned by the
operator, mode **0600**, outside the repository and any public served path.
Pass its path with `--observations`. Evidence hashes refer to separate
restricted screenshots/browser traces/review logs, preserved only in the
operator's authorized private receipt directory. Example **schema only**:

```json
{
  "version": "studio-garlasco-usability-v1",
  "tasks": {
    "source-capture": {
      "status": "PASS",
      "time_to_source_ms": 1800,
      "actions": 3,
      "navigation_errors": 0,
      "source_id": "source:example",
      "capture_id": "capture:example",
      "rights_record_id": "private-rights:example",
      "evidence_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    }
  },
  "modes": {
    "keyboard-only": {
      "status": "PASS",
      "evidence_ref": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    }
  }
}
```

These placeholder values are *not evidence* and must never be submitted as a
real observation. For tasks requiring Passage, add `passage_id`; for every
positive task retain the actual current, source-specific rights record
alongside its source/capture binding. Confirm rights applicability, timestamps,
privacy, attribution, version hash and revocation status against PostgreSQL.
An independent Standards/Spec reviewer must check the underlying screenshot,
navigation, DB bindings and current rights; the receipt itself proves only
schema completeness and reported timing. Failures remain explicit, and a
`PASS` observation lacking metrics, rights ID, or evidence digest is HOLD.

## Current genuine sample — 25 October 2026

Readback from MiniPC PostgreSQL on 25 October: Garlasco historical baseline
**18 Content, 30 Claims**, all 30 baseline claims linked and searchable,
**0 Capture / 0 Passage / 0 Statement Candidate / 0 Claim Candidate**.
**13/13** pinned query cases passed, Recall 1.0, p95 **75.531 ms** for this
single benchmark run, measured by `corpus_search_benchmark --json`. The
Collection is incomplete, including missing source rights and coverage.
The public read model health responded HTTP 200 with `DRAFT` and 0 dossiers;
this is not evidence of private Studio usability. All source-linked and
Candidate operator tasks remain unaccepted pending actual permitted data and
an observed browser session. Source choice/legal review is the agents' technical
work under the owner's 25 October decision; do not ask the owner to approve
ordinary sources. Personal token provisioning is already tracked in #300.
