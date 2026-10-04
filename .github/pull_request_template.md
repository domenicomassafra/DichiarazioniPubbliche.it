## Ticket / spec

<!-- DP-###, public issue, or spec path -->

## What changed

<!-- Keep this behavioral and concise. -->

## Invariants checked

- [ ] No publication/review/provenance boundary was weakened.
- [ ] No raw/private transcript or evidence body was added to public output.
- [ ] No person-level political/reliability score or biometric identity feature was added.
- [ ] Provider failure still fails closed.

## Validation

- [ ] Focused tests
- [ ] `python3 -m compileall -q poc tests`
- [ ] `PYTHONPATH=poc python3 -m unittest discover -s tests -v`
- [ ] deterministic benchmark when relevant
- [ ] `git diff --check`
- [ ] MiniPC runtime proof when the ticket requires it

## Data / schema / public contract

<!-- None, or describe migration/public-schema compatibility impact. -->

## Documentation / ADR

<!-- Files updated, or why none are needed. -->
