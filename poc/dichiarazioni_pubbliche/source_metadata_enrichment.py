from __future__ import annotations

import hashlib
import ipaddress
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


METADATA_ENRICHMENT_VERSION = "source-metadata-enrichment-v1"
MAX_CANDIDATES_PER_FIELD = 8
MAX_VALUE_CHARS = 1024
MAX_URL_CHARS = 4096


class MetadataEnrichmentError(ValueError):
    pass


@dataclass(frozen=True)
class MetadataCandidate:
    field: str
    value: str
    origin: str
    publication_authority: bool = False


@dataclass(frozen=True)
class MetadataConflict:
    code: str
    field: str
    expected_origin: str
    expected_value: str
    observed_values: tuple[str, ...]


@dataclass(frozen=True)
class MetadataEnrichment:
    content_id: str
    candidates: tuple[MetadataCandidate, ...]
    canonical_url_candidates: tuple[str, ...]
    oembed_endpoint_candidates: tuple[str, ...]
    conflicts: tuple[MetadataConflict, ...]
    contract_version: str = METADATA_ENRICHMENT_VERSION
    publication_authority: bool = False
    identity_mutation_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "content_id": self.content_id,
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "canonical_url_candidates": list(self.canonical_url_candidates),
            "oembed_endpoint_candidates": list(self.oembed_endpoint_candidates),
            "conflicts": [asdict(conflict) for conflict in self.conflicts],
            "publication_authority": self.publication_authority,
            "identity_mutation_allowed": self.identity_mutation_allowed,
        }


def _bounded_text(value: object) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return text[:MAX_VALUE_CHARS]


def _compare_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _safe_https_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or len(raw) > MAX_URL_CHARS:
        return None
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        return None
    host = parsed.hostname.rstrip(".").casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return None
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        return None
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    netloc = ascii_host if port is None else f"{ascii_host}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def _unsafe_fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


def _append_candidate(
    target: list[MetadataCandidate],
    seen: set[tuple[str, str, str]],
    *,
    field: str,
    value: object,
    origin: str,
) -> None:
    text = _bounded_text(value)
    if text is None:
        return
    key = (field, _compare_text(text), origin)
    if key in seen:
        return
    if sum(candidate.field == field for candidate in target) >= MAX_CANDIDATES_PER_FIELD:
        return
    seen.add(key)
    target.append(MetadataCandidate(field=field, value=text, origin=origin))


def _page_candidates(parsed_metadata: Mapping[str, Any]) -> tuple[MetadataCandidate, ...]:
    candidates: list[MetadataCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    meta = parsed_metadata.get("meta")
    if isinstance(meta, Mapping):
        field_keys = {
            "title": ("og:title", "twitter:title", "title"),
            "description": ("og:description", "twitter:description", "description"),
            "author": ("author", "article:author"),
            "publisher": ("publisher", "og:site_name", "application-name"),
        }
        for field, keys in field_keys.items():
            for key in keys:
                if key in meta:
                    _append_candidate(
                        candidates,
                        seen,
                        field=field,
                        value=meta.get(key),
                        origin=f"page_meta:{key}",
                    )

    jsonld = parsed_metadata.get("jsonld_identity")
    if isinstance(jsonld, Sequence) and not isinstance(jsonld, (str, bytes, bytearray)):
        for index, node in enumerate(jsonld[:8]):
            if not isinstance(node, Mapping):
                continue
            _append_candidate(
                candidates,
                seen,
                field="title",
                value=node.get("headline") or node.get("name"),
                origin=f"jsonld:{index}",
            )
            for field in ("author", "publisher"):
                raw = node.get(field)
                if isinstance(raw, Mapping):
                    raw = raw.get("name")
                _append_candidate(
                    candidates,
                    seen,
                    field=field,
                    value=raw,
                    origin=f"jsonld:{index}:{field}",
                )
    return tuple(candidates)


def _reference_candidates(
    identity: Mapping[str, Any] | None,
    *,
    origin: str,
) -> tuple[MetadataCandidate, ...]:
    if identity is None:
        return ()
    if not isinstance(identity, Mapping):
        raise MetadataEnrichmentError(f"{origin.upper()}_IDENTITY_INVALID")
    candidates: list[MetadataCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for field in ("title", "author", "publisher"):
        _append_candidate(
            candidates,
            seen,
            field=field,
            value=identity.get(field),
            origin=origin,
        )
    return tuple(candidates)


def _field_conflicts(
    *,
    page_candidates: Sequence[MetadataCandidate],
    content_identity: Mapping[str, Any],
    source_registry_identity: Mapping[str, Any] | None,
) -> list[MetadataConflict]:
    conflicts: list[MetadataConflict] = []
    page_by_field: dict[str, list[str]] = {}
    for candidate in page_candidates:
        page_by_field.setdefault(candidate.field, []).append(candidate.value)

    references: list[tuple[str, Mapping[str, Any]]] = [("content", content_identity)]
    if source_registry_identity is not None:
        references.append(("source_registry", source_registry_identity))
    for origin, identity in references:
        for field in ("title", "author", "publisher"):
            expected = _bounded_text(identity.get(field))
            observed = page_by_field.get(field, [])
            if expected is None or not observed:
                continue
            normalized_expected = _compare_text(expected)
            if normalized_expected not in {_compare_text(value) for value in observed}:
                conflicts.append(
                    MetadataConflict(
                        code=f"{origin.upper()}_{field.upper()}_CONFLICT",
                        field=field,
                        expected_origin=origin,
                        expected_value=expected,
                        observed_values=tuple(observed[:MAX_CANDIDATES_PER_FIELD]),
                    )
                )
    return conflicts


def build_metadata_enrichment(
    *,
    content_id: str,
    parsed_metadata: Mapping[str, Any],
    content_identity: Mapping[str, Any],
    source_registry_identity: Mapping[str, Any] | None = None,
) -> MetadataEnrichment:
    clean_content_id = _bounded_text(content_id)
    if clean_content_id is None:
        raise MetadataEnrichmentError("CONTENT_ID_REQUIRED")
    if not isinstance(parsed_metadata, Mapping):
        raise MetadataEnrichmentError("PARSED_METADATA_INVALID")
    if not isinstance(content_identity, Mapping):
        raise MetadataEnrichmentError("CONTENT_IDENTITY_INVALID")
    if source_registry_identity is not None and not isinstance(source_registry_identity, Mapping):
        raise MetadataEnrichmentError("SOURCE_REGISTRY_IDENTITY_INVALID")

    expected_content_url = _safe_https_url(content_identity.get("canonical_url"))
    if content_identity.get("canonical_url") and expected_content_url is None:
        raise MetadataEnrichmentError("CONTENT_CANONICAL_URL_UNSAFE")
    expected_source_url = None
    if source_registry_identity and source_registry_identity.get("canonical_url"):
        expected_source_url = _safe_https_url(source_registry_identity.get("canonical_url"))
        if expected_source_url is None:
            raise MetadataEnrichmentError("SOURCE_REGISTRY_CANONICAL_URL_UNSAFE")

    conflicts = _field_conflicts(
        page_candidates=_page_candidates(parsed_metadata),
        content_identity=content_identity,
        source_registry_identity=source_registry_identity,
    )

    canonical_urls: list[str] = []
    raw_canonicals = parsed_metadata.get("canonical_url_candidates")
    if isinstance(raw_canonicals, Sequence) and not isinstance(raw_canonicals, (str, bytes, bytearray)):
        for raw in raw_canonicals[:MAX_CANDIDATES_PER_FIELD]:
            safe = _safe_https_url(raw)
            if safe is None:
                conflicts.append(
                    MetadataConflict(
                        code="UNSAFE_CANONICAL_CANDIDATE",
                        field="canonical_url",
                        expected_origin="capture_policy",
                        expected_value="safe_https_public_url",
                        observed_values=(_unsafe_fingerprint(raw),),
                    )
                )
                continue
            if safe not in canonical_urls:
                canonical_urls.append(safe)

    if len(canonical_urls) > 1:
        conflicts.append(
            MetadataConflict(
                code="PAGE_CANONICAL_AMBIGUOUS",
                field="canonical_url",
                expected_origin="page",
                expected_value=canonical_urls[0],
                observed_values=tuple(canonical_urls),
            )
        )
    if expected_content_url and canonical_urls and expected_content_url not in canonical_urls:
        conflicts.append(
            MetadataConflict(
                code="CONTENT_CANONICAL_URL_CONFLICT",
                field="canonical_url",
                expected_origin="content",
                expected_value=expected_content_url,
                observed_values=tuple(canonical_urls),
            )
        )
    if expected_source_url and canonical_urls and expected_source_url not in canonical_urls:
        conflicts.append(
            MetadataConflict(
                code="SOURCE_REGISTRY_CANONICAL_URL_CONFLICT",
                field="canonical_url",
                expected_origin="source_registry",
                expected_value=expected_source_url,
                observed_values=tuple(canonical_urls),
            )
        )
    if expected_content_url and expected_source_url and expected_content_url != expected_source_url:
        conflicts.append(
            MetadataConflict(
                code="CONTENT_SOURCE_REGISTRY_CANONICAL_CONFLICT",
                field="canonical_url",
                expected_origin="content",
                expected_value=expected_content_url,
                observed_values=(expected_source_url,),
            )
        )

    oembed_endpoints: list[str] = []
    raw_oembed = parsed_metadata.get("oembed_candidates")
    if isinstance(raw_oembed, Sequence) and not isinstance(raw_oembed, (str, bytes, bytearray)):
        for row in raw_oembed[:MAX_CANDIDATES_PER_FIELD]:
            raw_url = row.get("url") if isinstance(row, Mapping) else None
            safe = _safe_https_url(raw_url)
            if safe is None:
                conflicts.append(
                    MetadataConflict(
                        code="UNSAFE_OEMBED_ENDPOINT",
                        field="oembed_endpoint",
                        expected_origin="capture_policy",
                        expected_value="safe_https_public_url",
                        observed_values=(_unsafe_fingerprint(raw_url),),
                    )
                )
                continue
            if safe not in oembed_endpoints:
                oembed_endpoints.append(safe)

    page = list(_page_candidates(parsed_metadata))
    references = list(_reference_candidates(content_identity, origin="content"))
    references.extend(
        _reference_candidates(source_registry_identity, origin="source_registry")
    )
    return MetadataEnrichment(
        content_id=clean_content_id,
        candidates=tuple(page + references),
        canonical_url_candidates=tuple(canonical_urls),
        oembed_endpoint_candidates=tuple(oembed_endpoints),
        conflicts=tuple(conflicts),
    )


__all__ = [
    "MAX_CANDIDATES_PER_FIELD",
    "MAX_URL_CHARS",
    "MAX_VALUE_CHARS",
    "METADATA_ENRICHMENT_VERSION",
    "MetadataCandidate",
    "MetadataConflict",
    "MetadataEnrichment",
    "MetadataEnrichmentError",
    "build_metadata_enrichment",
]
