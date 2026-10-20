"""Explicitly synthetic rights object used only by prior worker unit fixtures."""
from types import SimpleNamespace


def cleared_caption_rights():
    return SimpleNamespace(
        rights_record_id="synthetic:approved-youtube",
        require=lambda use: SimpleNamespace(decision_fingerprint="a" * 64),
    )
