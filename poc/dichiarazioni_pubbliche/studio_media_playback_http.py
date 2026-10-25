"""Private Studio binary media delivery adapter with a narrow HTTP mixin.

All authentication, Origin checks and strict JSON parsing belong to the caller;
this module handles only the media payload and security-safe response headers.
"""
from __future__ import annotations

from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore
from dichiarazioni_pubbliche.studio_readonly_db import StudioReadOnlyDb
from dichiarazioni_pubbliche.studio_media_playback import verified_media_playback


class StudioMediaRightsReader(StudioReadOnlyDb, PrivateRightsRegistryStore):
    pass


class StudioMediaHttpMixin:
    def _verified_media_reply(self, payload: dict[str, object]) -> None:
        if payload.keys() != {"binding_id"}:
            raise ValueError("STUDIO_MEDIA_PLAYBACK_FIELDS_INVALID")
        readers = self.server.readers
        if readers.body_store is None or readers.rights_reader is None:
            raise RuntimeError("STUDIO_LOCAL_MEDIA_NOT_CONFIGURED")
        media = verified_media_playback(
            capture_reader=readers.captures,
            rights_reader=readers.rights_reader,
            body_store=readers.body_store,
            binding_id=payload["binding_id"],
        )
        self.send_response(200)
        self.send_header("Content-Type", media.media_type)
        self.send_header("Content-Length", str(len(media.body)))
        self.send_header("X-Seek-Start-Ms", str(media.start_ms))
        self.send_header("X-Seek-End-Ms", str(media.end_ms))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(media.body)
        except OSError:
            pass
