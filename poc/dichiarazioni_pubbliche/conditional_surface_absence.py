"""Narrow technical proof for DP-507/508 *conditional* launch scope.

This asserts only the present code topology. It neither grants admin/submitter
permissions nor licenses an account rollout or legal launch. Any future public
mutation implementation must explicitly withdraw this NOT_APPLICABLE decision.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from dichiarazioni_pubbliche.public_api import PublicApiRequestHandler
from dichiarazioni_pubbliche.studio_local_api import _ALLOWED_PATHS, StudioLoopbackServer


_SAFE_PUBLIC_MEMBER_PATHS = frozenset({
    "/account/auth/google", "/account/oauth/callback", "/account/api/session",
    "/account/api/logout", "/account/api/delete",
})
_MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE", "OPTIONS")
_PRIVATE_STUDIO_READ_PATHS = frozenset({
    "/v1/corpus/search", "/v1/capture/compare", "/v1/capture/passages",
    "/v1/media/segment", "/v1/candidate/matches",
    "/v1/candidate/review-readiness", "/v1/candidate/handoff-receipt",
    "/v1/collections/list",
    "/v1/collections/members", "/v1/collections/member",
    "/v1/collections/claim-provenance", "/v1/collections/captures",
    "/v1/collections/passage-candidates", "/v1/discovery/list",
    "/v1/discovery/inspect", "/v1/discovery/triage-history",
    "/v1/discovery/inbox", "/v1/discovery/bulk-preview",
})


def verify_surface_absence(root: Path) -> None:
    """Fail on a newly surfaced admin/editorial-intake path or method seam."""
    root = Path(root)
    public_handler = PublicApiRequestHandler
    if any(getattr(public_handler, "do_" + method, None) is not public_handler._reject
           for method in _MUTATING_METHODS):
        raise ValueError("CONDITIONAL_PUBLIC_MUTATION_HANDLER_CHANGED")
    if getattr(public_handler, "account_service", "unexpected") is not None:
        raise ValueError("CONDITIONAL_PUBLIC_MEMBER_OPT_IN_NOT_DEFAULT")

    # Exactly the five member-only paths are exempted from the generic
    # read-only rejection; they do not confer review/admin/intake authority.
    for path in (*_SAFE_PUBLIC_MEMBER_PATHS, "/admin/", "/v1/admin/review",
                 "/api/v1/intake", "/api/v1/replies", "/contribuisci/",
                 "/moderazione/", "/publish/", "/v1/candidate/approve"):
        routed = public_handler._is_account_path(SimpleNamespace(path=path))
        if routed != (path in _SAFE_PUBLIC_MEMBER_PATHS):
            raise ValueError("CONDITIONAL_PUBLIC_ACCOUNT_PATH_SCOPE_CHANGED")

    if _ALLOWED_PATHS != _PRIVATE_STUDIO_READ_PATHS:
        raise ValueError("CONDITIONAL_PRIVATE_STUDIO_PATH_SCOPE_CHANGED")
    # The local operator service must bind exclusively to loopback. An
    # ephemeral listener is closed immediately; no private data is queried.
    with StudioLoopbackServer(0, SimpleNamespace(), "a" * 64) as server:
        if server.server_address[0] != "127.0.0.1":
            raise ValueError("CONDITIONAL_STUDIO_SERVER_TOPOLOGY_CHANGED")
    for relative in (
        "web/src/pages/contribuisci.astro",
        "web/src/pages/contribuisci/index.astro",
        "web/src/pages/admin.astro",
        "web/src/pages/admin/index.astro",
    ):
        if (root / relative).exists():
            raise ValueError("CONDITIONAL_PUBLIC_MUTATION_PAGE_EXISTS")


__all__ = ["verify_surface_absence"]
