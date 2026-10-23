"""Capture target and bounded response validation shared by the capture pipeline.

Pure guards: never perform DNS lookups. The transport separately pins resolved
public endpoints at every actual HTTPS connection.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.source_watcher import (
    FetchedBytes, MAX_DISCOVERY_RESPONSE_BYTES,
)


class CapturePipelineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "CAPTURE_PIPELINE_FAILURE").strip().upper()[:120]
        super().__init__(self.code)


def _capture_response_limit(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_DISCOVERY_RESPONSE_BYTES:
        raise CapturePipelineError("CAPTURE_RESPONSE_LIMIT_INVALID")
    return value


def _validate_capture_target(value: object, *, final: bool) -> None:
    """No DNS calls: refuse unsafe literal/ambiguous URLs at both pipeline boundaries.

    The transport's own DNS/redirect policy still owns address resolution and
    connection safety; validation here cannot certify an arbitrary fetcher.
    """
    prefix = "CAPTURE_FINAL_URL" if final else "CAPTURE_URL"
    if (not isinstance(value, str) or not value or len(value) > 4096
            or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value)):
        raise CapturePipelineError(f"{prefix}_INVALID")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise CapturePipelineError(f"{prefix}_INVALID") from None
    if parsed.scheme.lower() != "https" or not hostname:
        raise CapturePipelineError(f"{prefix}_HTTPS_REQUIRED")
    if parsed.username is not None or parsed.password is not None or port not in {None, 443}:
        raise CapturePipelineError(f"{prefix}_AUTHORITY_REFUSED")
    host = hostname.rstrip(".")
    if (not host or "%" in host or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))):
        raise CapturePipelineError(f"{prefix}_LOCAL_HOST_REFUSED")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        # libc accepts IPv4 aliases rejected by ipaddress, e.g. 2130706433,
        # 0177.0.0.1 and 0x7f000001. Reject all such ambiguous IP spellings;
        # a resolver might otherwise connect to loopback/link-local targets.
        try:
            socket.inet_aton(host)
        except OSError:
            pass
        else:
            raise CapturePipelineError(f"{prefix}_AMBIGUOUS_IP") from None
    else:
        if not literal.is_global:
            raise CapturePipelineError(f"{prefix}_NONPUBLIC_IP")


def _validate_fetched_resource(fetched: FetchedBytes, *, max_response_bytes: int) -> None:
    if not isinstance(fetched.body, bytes):
        raise CapturePipelineError("CAPTURE_BODY_INVALID")
    if len(fetched.body) > _capture_response_limit(max_response_bytes):
        raise CapturePipelineError("CAPTURE_RESPONSE_TOO_LARGE")
    if type(fetched.content_length) is not int or fetched.content_length != len(fetched.body):
        raise CapturePipelineError("CAPTURE_CONTENT_LENGTH_MISMATCH")
    if type(fetched.status_code) is not int or not 200 <= fetched.status_code < 300:
        raise CapturePipelineError("CAPTURE_HTTP_STATUS_BLOCKED")
    _validate_capture_target(fetched.final_url, final=True)
