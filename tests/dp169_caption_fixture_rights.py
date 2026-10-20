"""Explicitly synthetic rights object used only by prior worker unit fixtures."""
from types import SimpleNamespace


def cleared_caption_rights():
    return SimpleNamespace(
        rights_record_id="synthetic:approved-youtube",
        require=lambda use: SimpleNamespace(decision_fingerprint="a" * 64),
    )


def synthetic_caption_variant(handler, *, guard, **kwargs):
    """Old receipt tests exercise their fake store, never an actual rights DB."""
    segments = kwargs.pop("segments")
    variant_id, inserted = handler.store.insert_transcript_variant(**kwargs)
    if inserted:
        handler.store.insert_transcript_segments(variant_id=variant_id, segments=segments)
    return variant_id, inserted
