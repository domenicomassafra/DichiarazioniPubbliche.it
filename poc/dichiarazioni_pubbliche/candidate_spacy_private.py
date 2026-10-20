"""Opt-in spaCy mentions for private, authorization-fenced candidate extraction.

No pretrained model is bundled or downloaded. The wrapper preserves the DP-211
commit/review machinery; NER can only add source-anchored CANDIDATE mentions.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.candidate_extraction import (
    CandidateExtractionError,
    CandidateExtractionProvider,
    CandidateExtractionReceipt,
    CandidateExtractionStore,
    PreparedEntityMention,
    ProviderExtractionResult,
    _mention_id,
    extract_passage_candidates,
)
from dichiarazioni_pubbliche.private_candidate_commit_fence import PrivateCandidateCommitFence


ADAPTER_VERSION = "spacy-private-entities-v1"
_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0"})
_LABEL_TYPES = {"PER": "PERSON", "ORG": "ORGANIZATION", "LOC": None}


@dataclass(frozen=True)
class ApprovedSpaCyModel:
    source_url: str
    revision: str
    license_id: str
    pipeline_sha256: str

    def validate(self) -> None:
        url = urlsplit(self.source_url)
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise CandidateExtractionError("SPACY_MODEL_SOURCE_INVALID")
        if not re.fullmatch(r"[A-Za-z0-9._-]{7,100}", self.revision):
            raise CandidateExtractionError("SPACY_MODEL_REVISION_INVALID")
        if self.license_id not in _LICENSES:
            raise CandidateExtractionError("SPACY_MODEL_LICENSE_NOT_APPROVED")
        if not re.fullmatch(r"[0-9a-f]{64}", self.pipeline_sha256):
            raise CandidateExtractionError("SPACY_MODEL_DIGEST_INVALID")


@dataclass(frozen=True)
class SpaCyEntitySpan:
    start_char: int
    end_char: int
    text: str
    text_sha256: str
    label: str


class SpaCyItalianPrivateAdapter:
    """Explicitly approved spaCy Italian pipeline; default runtime has none."""

    def __init__(self, pipeline: Any, *, approval: ApprovedSpaCyModel) -> None:
        approval.validate()
        if getattr(pipeline, "lang", None) != "it":
            raise CandidateExtractionError("SPACY_MODEL_LANGUAGE_INVALID")
        metadata = getattr(pipeline, "meta", None)
        if not isinstance(metadata, dict) or metadata.get("license") != approval.license_id:
            raise CandidateExtractionError("SPACY_MODEL_LICENSE_MISMATCH")
        component_names = getattr(pipeline, "pipe_names", ())
        if not {"ner", "entity_ruler"}.intersection(component_names):
            raise CandidateExtractionError("SPACY_MODEL_NER_MISSING")
        try:
            actual_digest = hashlib.sha256(pipeline.to_bytes()).hexdigest()
        except Exception as exc:
            raise CandidateExtractionError("SPACY_MODEL_DIGEST_UNAVAILABLE") from exc
        if actual_digest != approval.pipeline_sha256:
            raise CandidateExtractionError("SPACY_MODEL_DIGEST_MISMATCH")
        self._pipeline = pipeline
        self._digest = actual_digest
        self.approval = approval
        self.fingerprint = hashlib.sha256(
            (ADAPTER_VERSION + "\x1f" + approval.source_url + "\x1f"
             + approval.revision + "\x1f" + approval.pipeline_sha256).encode("utf-8")
        ).hexdigest()
        # Safe to persist: metadata only, never source text or model predictions.
        self.receipt = {
            "adapter": ADAPTER_VERSION,
            "model_source_url": approval.source_url,
            "model_revision": approval.revision,
            "model_license": approval.license_id,
            "model_pipeline_sha256": approval.pipeline_sha256,
            "adapter_fingerprint": self.fingerprint,
        }

    @classmethod
    def load(
        cls, model_directory: Path, *, approval: ApprovedSpaCyModel
    ) -> SpaCyItalianPrivateAdapter:
        approval.validate()
        if not isinstance(model_directory, Path) or not model_directory.is_dir():
            raise CandidateExtractionError("SPACY_MODEL_UNAVAILABLE")
        try:
            import spacy  # optional dependency; never downloaded implicitly
        except ImportError as exc:
            raise CandidateExtractionError("SPACY_PACKAGE_UNAVAILABLE") from exc
        try:
            pipeline = spacy.load(model_directory)
        except (OSError, ValueError, KeyError) as exc:
            raise CandidateExtractionError("SPACY_MODEL_UNAVAILABLE") from exc
        return cls(pipeline, approval=approval)

    def propose(
        self, *, text: str, text_sha256: str, language: str | None
    ) -> tuple[SpaCyEntitySpan, ...]:
        if language != "it":
            raise CandidateExtractionError("SPACY_PASSAGE_LANGUAGE_UNSUPPORTED")
        if not isinstance(text, str) or not text or len(text) > 32000:
            raise CandidateExtractionError("SPACY_PASSAGE_TEXT_INVALID")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != text_sha256:
            raise CandidateExtractionError("SPACY_PASSAGE_HASH_MISMATCH")
        try:
            current_digest = hashlib.sha256(self._pipeline.to_bytes()).hexdigest()
        except Exception as exc:
            raise CandidateExtractionError("SPACY_MODEL_DIGEST_UNAVAILABLE") from exc
        if current_digest != self._digest:
            raise CandidateExtractionError("SPACY_MODEL_CHANGED")
        try:
            document = self._pipeline(text)
        except Exception as exc:
            raise CandidateExtractionError("SPACY_NER_FAILED") from exc
        if getattr(document, "text", None) != text:
            raise CandidateExtractionError("SPACY_NER_TEXT_CHANGED")
        spans: list[SpaCyEntitySpan] = []
        seen: set[tuple[int, int, str]] = set()
        for entity in document.ents:
            label = str(entity.label_)
            if label not in _LABEL_TYPES:
                continue  # MISC and other labels do not become entity identities.
            start, end = entity.start_char, entity.end_char
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(text)
                    or entity.text != text[start:end]):
                raise CandidateExtractionError("SPACY_NER_SPAN_INVALID")
            key = (start, end, label)
            if key in seen:
                raise CandidateExtractionError("SPACY_NER_DUPLICATE_SPAN")
            seen.add(key)
            excerpt = text[start:end]
            spans.append(SpaCyEntitySpan(
                start, end, excerpt, hashlib.sha256(excerpt.encode("utf-8")).hexdigest(), label
            ))
            if len(spans) > 128:
                raise CandidateExtractionError("SPACY_NER_TOO_MANY_SPANS")
        return tuple(sorted(spans, key=lambda span: (span.start_char, span.end_char, span.label)))


class _VersionedProvider:
    def __init__(
        self, original: CandidateExtractionProvider, adapter: SpaCyItalianPrivateAdapter
    ) -> None:
        self._original = original
        self._receipt = adapter.receipt
        self.provider_id = original.provider_id
        self.model_id = original.model_id
        # Replay identity changes whenever an approved pipeline/revision changes.
        self.provider_version = original.provider_version + "+spacy:" + adapter.fingerprint

    def __getattr__(self, name: str) -> Any:
        # copy/deepcopy may probe attributes before reconstructing _original.
        return getattr(object.__getattribute__(self, "_original"), name)

    def cost_upper_bound_usd(self, request: Any) -> Decimal:
        return self._original.cost_upper_bound_usd(request)

    def extract(self, request: Any) -> Any:
        result = self._original.extract(request)
        if isinstance(result, ProviderExtractionResult) and isinstance(result.receipt, Mapping):
            return replace(result, receipt={**result.receipt, "spacy_model": self._receipt})
        return result


class _MentionStore:
    def __init__(
        self, original: CandidateExtractionStore, spans: tuple[SpaCyEntitySpan, ...],
        adapter: SpaCyItalianPrivateAdapter, input_sha256: str,
    ) -> None:
        self._original = original
        self._spans = spans
        self._adapter = adapter
        self._input_sha256 = input_sha256

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)

    def commit_batch(self, **kwargs: Any) -> Any:
        context = kwargs["context"]
        if context.text_sha256 != self._input_sha256 or (
            hashlib.sha256(context.text.encode("utf-8")).hexdigest() != self._input_sha256
        ):
            raise CandidateExtractionError("SPACY_PASSAGE_CHANGED")
        batch = kwargs["batch"]
        existing = {
            (m.start_char, m.end_char, m.proposed_entity_type)
            for m in batch.mentions if m.extraction_method == "MODEL"
        }
        additions: list[PreparedEntityMention] = []
        for span in self._spans:
            proposed_type = _LABEL_TYPES[span.label]
            if (span.start_char, span.end_char, proposed_type) in existing:
                continue
            existing.add((span.start_char, span.end_char, proposed_type))
            additions.append(PreparedEntityMention(
                id=_mention_id(
                    kwargs["run_id"], context.passage_id, span.start_char,
                    span.end_char, "MODEL", proposed_type
                ),
                passage_id=context.passage_id,
                start_char=span.start_char,
                end_char=span.end_char,
                mention_text=span.text,
                mention_text_sha256=span.text_sha256,
                proposed_entity_type=proposed_type,
                extraction_method="MODEL",  # allowed by the current private DB contract
                metadata={
                    "ner_backend": "spacy",
                    "ner_label": span.label,
                    "review_required": True,
                    "model_receipt": self._adapter.receipt,
                },
            ))
        kwargs["batch"] = replace(batch, mentions=batch.mentions + tuple(additions))
        return self._original.commit_batch(**kwargs)


def extract_passage_candidates_with_spacy(
    *, passage_id: str, store: CandidateExtractionStore,
    provider: CandidateExtractionProvider, adapter: SpaCyItalianPrivateAdapter,
    max_cost_usd: Decimal | str | float = Decimal("0"),
    authorization_guard: Callable[[], None] | None = None,
    commit_fence: PrivateCandidateCommitFence | None = None,
) -> CandidateExtractionReceipt:
    """Propose private NER mentions via the existing fail-closed DP-211 commit.

    Requires the same rights guard and commit fence as the private operator.
    It never performs alias linking, speaker identification or publication.
    """
    if authorization_guard is None or commit_fence is None:
        raise CandidateExtractionError("SPACY_PRIVATE_AUTHORITY_REQUIRED")
    if not isinstance(adapter, SpaCyItalianPrivateAdapter):
        raise CandidateExtractionError("SPACY_MODEL_APPROVAL_REQUIRED")
    try:
        commit_fence.sql_parameters()
    except ValueError as exc:
        raise CandidateExtractionError("SPACY_PRIVATE_FENCE_INVALID") from exc
    if commit_fence.passage_id != passage_id:
        raise CandidateExtractionError("SPACY_PRIVATE_FENCE_PASSAGE_MISMATCH")
    authorization_guard()
    context = store.load_passage(passage_id)
    if context is None:
        raise CandidateExtractionError("CANDIDATE_PASSAGE_NOT_FOUND")
    if context.passage_id != passage_id:
        raise CandidateExtractionError("SPACY_PASSAGE_ID_MISMATCH")
    if (context.content_id != commit_fence.content_id
            or context.capture_id != commit_fence.capture_id
            or context.text_sha256 != commit_fence.passage_sha256):
        raise CandidateExtractionError("SPACY_PRIVATE_FENCE_CONTEXT_MISMATCH")
    spans = adapter.propose(
        text=context.text, text_sha256=context.text_sha256, language=context.language
    )
    return extract_passage_candidates(
        passage_id=passage_id,
        store=_MentionStore(store, spans, adapter, context.text_sha256),
        provider=_VersionedProvider(provider, adapter),
        max_cost_usd=max_cost_usd,
        authorization_guard=authorization_guard,
        commit_fence=commit_fence,
    )
