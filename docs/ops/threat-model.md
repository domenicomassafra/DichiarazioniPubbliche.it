# Dichiarazioni Pubbliche — Operational threat model

Status: implementation evidence; launch acceptance still requires MiniPC proof and the DP-702 review packet.

The executable threat register is `poc/dichiarazioni_pubbliche/ops/threats.py`. It covers every pipeline stage from source ingest through public API and records STRIDE category, severity, mitigations, enforcement mechanism, product invariant, and evidence pointer. `tests/test_ops_threat_matrix.py` is the regression matrix: machine-enforced rows must resolve to real code/config/unit/test artifacts and critical threats must name the invariant they defend.

The model deliberately treats provider downgrade, fabricated receipts, publication bypass, future-evidence misuse, person scoring, biometric identity, SSRF/source spoofing, projection tampering, secret leakage, destructive retention, unbounded fan-out, and restore fabrication as failures. A failing provider is a blocked state, never permission to switch quality tiers or manufacture output.

Public/admin trust boundaries remain conservative. Public output is the bounded projection only. Review/admin operations remain local/operator-only until DP-507 is explicitly activated and reviewed. Public intake remains disabled until DP-508 is explicitly activated and approved.

## Validation

Run:

```bash
PYTHONPATH=poc python3 -m unittest tests.test_ops_threat_matrix -v
PYTHONPATH=poc python3 -m unittest discover -s tests
git diff --check
```

Mac test success is development evidence. DP-501 is not launch-closed until the candidate is exercised/read back on the MiniPC runtime authority and incorporated into DP-702.
