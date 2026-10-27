"""Invalidate Cloudflare public caches and verify omission before intake ACK.

Cloudflare Cache Purge: https://developers.cloudflare.com/api/resources/cache/methods/purge/
Only a complete 503/no-store readback is accepted while the challenged static
release is quarantined. Any partial purge/readback leaves the ledger HOLD active.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import quote


@dataclass(frozen=True)
class CloudflareCorrectionPurge:
    zone_id: str
    token: str = field(repr=False)
    site_origin: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", self.zone_id):
            raise ValueError("CLOUDFLARE_ZONE_ID_INVALID")
        if not self.token or any(ch.isspace() for ch in self.token):
            raise ValueError("CLOUDFLARE_TOKEN_INVALID")
        if self.site_origin != "https://dichiarazionipubbliche.it":
            raise ValueError("CORRECTION_SITE_ORIGIN_INVALID")

    @staticmethod
    def _read_status(request: urllib.request.Request) -> tuple[int, dict, bytes]:
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, dict(response.headers), response.read(8193)
        except urllib.error.HTTPError as response:
            try:
                return response.code, dict(response.headers), response.read(8193)
            finally:
                response.close()

    def __call__(self, finding_id: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", finding_id):
            return False
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}/purge_cache"
        request = urllib.request.Request(
            endpoint,
            data=b'{"purge_everything":true}',
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            code, _, body = self._read_status(request)
            receipt = json.loads(body)
            if (code != 200 or not isinstance(receipt, dict)
                    or receipt.get("success") is not True or receipt.get("errors") != []):
                return False
            paths = ("/", "/api/v1/index.json", "/api/v1/findings/" + quote(finding_id, safe=""))
            for path in paths:
                probe = urllib.request.Request(
                    self.site_origin + path,
                    headers={"Cache-Control": "no-cache", "Accept": "application/json"},
                    method="GET",
                )
                status, headers, _ = self._read_status(probe)
                cache_control = next((str(value) for key, value in headers.items() if key.lower() == "cache-control"), "")
                if status != 503 or "no-store" not in cache_control.lower():
                    return False
            return True
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            return False
