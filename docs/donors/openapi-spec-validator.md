# OpenAPI 3.1 validator (developer/CI only, issue #175)

- Upstream: https://github.com/python-openapi/openapi-spec-validator
- Version: PyPI `openapi-spec-validator==0.9.0`, released 2026-05-20.
- Exact upstream tag commit: `2121137e4832871202b96a276b225b90f3aece50` (`0.9.0`).
- License: Apache-2.0 ([LICENSE](https://github.com/python-openapi/openapi-spec-validator/blob/0.9.0/LICENSE)).
- Upstream [NOTICE](https://github.com/python-openapi/openapi-spec-validator/blob/0.9.0/NOTICE): `openapi-spec-validator`, copyright 2017–2021 Artur Maciag, licensed under Apache-2.0. It remains in the installed upstream distribution; no source is vendored here.
- Direct package dependencies at that commit: `jsonschema>=4.26,<5`, `openapi-schema-validator>=0.9,<0.10`, `jsonschema-path>=0.5,<0.6`, `lazy-object-proxy>=1.7.1,<2`, `pydantic>=2,<3`, `pydantic-settings>=2,<3`. Their transitive dependencies are resolved by pip only in the `dev` environment; the complete local graph can be inspected with `python -m pip list` or `python -m pip inspect`.
- Known upstream risk: [issue #400](https://github.com/python-openapi/openapi-spec-validator/issues/400), open as of 2026-10-19, reports a `RecursionError` for a recursive `oneOf`/`allOf` graph in 0.7.2. **The minimal upstream reproducer still triggers `RecursionError` under 0.9.0**, confirmed locally with Python 3.14.7 and a bounded recursion limit of 600. The current generated DP schemas do not contain that cycle and validate successfully with 0.9.0 for both empty and realistic projections; upstream recursive schemas remain a known limitation, not a resolved regression.

Only `pyproject.toml`'s `dev` extra and the `openapi-contract` CI job install the validator. The generated API and ordinary backend runtime do not import it. `tests.test_openapi_spec_validator` tests the upstream validator and its installed OpenAPI 3.1 JSON Schema checker; it skips cleanly when the optional tooling is absent, while the dedicated CI job explicitly installs it. The sole generator correction for this adoption passes inline JSON Schemas as schemas instead of wrongly wrapping them in `$ref`.
