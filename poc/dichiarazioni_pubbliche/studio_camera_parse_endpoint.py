"""Authenticated read-only Studio adapter for DP-319B private source-use checks."""
from __future__ import annotations

import re
from typing import Any

from dichiarazioni_pubbliche.camera_parse_authority import CameraParseAuthority

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def inspect_camera_parse(service: Any, body: dict[str, Any]) -> dict[str, Any]:
    if set(body) != {"content_id", "capture_sha256", "use"}:
        raise ValueError("CAMERA_PARSE_REQUEST_FIELDS_INVALID")
    if type(service) is not CameraParseAuthority:
        raise RuntimeError("CAMERA_PARSE_AUTHORITY_NOT_CONFIGURED")
    if (
        not isinstance(body["content_id"], str)
        or not isinstance(body["capture_sha256"], str)
        or not _SHA.fullmatch(body["capture_sha256"])
        or not isinstance(body["use"], str)
    ):
        raise ValueError("CAMERA_PARSE_REQUEST_INVALID")
    return service.inspect(**body)
