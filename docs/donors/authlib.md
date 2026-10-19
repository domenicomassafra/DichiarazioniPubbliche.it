# Authlib donor provenance — optional public-account OIDC (issue #177)

- Upstream: https://github.com/lepture/authlib
- PyPI release: `Authlib==1.9.1`, released 2026-10-14.
- Upstream annotated tag: `v1.9.1` (tag object `a048d12e3d3356b24db8412f5d3508eb3706460a`, target commit `46b94870d915ee77430da8fa2a358378d90b3a45`).
- License: BSD-3-Clause ([upstream LICENSE](https://github.com/lepture/authlib/blob/v1.9.1/LICENSE)); preserve upstream copyright and license notices in the installed dependency distribution. No Authlib code is vendored into this Apache-2.0 repository.
- Scope: `pyproject.toml` optional `[account]` extra only, alongside the bounded cryptography dependency; the default contributor/runtime profile remains stdlib-only.
- API in use: `authlib.jose.JsonWebToken(["RS256"])` for signed Google ID-token verification. This module is marked deprecated in Authlib 1.9.1 in favor of `joserfc`; keeping the release pinned below 2.0 avoids silently changing the API, and an independent migration needs a separate security review.

The product still enforces its narrower issuer, audience, azp, nonce, timestamps, RSA key strength, JWKS key uniqueness and rotation, approved Google HTTPS destinations, PKCE/CSRF, cookie and session boundaries. Account enablement is **not** part of this integration; reader account membership grants no editorial or publication authority.
