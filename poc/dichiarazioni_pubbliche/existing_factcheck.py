from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


GOOGLE_FACTCHECK_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
FACTCHECK_ADAPTER_VERSION = "existing-factcheck-v1"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ExistingFactCheckError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "EXISTING_FACTCHECK_ERROR").strip().upper()[:120]
        super().__init__(self.code)


@dataclass(frozen=True)
class ExistingFactCheckRecord:
    record_id: str
    provider_id: str
    claim_text: str
    claimant: str | None
    claim_date: str | None
    review_publisher_name: str | None
    review_publisher_site: str | None
    review_url: str
    review_title: str | None
    review_date: str | None
    textual_rating: str | None
    language_code: str | None
    adapter_version: str = FACTCHECK_ADAPTER_VERSION


@dataclass(frozen=True)
class ExistingFactCheckSearchResult:
    records: tuple[ExistingFactCheckRecord, ...]
    next_page_token: str | None
    provider_receipt: dict[str, Any]


def _text(value: Any, *, limit: int, required: bool = False) -> str | None:
    if value is None:
        result = ""
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        result = str(value).strip()
    else:
        result = ""
    if required and not result:
        raise ExistingFactCheckError("FACTCHECK_REQUIRED_FIELD_MISSING")
    return result[:limit] or None


def _https_url(value: Any) -> str:
    raw = _text(value, limit=4096, required=True)
    assert raw is not None
    parsed = urlsplit(raw)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ExistingFactCheckError("FACTCHECK_REVIEW_URL_INVALID")
    return raw


def _record_id(
    *,
    provider_id: str,
    claim_text: str,
    review_url: str,
    publisher_site: str | None,
) -> str:
    material = "\x1f".join(
        (provider_id, claim_text, review_url, publisher_site or "", FACTCHECK_ADAPTER_VERSION)
    )
    return "existing-factcheck:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalize_google_factcheck_response(
    payload: Mapping[str, Any],
) -> ExistingFactCheckSearchResult:
    raw_claims = payload.get("claims") or []
    if not isinstance(raw_claims, list):
        raise ExistingFactCheckError("FACTCHECK_RESPONSE_CLAIMS_INVALID")
    records: list[ExistingFactCheckRecord] = []
    for claim in raw_claims[:100]:
        if not isinstance(claim, Mapping):
            continue
        claim_text = _text(claim.get("text"), limit=8192)
        if not claim_text:
            continue
        claimant = _text(claim.get("claimant"), limit=1024)
        claim_date = _text(claim.get("claimDate"), limit=128)
        reviews = claim.get("claimReview") or []
        if not isinstance(reviews, list):
            continue
        for review in reviews[:20]:
            if not isinstance(review, Mapping):
                continue
            try:
                review_url = _https_url(review.get("url"))
            except ExistingFactCheckError:
                continue
            publisher = review.get("publisher") or {}
            if not isinstance(publisher, Mapping):
                publisher = {}
            publisher_name = _text(publisher.get("name"), limit=1024)
            publisher_site = _text(publisher.get("site"), limit=512)
            records.append(
                ExistingFactCheckRecord(
                    record_id=_record_id(
                        provider_id="google-factcheck-tools",
                        claim_text=claim_text,
                        review_url=review_url,
                        publisher_site=publisher_site,
                    ),
                    provider_id="google-factcheck-tools",
                    claim_text=claim_text,
                    claimant=claimant,
                    claim_date=claim_date,
                    review_publisher_name=publisher_name,
                    review_publisher_site=publisher_site,
                    review_url=review_url,
                    review_title=_text(review.get("title"), limit=2048),
                    review_date=_text(review.get("reviewDate"), limit=128),
                    textual_rating=_text(review.get("textualRating"), limit=1024),
                    language_code=_text(review.get("languageCode"), limit=64),
                )
            )
    next_page = _text(payload.get("nextPageToken"), limit=4096)
    return ExistingFactCheckSearchResult(
        records=tuple(records),
        next_page_token=next_page,
        provider_receipt={
            "provider_id": "google-factcheck-tools",
            "adapter_version": FACTCHECK_ADAPTER_VERSION,
            "claim_count": len(raw_claims),
            "normalized_review_count": len(records),
            "has_next_page": bool(next_page),
        },
    )


def _default_transport(url: str, *, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DichiarazioniPubbliche/0.0.1 existing-factcheck",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > MAX_RESPONSE_BYTES:
                        raise ExistingFactCheckError("FACTCHECK_RESPONSE_TOO_LARGE")
                except ValueError:
                    pass
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except ExistingFactCheckError:
        raise
    except Exception as exc:
        raise ExistingFactCheckError("FACTCHECK_PROVIDER_REQUEST_FAILED") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise ExistingFactCheckError("FACTCHECK_RESPONSE_TOO_LARGE")
    return body


class GoogleFactCheckAdapter:
    provider_id = "google-factcheck-tools"
    adapter_version = FACTCHECK_ADAPTER_VERSION

    def __init__(
        self,
        api_key: str,
        *,
        transport: Callable[..., bytes] = _default_transport,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        if not self.api_key:
            raise ExistingFactCheckError("FACTCHECK_API_KEY_REQUIRED")
        self.transport = transport
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))

    def search(
        self,
        query: str,
        *,
        language_code: str = "it",
        review_publisher_site: str | None = None,
        max_age_days: int | None = None,
        page_size: int = 10,
        page_token: str | None = None,
    ) -> ExistingFactCheckSearchResult:
        query_text = str(query or "").strip()
        publisher = str(review_publisher_site or "").strip()
        if not query_text and not publisher:
            raise ExistingFactCheckError("FACTCHECK_QUERY_OR_PUBLISHER_REQUIRED")
        if not 1 <= int(page_size) <= 50:
            raise ExistingFactCheckError("FACTCHECK_PAGE_SIZE_INVALID")
        if max_age_days is not None and not 0 <= int(max_age_days) <= 36500:
            raise ExistingFactCheckError("FACTCHECK_MAX_AGE_INVALID")
        params: dict[str, str | int] = {
            "key": self.api_key,
            "pageSize": int(page_size),
        }
        if query_text:
            params["query"] = query_text[:4096]
        if language_code:
            params["languageCode"] = str(language_code)[:64]
        if publisher:
            params["reviewPublisherSiteFilter"] = publisher[:512]
        if max_age_days is not None:
            params["maxAgeDays"] = int(max_age_days)
        if page_token:
            params["pageToken"] = str(page_token)[:4096]
        url = GOOGLE_FACTCHECK_ENDPOINT + "?" + urlencode(params)
        body = self.transport(url, timeout_seconds=self.timeout_seconds)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ExistingFactCheckError("FACTCHECK_RESPONSE_TOO_LARGE")
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExistingFactCheckError("FACTCHECK_RESPONSE_JSON_INVALID") from exc
        if not isinstance(decoded, Mapping):
            raise ExistingFactCheckError("FACTCHECK_RESPONSE_OBJECT_REQUIRED")
        result = normalize_google_factcheck_response(decoded)
        # Never retain the API key or full request URL in the receipt.
        return ExistingFactCheckSearchResult(
            records=result.records,
            next_page_token=result.next_page_token,
            provider_receipt={
                **result.provider_receipt,
                "query_sha256": hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
                "page_size": int(page_size),
                "language_code": str(language_code)[:64],
                "publisher_filter": publisher or None,
                "max_age_days": max_age_days,
            },
        )


__all__ = [
    "FACTCHECK_ADAPTER_VERSION",
    "GOOGLE_FACTCHECK_ENDPOINT",
    "ExistingFactCheckError",
    "ExistingFactCheckRecord",
    "ExistingFactCheckSearchResult",
    "GoogleFactCheckAdapter",
    "normalize_google_factcheck_response",
]
