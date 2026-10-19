"""Opt-in private Wikidata lookup: review proposals, never identity authority.

WikibaseIntegrator is imported only inside the optional read-only backend.
No caller or public endpoint invokes this adapter automatically. The caller must
first obtain a CURRENT source-use decision from evaluate_source_use and an
independent, source-bound operator egress approval. Neither can approve an ID.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Callable, Mapping, Protocol

from dichiarazioni_pubbliche.knowledge_repository import (
    EntityResolutionCandidateRecord,
    make_resolution_candidate,
    normalized_alias,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceUseDecision


ADAPTER_VERSION = "wikidata-proposal-v1"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_HOST = "www.wikidata.org"
_QID = re.compile(r"Q[1-9][0-9]{0,11}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TYPES = {"PERSON": frozenset({"Q5"}),
          "ORGANIZATION": frozenset({"Q43229", "Q4830453", "Q7278", "Q3918"})}


@dataclass(frozen=True)
class WikidataLookupRequest:
    local_entity_id: str
    entity_type: str
    aliases: tuple[str, ...]
    source_sha256: str
    reference_date: str | None = None
    role_qid: str | None = None
    type_qids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EgressApproval:
    host: str
    purpose: str
    reviewed_by: str
    expires_at: datetime
    source_sha256: str


@dataclass(frozen=True)
class WikidataReceipt:
    qid: str
    url: str
    revision: int
    observed_at: str
    source_sha256: str
    rights_decision_fingerprint: str
    adapter_version: str = ADAPTER_VERSION


@dataclass(frozen=True)
class WikidataProposal:
    local_entity_id: str
    entity_type: str
    mention_text: str
    qid: str
    receipt: WikidataReceipt

    def to_resolution_candidate(self, *, content_id: str, passage_id: str | None = None) -> EntityResolutionCandidateRecord:
        """Build an unapproved local candidate; persistence/review stays elsewhere."""
        return make_resolution_candidate(
            content_id=content_id, passage_id=passage_id,
            mention_text=self.mention_text, entity_type=self.entity_type,
            target_id=self.local_entity_id, resolution_method="CONTEXT_MATCH",
            supporting_features=({"code": "WIKIDATA_QID_PROPOSAL", "qid": self.qid},),
            metadata={"external_lookup": asdict(self.receipt),
                      "external_lookup_status": "REVIEW_REQUIRED"},
        )


@dataclass(frozen=True)
class WikidataLookupResult:
    status: str
    reason: str
    proposals: tuple[WikidataProposal, ...] = ()


class WikidataBackend(Protocol):
    def search(self, alias: str, *, language: str, limit: int, timeout: float) -> list[str]: ...
    def get_item(self, qid: str, *, timeout: float) -> Mapping: ...


class WikibaseIntegratorReadOnly:
    """WikibaseIntegrator 0.12.15 search/get only, no authenticated writes.

    Each call has a strict request timeout and one API attempt. Throttle reads,
    including subsequent entity fetches, instead of retrying 429/maxlag storms.
    """

    def __init__(self, *, user_agent: str, spacing_seconds: float = 1.0):
        if not isinstance(user_agent, str) or len(user_agent.strip()) < 12:
            raise ValueError("WIKIDATA_USER_AGENT_REQUIRED")
        # Deferred import: ordinary installs never acquire HTTP dependencies.
        from wikibaseintegrator import WikibaseIntegrator, wbi_helpers

        self._helpers = wbi_helpers
        self._client = WikibaseIntegrator()
        self._user_agent = user_agent
        self._spacing = spacing_seconds
        self._last_call: float | None = None

    def _pace(self):
        now = time.monotonic()
        if self._last_call is not None:
            delay = self._spacing - (now - self._last_call)
            if delay > 0:
                time.sleep(delay)
        self._last_call = time.monotonic()

    def search(self, alias: str, *, language: str, limit: int, timeout: float) -> list[str]:
        self._pace()
        return self._helpers.search_entities(
            search_string=alias, language=language, strict_language=True,
            search_type="item", max_results=limit, dict_result=False,
            mediawiki_api_url=WIKIDATA_API, user_agent=self._user_agent,
            max_retries=1, retry_after=0, timeout=(timeout, timeout),
            allow_redirects=False,
        )

    def get_item(self, qid: str, *, timeout: float) -> Mapping:
        self._pace()
        item = self._client.item.get(
            entity_id=qid, mediawiki_api_url=WIKIDATA_API,
            user_agent=self._user_agent, allow_anonymous=True,
            max_retries=1, retry_after=0, timeout=(timeout, timeout),
            allow_redirects=False,
        )
        return {**item.get_json(), "id": qid, "lastrevid": item.lastrevid}


def _valid_request(request: WikidataLookupRequest) -> bool:
    if not isinstance(request, WikidataLookupRequest):
        return False
    if (request.entity_type not in {"PERSON", "ORGANIZATION", "TOPIC"}
        or not isinstance(request.local_entity_id, str)
        or not 0 < len(request.local_entity_id.strip()) <= 128
        or not isinstance(request.source_sha256, str)
        or not _SHA.fullmatch(request.source_sha256)
        or not isinstance(request.aliases, tuple)
        or not 1 <= len(request.aliases) <= 5
        or any(not isinstance(a, str) or not 2 <= len(a.strip()) <= 96 or "\n" in a
               for a in request.aliases)
        or not isinstance(request.type_qids, tuple)
        or len(request.type_qids) > 8
        or any(not isinstance(q, str) or not _QID.fullmatch(q) for q in request.type_qids)
        or (request.role_qid is not None and (not isinstance(request.role_qid, str)
                                              or not _QID.fullmatch(request.role_qid)))):
        return False
    if request.reference_date is not None:
        try:
            date.fromisoformat(request.reference_date)
        except (ValueError, TypeError):
            return False
    return True


def _qid_claims(entity: Mapping, prop: str) -> set[str] | None:
    claims = entity.get("claims")
    if not isinstance(claims, dict) or not isinstance(claims.get(prop, []), list):
        return None
    result = set()
    for row in claims.get(prop, []):
        if not isinstance(row, dict):
            return None
        value = row.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not _QID.fullmatch(value["id"]):
            return None
        result.add(value["id"])
    return result


def _time_value(snak: object) -> date | None:
    if not isinstance(snak, dict):
        return None
    value = snak.get("datavalue", {}).get("value")
    if not isinstance(value, dict) or not isinstance(value.get("time"), str):
        return None
    match = re.fullmatch(r"\+([0-9]{4})-([0-9]{2})-([0-9]{2})T00:00:00Z", value["time"])
    if not match or type(value.get("precision")) is not int or value["precision"] < 11:
        return None
    try:
        return date(*(int(n) for n in match.groups()))
    except ValueError:
        return None


def _person_role_valid(entity: Mapping, role_qid: str, when: date) -> bool:
    claims = entity.get("claims", {})
    if not isinstance(claims, dict) or not isinstance(claims.get("P39"), list):
        return False
    for row in claims["P39"]:
        if not isinstance(row, dict):
            return False
        value = row.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict) or value.get("id") != role_qid:
            continue
        qualifiers = row.get("qualifiers")
        if not isinstance(qualifiers, dict):
            continue
        start = qualifiers.get("P580")
        end = qualifiers.get("P582")
        if not isinstance(start, list) or len(start) != 1 or not isinstance(end, list) or len(end) != 1:
            continue
        lower, upper = _time_value(start[0]), _time_value(end[0])
        if lower is not None and upper is not None and lower <= when <= upper:
            return True
    return False


def _organization_epoch_valid(entity: Mapping, when: date) -> bool:
    claims = entity.get("claims", {})
    if not isinstance(claims, dict):
        return False
    inception = claims.get("P571")
    dissolved = claims.get("P576", [])
    if not isinstance(inception, list) or len(inception) != 1 or not isinstance(dissolved, list) or len(dissolved) > 1:
        return False
    start = _time_value(inception[0].get("mainsnak")) if isinstance(inception[0], dict) else None
    end = (_time_value(dissolved[0].get("mainsnak")) if isinstance(dissolved[0], dict)
           else None) if dissolved else None
    return bool(start and start <= when and (not dissolved or (end and when <= end)))


def _exact_alias(entity: Mapping, aliases: tuple[str, ...]) -> bool | None:
    labels, alt = entity.get("labels"), entity.get("aliases")
    if not isinstance(labels, dict) or not isinstance(alt, dict):
        return None
    names: list[str] = []
    for item in labels.values():
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            return None
        names.append(item["value"])
    for group in alt.values():
        if not isinstance(group, list):
            return None
        for item in group:
            if not isinstance(item, dict) or not isinstance(item.get("value"), str):
                return None
            names.append(item["value"])
    return bool({normalized_alias(name) for name in names if name.strip()} &
                {normalized_alias(alias) for alias in aliases})


def _eligible(entity: Mapping, request: WikidataLookupRequest) -> bool | None:
    if not isinstance(entity, Mapping):
        return None
    revision = entity.get("lastrevid")
    if type(revision) is not int or revision < 1:
        return None
    aliases_match = _exact_alias(entity, request.aliases)
    instance = _qid_claims(entity, "P31")
    if aliases_match is None or instance is None:
        return None
    if not aliases_match:
        return False
    allowed = set(request.type_qids) if request.entity_type == "TOPIC" else _TYPES[request.entity_type]
    if not allowed or not (instance & allowed):
        return False
    if request.entity_type == "PERSON":
        if not request.role_qid or not request.reference_date:
            return None
        return _person_role_valid(entity, request.role_qid, date.fromisoformat(request.reference_date))
    if request.entity_type == "ORGANIZATION" and request.reference_date:
        return _organization_epoch_valid(entity, date.fromisoformat(request.reference_date))
    return True


class WikidataProposalAdapter:
    def __init__(self, *, backend: WikidataBackend | None = None, enabled: bool = False,
                 user_agent: str | None = None, clock: Callable[[], datetime] | None = None,
                 monotonic: Callable[[], float] | None = None, timeout_seconds: float = 3.0,
                 min_interval_seconds: float = 1.0, cache_max_entries: int = 32,
                 cache_ttl_seconds: float = 120.0):
        if not (0 < timeout_seconds <= 10 and 0 <= min_interval_seconds <= 60
                and 1 <= cache_max_entries <= 128 and 0 < cache_ttl_seconds <= 300):
            raise ValueError("WIKIDATA_BOUNDS_INVALID")
        self._backend = backend
        self._enabled = enabled
        self._user_agent = user_agent
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._timeout = timeout_seconds
        self._interval = min_interval_seconds
        self._max_cache = cache_max_entries
        self._ttl = cache_ttl_seconds
        self._cache: OrderedDict[str, tuple[float, WikidataLookupResult]] = OrderedDict()
        self._last_lookup: float | None = None

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def lookup(self, request: WikidataLookupRequest, *, source_use: SourceUseDecision | None,
               egress: EgressApproval | None) -> WikidataLookupResult:
        def hold(reason: str) -> WikidataLookupResult:
            return WikidataLookupResult("HOLD", reason)

        if not self._enabled:
            return hold("ADAPTER_DISABLED")
        if not _valid_request(request):
            return hold("REQUEST_INVALID")
        if (request.entity_type == "PERSON" and (not request.role_qid or not request.reference_date)):
            return hold("PERSON_CONTEXT_REQUIRED")
        if request.entity_type == "TOPIC" and not request.type_qids:
            return hold("TOPIC_TYPE_REQUIRED")
        if (not isinstance(source_use, SourceUseDecision)
            or source_use.use != "DISCOVER_METADATA" or not source_use.permitted
            or not isinstance(source_use.record_id, str) or not source_use.record_id.strip()
            or not isinstance(source_use.decision_fingerprint, str)
            or not _SHA.fullmatch(source_use.decision_fingerprint)):
            return hold("SOURCE_USE_NOT_AUTHORIZED")
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return hold("CLOCK_INVALID")
        if (not isinstance(egress, EgressApproval)
            or egress.host != WIKIDATA_HOST
            or egress.purpose != "PRIVATE_ENTITY_PROPOSAL"
            or not isinstance(egress.reviewed_by, str) or not egress.reviewed_by.strip()
            or not isinstance(egress.expires_at, datetime)
            or egress.expires_at.tzinfo is None or egress.expires_at.utcoffset() is None
            or egress.expires_at <= now or egress.source_sha256 != request.source_sha256):
            return hold("EGRESS_NOT_AUTHORIZED")
        fingerprint = hashlib.sha256(json.dumps({
            "request": asdict(request), "source_use": source_use.decision_fingerprint,
            "record_id": source_use.record_id, "approval": {
                "reviewed_by": egress.reviewed_by,
                "expires_at": egress.expires_at.isoformat(),
            }, "version": ADAPTER_VERSION,
        }, sort_keys=True).encode()).hexdigest()
        tick = self._monotonic()
        cached = self._cache.get(fingerprint)
        if cached and 0 <= tick - cached[0] < self._ttl:
            self._cache.move_to_end(fingerprint)
            return cached[1]
        if self._last_lookup is not None and tick - self._last_lookup < self._interval:
            return hold("RATE_LIMIT")
        self._last_lookup = tick
        try:
            backend = self._backend
            if backend is None:
                if not self._user_agent:
                    return hold("USER_AGENT_REQUIRED")
                backend = WikibaseIntegratorReadOnly(user_agent=self._user_agent)
            qids: set[str] = set()
            for alias in dict.fromkeys(request.aliases):
                rows = backend.search(alias, language="it", limit=5, timeout=self._timeout)
                if not isinstance(rows, (list, tuple)) or len(rows) >= 5:
                    return hold("RESULT_CAP_OR_INVALID")
                if any(not isinstance(qid, str) or not _QID.fullmatch(qid) for qid in rows):
                    return hold("MALFORMED_PROVIDER_RESPONSE")
                qids.update(rows)
                if len(qids) > 5:
                    return hold("RESULT_CAP_OR_INVALID")
            eligible: list[Mapping] = []
            unresolved = False
            for qid in sorted(qids):
                entity = backend.get_item(qid, timeout=self._timeout)
                if not isinstance(entity, Mapping) or entity.get("id") != qid:
                    return hold("MALFORMED_PROVIDER_RESPONSE")
                outcome = _eligible(entity, request)
                if outcome is None:
                    unresolved = True
                elif outcome:
                    eligible.append(entity)
            if len(eligible) > 1:
                return hold("HOMONYMS")
            if unresolved:
                return hold("UNRESOLVED_CANDIDATE")
            if not eligible:
                return hold("NO_VERIFIABLE_MATCH")
            row = eligible[0]
            qid = row["id"]
            observed_at = self._clock()
            if (not isinstance(observed_at, datetime)
                or observed_at.tzinfo is None or observed_at.utcoffset() is None
                or observed_at >= egress.expires_at):
                return hold("EGRESS_EXPIRED_DURING_LOOKUP")
            receipt = WikidataReceipt(
                qid=qid, url=f"https://{WIKIDATA_HOST}/wiki/{qid}",
                revision=row["lastrevid"], observed_at=observed_at.astimezone(timezone.utc).isoformat(),
                source_sha256=request.source_sha256,
                rights_decision_fingerprint=source_use.decision_fingerprint,
            )
            result = WikidataLookupResult("PROPOSED", "WIKIDATA_REVIEW_REQUIRED", (
                WikidataProposal(request.local_entity_id, request.entity_type,
                                 request.aliases[0], qid, receipt),
            ))
            self._cache[fingerprint] = (tick, result)
            self._cache.move_to_end(fingerprint)
            if len(self._cache) > self._max_cache:
                self._cache.popitem(last=False)
            return result
        except (ImportError, ModuleNotFoundError):
            return hold("OPTIONAL_DEPENDENCY_MISSING")
        except Exception:
            # No raw provider error or potentially private query leaks via UI/logs.
            return hold("PROVIDER_FAILURE")
