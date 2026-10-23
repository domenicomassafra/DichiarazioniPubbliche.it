"""Private, opt-in JavaScript rendition via Playwright Python 1.64.0.

All browser networking is disabled by a mandatory Linux bubblewrap network
namespace. Requests are fulfilled by the existing pinned-DNS HTTPS client in
the parent process; browser code cannot open sockets, even for subresources.
No caller may use this adapter without capture_pipeline's current rights gate.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import shutil
import socket
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.capture_authorization import PrivateCaptureAuthorizationBlocked
from dichiarazioni_pubbliche.source_watcher import (
    FetchedBytes,
    MAX_DISCOVERY_RESPONSE_BYTES,
    fetch_bytes,
    validate_discovery_url,
)

PLAYWRIGHT_VERSION = "1.64.0"
RENDERER_VERSION = "playwright-python-1.64.0-netns-v1"
_MAX_REQUESTS = 32
_ALLOWED_RESOURCES = frozenset({"document", "script", "stylesheet", "xhr", "fetch"})


class BrowserRenderBlocked(RuntimeError):
    """Stable error code; never include a URL, page content or credentials."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PlaywrightBrowserRenderer:
    """One disposable headless Chromium context per explicitly authorized rendition.

    The package extra alone does not enable this backend. The caller must supply
    enabled=True and the capture pipeline must assert current source rights.
    Sandbox is mandatory on Linux, with no browser egress and no personal profile.
    """

    renderer_id = "playwright-python"
    renderer_version = RENDERER_VERSION
    requires_render_authorization = True

    def __init__(
        self,
        *,
        enabled: bool = False,
        chromium_binary: str | None = None,
        timeout_seconds: float = 12.0,
        max_requests: int = _MAX_REQUESTS,
        allowed_subresource_hosts: tuple[str, ...] = (),
        fetcher: Callable[..., FetchedBytes] = fetch_bytes,
        resolver: Callable = socket.getaddrinfo,
        playwright_factory: Callable | None = None,
    ) -> None:
        if not (isinstance(timeout_seconds, (int, float))
                and not isinstance(timeout_seconds, bool)
                and 1 <= timeout_seconds <= 30):
            raise BrowserRenderBlocked("BROWSER_TIMEOUT_POLICY_INVALID")
        if type(max_requests) is not int or not 1 <= max_requests <= 64:
            raise BrowserRenderBlocked("BROWSER_REQUEST_BUDGET_INVALID")
        if len(allowed_subresource_hosts) > 12 or any(
            not isinstance(host, str) or not host or
            host != host.lower() or
            host != urlsplit("https://" + host).hostname or
            any(char in host for char in ("/", ":", "@", "%"))
            for host in allowed_subresource_hosts
        ):
            raise BrowserRenderBlocked("BROWSER_HOST_POLICY_INVALID")
        self.enabled = enabled is True
        self.chromium_binary = chromium_binary
        self.timeout_seconds = float(timeout_seconds)
        self.max_requests = max_requests
        self.allowed_subresource_hosts = frozenset(allowed_subresource_hosts)
        self.fetcher = fetcher
        self.resolver = resolver
        self.playwright_factory = playwright_factory
        self.sandbox_executable = Path(__file__).with_name("browser_renderer_netns.sh")
        self.last_receipt: dict[str, str | int] | None = None

    def _preflight(self) -> None:
        if not self.enabled:
            raise BrowserRenderBlocked("BROWSER_POLICY_DISABLED")
        if platform.system() != "Linux" or not shutil.which("bwrap"):
            raise BrowserRenderBlocked("BROWSER_LINUX_NETNS_REQUIRED")
        wrapper = self.sandbox_executable
        if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
            raise BrowserRenderBlocked("BROWSER_NETNS_WRAPPER_MISSING")
        try:
            installed_version = importlib.metadata.version("playwright")
        except importlib.metadata.PackageNotFoundError:
            raise BrowserRenderBlocked("BROWSER_PLAYWRIGHT_NOT_INSTALLED") from None
        if installed_version != PLAYWRIGHT_VERSION:
            raise BrowserRenderBlocked("BROWSER_PLAYWRIGHT_VERSION_MISMATCH")
        if self.chromium_binary is None or (
            not Path(self.chromium_binary).is_absolute()
            or not (self.chromium_binary.startswith("/usr/bin/")
                    or self.chromium_binary.startswith("/opt/"))
            or not Path(self.chromium_binary).is_file()
            or not os.access(self.chromium_binary, os.X_OK)
        ):
            raise BrowserRenderBlocked("BROWSER_CHROMIUM_BINARY_INVALID")

    def render(
        self, url: str, *, max_response_bytes: int,
        authorization_guard: Callable[[], None] | None = None,
    ) -> FetchedBytes:
        self.last_receipt = None
        self._preflight()
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= MAX_DISCOVERY_RESPONSE_BYTES:
            raise BrowserRenderBlocked("BROWSER_BODY_BUDGET_INVALID")
        try:
            url = validate_discovery_url(url, resolver=self.resolver)
        except (ValueError, TypeError):
            raise BrowserRenderBlocked("BROWSER_TARGET_REFUSED") from None
        origin_host = urlsplit(url).hostname
        permitted_hosts = {origin_host, *self.allowed_subresource_hosts}
        budget_bytes = max_response_bytes * 2
        total_bytes = 0
        request_count = 0
        blocked: str | None = None
        authorization_error: PrivateCaptureAuthorizationBlocked | None = None
        deadline = time.monotonic() + self.timeout_seconds

        def route_request(route) -> None:
            nonlocal request_count, total_bytes, blocked, authorization_error
            request = route.request
            # Browser is in a network namespace with no egress. No fallback to
            # Chromium's fetch or route.continue_ is ever permitted.
            try:
                if blocked:
                    route.abort()
                    return
                if request.resource_type not in _ALLOWED_RESOURCES:
                    route.abort()
                    return
                if request.method != "GET":
                    raise BrowserRenderBlocked("BROWSER_REQUEST_METHOD_REFUSED")
                # Rights may be withdrawn after the previous resource was read.
                if authorization_guard is not None:
                    authorization_guard()
                request_count += 1
                if request_count > self.max_requests or time.monotonic() >= deadline:
                    raise BrowserRenderBlocked("BROWSER_RESOURCE_BUDGET_EXCEEDED")
                requested = validate_discovery_url(request.url, resolver=self.resolver)
                if urlsplit(requested).hostname not in permitted_hosts:
                    raise BrowserRenderBlocked("BROWSER_SUBRESOURCE_HOST_REFUSED")
                if request.is_navigation_request() and requested != url:
                    raise BrowserRenderBlocked("BROWSER_NAVIGATION_REFUSED")
                remaining = min(max_response_bytes, budget_bytes - total_bytes)
                if remaining <= 0:
                    raise BrowserRenderBlocked("BROWSER_RESOURCE_BUDGET_EXCEEDED")
                timeout = max(0.1, min(5.0, deadline - time.monotonic()))
                if timeout <= 0.1 and time.monotonic() >= deadline:
                    raise BrowserRenderBlocked("BROWSER_TIMEOUT")
                fetched = self.fetcher(
                    requested, timeout=timeout, max_response_bytes=remaining,
                    resolver=self.resolver,
                )
                # route.fulfill serves bytes under request.url and cannot
                # represent a followed HTTP redirect. Refuse all redirects,
                # including same-host ones, to preserve source identity.
                final = validate_discovery_url(fetched.final_url, resolver=self.resolver)
                if final != requested:
                    raise BrowserRenderBlocked("BROWSER_HTTP_REDIRECT_REFUSED")
                if (fetched.status_code < 200 or fetched.status_code >= 300
                        or len(fetched.body) != fetched.content_length
                        or len(fetched.body) > remaining):
                    raise BrowserRenderBlocked("BROWSER_RESPONSE_REFUSED")
                total_bytes += len(fetched.body)
                route.fulfill(
                    status=fetched.status_code,
                    body=fetched.body,
                    headers={"content-type": fetched.media_type +
                             ("; charset=" + fetched.charset if fetched.charset else "")},
                )
            except PrivateCaptureAuthorizationBlocked as exc:
                authorization_error = exc
                blocked = "BROWSER_RIGHTS_REVOKED"
                route.abort()
            except Exception:
                # Never permit a failed guard to downgrade to browser networking.
                blocked = "BROWSER_RESOURCE_REFUSED"
                route.abort()

        def remaining_timeout_ms() -> int:
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0:
                raise BrowserRenderBlocked("BROWSER_TIMEOUT")
            return remaining

        try:
            if self.playwright_factory is None:
                from playwright.sync_api import sync_playwright
                factory = sync_playwright
            else:
                factory = self.playwright_factory
            with factory() as playwright:
                chrome_bin = self.chromium_binary
                if not Path(chrome_bin).is_absolute():
                    raise BrowserRenderBlocked("BROWSER_CHROMIUM_BINARY_INVALID")
                env = {
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "LANG": "C.UTF-8",
                    "HOME": "/tmp",
                    "DICHIARAZIONI_PLAYWRIGHT_CHROMIUM_BIN": chrome_bin,
                }
                browser = playwright.chromium.launch(
                    executable_path=str(self.sandbox_executable),
                    headless=True,
                    chromium_sandbox=True,
                    timeout=remaining_timeout_ms(),
                    env=env,
                    args=["--disable-background-networking", "--disable-extensions",
                          "--disable-sync", "--disable-gpu", "--no-first-run",
                          "--renderer-process-limit=2",
                          "--js-flags=--max-old-space-size=128",
                          "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
                )
                try:
                    context = browser.new_context(
                        accept_downloads=False, service_workers="block",
                        permissions=[], ignore_https_errors=False,
                    )
                    try:
                        context.route("**/*", route_request)
                        # WebSockets are not HTTP routes and must be blocked
                        # independently before any page JS can run.
                        context.route_web_socket("**/*", lambda websocket: websocket.close())
                        page = context.new_page()
                        page.set_default_timeout(remaining_timeout_ms())
                        page.on("popup", lambda popup: popup.close())
                        page.on("download", lambda download: download.cancel())
                        page.goto(url, wait_until="domcontentloaded",
                                  timeout=remaining_timeout_ms())
                        if blocked:
                            if authorization_error is not None:
                                raise authorization_error
                            raise BrowserRenderBlocked(blocked)
                        remaining_ms = int(max(0, deadline - time.monotonic()) * 1000)
                        if remaining_ms <= 0:
                            raise BrowserRenderBlocked("BROWSER_TIMEOUT")
                        page.wait_for_timeout(min(500, remaining_ms))
                        remaining_timeout_ms()
                        html = page.content().encode("utf-8")
                        remaining_timeout_ms()
                        final_url = validate_discovery_url(page.url, resolver=self.resolver)
                        if final_url != url:
                            raise BrowserRenderBlocked("BROWSER_FINAL_URL_CHANGED")
                        if blocked:
                            if authorization_error is not None:
                                raise authorization_error
                            raise BrowserRenderBlocked(blocked)
                        if len(html) > max_response_bytes:
                            raise BrowserRenderBlocked("BROWSER_RENDERED_BODY_TOO_LARGE")
                        version = str(browser.version)
                    finally:
                        context.close()
                finally:
                    browser.close()
        except BrowserRenderBlocked:
            raise
        except Exception:
            if authorization_error is not None:
                raise authorization_error from None
            raise BrowserRenderBlocked(blocked or "BROWSER_RENDER_FAILED") from None
        result = FetchedBytes(
            body=html, final_url=final_url, status_code=200,
            media_type="text/html", charset="utf-8", content_length=len(html),
        )
        self.last_receipt = {
            "renderer_id": self.renderer_id,
            "renderer_version": self.renderer_version,
            "playwright_version": PLAYWRIGHT_VERSION,
            "chromium_version": version[:80],
            "rendered_sha256": hashlib.sha256(html).hexdigest(),
            "rendered_bytes": len(html),
            "resource_count": request_count,
            "resource_bytes": total_bytes,
            "egress_policy": "bwrap-unshare-net-pinned-https-v1",
        }
        return result


def render_with_current_rights(
    renderer, url: str, *, max_response_bytes: int, source_use_guard, rights_guard,
) -> FetchedBytes:
    """Revalidate rights on every browser resource; preserve legacy adapter calls."""
    if not getattr(renderer, "requires_render_authorization", False):
        return renderer.render(url, max_response_bytes=max_response_bytes)

    def recheck() -> None:
        if source_use_guard is not None:
            source_use_guard.require("FETCH")
        if rights_guard is not None:
            rights_guard()

    return renderer.render(
        url, max_response_bytes=max_response_bytes, authorization_guard=recheck,
    )
