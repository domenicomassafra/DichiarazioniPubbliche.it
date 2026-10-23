"""#170 private canary: one authorized JS page through the isolated renderer.

The canary performs exactly the selective fallback the ticket asks for: a plain
HTTPS fetch first, then one Chromium rendition only when the static body shows no
JavaScript effect. It refuses everything that is not explicitly authorized:

* a current ``APPROVED`` rights decision naming this exact host with
  ``FETCH``, ``STORE_BODY`` and ``PARSE_TEXT`` and without ``PUBLISH``;
* redirects, oversized bodies and any host outside the decision;
* a rendition that adds nothing (``NO_JS_DELTA``), because then no fallback is
  justified by evidence.

The receipt keeps hashes, byte counts, versions and the sandbox identity only: no
page text is copied, stored or published.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.browser_renderer import (
    PLAYWRIGHT_VERSION, BrowserRenderBlocked, PlaywrightBrowserRenderer,
)
from dichiarazioni_pubbliche.source_watcher import (
    MAX_DISCOVERY_RESPONSE_BYTES, fetch_bytes,
)

SCHEMA = "browser-render-canary-v1"
REQUIRED_SCOPES = ("FETCH", "STORE_BODY", "PARSE_TEXT")


class CanaryRefused(ValueError):
    """Fail-closed canary refusal with a stable code."""


def _guard(decision: Any, url: str, *, now: datetime) -> None:
    if not isinstance(decision, dict) or decision.get("status") != "APPROVED":
        raise CanaryRefused("CANARY_RIGHTS_DECISION_MISSING")
    scopes = decision.get("scopes")
    if (not isinstance(scopes, list)
            or any(scope not in scopes for scope in REQUIRED_SCOPES)
            or "PUBLISH" in scopes or "REDISTRIBUTE" in scopes):
        raise CanaryRefused("CANARY_RIGHTS_SCOPE_UNSUPPORTED")
    for key in ("id", "reviewer_ref", "approved_at"):
        value = decision.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise CanaryRefused("CANARY_RIGHTS_DECISION_INVALID")
    constraints = decision.get("constraints")
    expires_at = constraints.get("expires_at") if isinstance(constraints, dict) else None
    if not isinstance(expires_at, str):
        raise CanaryRefused("CANARY_RIGHTS_DECISION_INVALID")
    try:
        approved = datetime.fromisoformat(decision["approved_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if approved.tzinfo is None or expires.tzinfo is None or now.tzinfo is None:
            raise ValueError("timezone required")
    except ValueError:
        raise CanaryRefused("CANARY_RIGHTS_DECISION_INVALID") from None
    if not approved <= now < expires:
        raise CanaryRefused("CANARY_RIGHTS_NOT_CURRENT")
    hosts = decision.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise CanaryRefused("CANARY_RIGHTS_HOST_MISSING")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise CanaryRefused("CANARY_URL_INSECURE")
    host = urlsplit(url).hostname or ""
    if host not in {str(item).lower() for item in hosts}:
        raise CanaryRefused("CANARY_RIGHTS_HOST_UNAUTHORIZED")


def render_canary(
    *, url: str, decision: Any, chromium_binary: str,
    fetcher: Callable[..., Any] = fetch_bytes,
    renderer_factory: Callable[..., Any] = PlaywrightBrowserRenderer,
    max_bytes: int = 1_048_576,
    clock: Callable = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    """Return a receipt for one authorized selective JS rendition."""
    _guard(decision, url, now=clock())
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_DISCOVERY_RESPONSE_BYTES:
        raise CanaryRefused("CANARY_BUDGET_INVALID")
    episode_host = urlsplit(url).hostname
    static = fetcher(url, allow_redirects=False, max_response_bytes=max_bytes)
    if static.final_url != url:
        raise CanaryRefused("CANARY_REDIRECT_UNAUTHORIZED")
    _guard(decision, static.final_url, now=clock())
    renderer = renderer_factory(
        enabled=True, chromium_binary=chromium_binary,
        allowed_subresource_hosts=(episode_host,), fetcher=fetcher,
    )
    rendered = renderer.render(
        url, max_response_bytes=max_bytes,
        authorization_guard=lambda: _guard(decision, url, now=clock()),
    )
    fragment_only = (
        rendered.final_url != url and "#" not in url
        and rendered.final_url.split("#", 1)[0] == url and "#" in rendered.final_url
    )
    if rendered.final_url != url and not fragment_only:
        raise CanaryRefused("CANARY_FINAL_URL_CHANGED")
    finished_at = clock()
    _guard(decision, url, now=finished_at)
    static_bytes = len(static.body)
    rendered_bytes = len(rendered.body)
    wrapper = Path(renderer.sandbox_executable)
    receipt = {
        "schema": SCHEMA,
        "decision": "RENDERED" if rendered.body != static.body else "NO_JS_DELTA",
        "generated_at": finished_at.isoformat().replace("+00:00", "Z"),
        "target": {"url": url, "host": episode_host},
        "static": {
            "status_code": static.status_code,
            "media_type": static.media_type,
            "bytes": static_bytes,
            "sha256": hashlib.sha256(static.body).hexdigest(),
        },
        "rendered": {
            "bytes": rendered_bytes,
            "sha256": hashlib.sha256(rendered.body).hexdigest(),
            "added_bytes": rendered_bytes - static_bytes,
            "fragment_only_url_change": fragment_only,
            **(renderer.last_receipt or {}),
        },
        "sandbox": {
            "wrapper_sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
            "chromium_binary": Path(chromium_binary).name,
            "playwright_version": PLAYWRIGHT_VERSION,
        },
        "rights": {
            "decision_id": decision["id"],
            "reviewer_ref": decision["reviewer_ref"],
            "approved_at": decision["approved_at"],
            "hosts": sorted(decision["hosts"]),
            "scopes": list(decision["scopes"]),
            "published": False,
        },
        "publication": "HOLD",
        "side_effects": {"downloads": 0, "uploads": 0, "profile_reuse": 0},
    }
    if receipt["decision"] == "NO_JS_DELTA":
        raise CanaryRefused("CANARY_NO_JS_DELTA")
    return receipt


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bounded private #170 canary")
    parser.add_argument("--url", required=True)
    parser.add_argument("--rights", required=True)
    parser.add_argument("--chromium", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    with open(args.rights, encoding="utf-8") as handle:
        decision = json.load(handle)
    try:
        receipt = render_canary(
            url=args.url, decision=decision, chromium_binary=args.chromium,
        )
    except (CanaryRefused, BrowserRenderBlocked) as exc:
        print(json.dumps({"schema": SCHEMA, "decision": "HOLD",
                          "code": str(exc)}))
        return 3
    payload = json.dumps(receipt, indent=1, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
