"""Connect the DP-202 CLI to the current private rights registry, read only."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject


def registered_source_guard(
    context_path: Path | None, *, audit_path: Path,
) -> SourceFamilyUseGuard | None:
    """Select a reviewed record; the private registry remains the authority.

    The context selects a subject and pins transcript bytes. Neither this
    context file nor the historical fixture grants rights by itself.
    """
    if context_path is None:
        return None
    try:
        context = json.loads(context_path.read_text())
        metadata = json.loads(audit_path.read_text())["content"]
        source_url = context["source_url"]
        if source_url not in {metadata["instagram_url"], metadata["tiktok_url"]}:
            raise ValueError("DP202_WRONG_SOURCE")
        subject = RightsSubject(
            source_family=context["source_family"], locator_kind="URL",
            locator_value=source_url, content_id=context["content_id"],
        )
        registry = PrivateRightsRegistryStore(database_url=os.environ.get("DATABASE_URL"))
        current = registry.read_current(subject)
        if current is None:
            raise ValueError("DP202_RIGHTS_MISSING")
        digest = context["transcript_sha256"]
        guard = SourceFamilyUseGuard(
            read_current=registry.read_current,
            subject=subject, rights_record_id=current.id,
            policy_version=context["policy_version"],
            expected_sha256=digest,
        )
        guard.require("PARSE_TEXT", content_sha256=digest)
        return guard
    except Exception:
        raise RuntimeError("DP202_SOURCE_RIGHTS_UNVERIFIED") from None
