from __future__ import annotations

import math
import urllib.error
from typing import Any

from dichiarazioni_pubbliche.claim_contract import validate_atomic_claim
from dichiarazioni_pubbliche.claim_runtime import (
    deterministic_claim_id,
    estimate_claim_request_cost,
)
from dichiarazioni_pubbliche.claim_windows import (
    build_claim_windows,
    canonical_segment_from_row,
)
from dichiarazioni_pubbliche.evidence_runtime import (
    EvidencePolicyError,
    EvidenceRateLimited,
    deterministic_evidence_id,
    get_evidence_source,
)
from dichiarazioni_pubbliche.evidence_query import compile_official_query
from dichiarazioni_pubbliche.queue_runtime import deterministic_followup_job_id
from dichiarazioni_pubbliche.verification_runtime import deterministic_evidence_observation_id
from dichiarazioni_pubbliche.worker_errors import BlockedJob, DeferredJob, RetryableJob


class ClaimEvidenceJobHandlers:
    def prepare_claim_windows(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        variant_id = str(job.payload.get("variant_id") or "").strip()
        if not variant_id:
            raise BlockedJob("CLAIM_PREPARE_VARIANT_ID_MISSING")
        blocker = self._claim_runtime_blocker()
        if blocker:
            self.store.update_content_status(
                content.content_id,
                "CLAIM_EXTRACTION_BLOCKED",
                {
                    "runtime_blocker": blocker,
                    "claim_variant_id": variant_id,
                    "claim_window_materialized": False,
                },
            )
            raise BlockedJob(blocker)
        rows = self.store.canonical_segments(content.content_id)
        if not rows:
            raise RetryableJob("CLAIM_PREPARE_CANONICAL_SEGMENTS_MISSING", 60)
        windows = build_claim_windows(
            [canonical_segment_from_row(row) for row in rows]
        )
        if not windows:
            raise BlockedJob("CLAIM_PREPARE_NO_WINDOWS")
        ordered = sorted(
            windows,
            key=lambda window: (
                {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(window.priority, 3),
                window.window_index,
            ),
        )
        jobs = []
        total_tokens = 0
        for window in ordered:
            payload = window.queue_payload(
                source_id=content.source_id,
                variant_id=variant_id,
                model=self.claim_client.model,
                prompt_version=self.claim_client.prompt_version,
            )
            estimated_cost = estimate_claim_request_cost(
                estimated_input_tokens=window.estimated_input_tokens,
                max_output_tokens=self.claim_client.max_output_tokens,
                max_usd_per_1k_total_tokens=(
                    self.claim_max_usd_per_1k_total_tokens
                ),
            )
            if estimated_cost is None:
                raise BlockedJob("CLAIM_EXTRACTION_COST_MODEL_MISSING")
            payload["estimated_cost_usd"] = estimated_cost
            payload["max_output_tokens"] = self.claim_client.max_output_tokens
            total_tokens += window.estimated_input_tokens
            jobs.append(
                {
                    "id": deterministic_followup_job_id(
                        "CLAIM_EXTRACT_WINDOW",
                        content.content_id,
                        window.input_sha256,
                    ),
                    "content_id": content.content_id,
                    "job_type": "CLAIM_EXTRACT_WINDOW",
                    "state": "QUEUED",
                    "payload": payload,
                    "last_error": "",
                }
            )
        created = self.store.enqueue_jobs_bulk(jobs)
        self.store.update_content_status(
            content.content_id,
            "CLAIM_EXTRACTION_QUEUED",
            {
                "claim_window_count": len(windows),
                "claim_window_new_jobs": created,
                "claim_window_blocked_jobs": 0,
                "claim_window_estimated_input_tokens": total_tokens,
                "claim_window_schema_version": "claim-window-v2",
                "claim_prompt_version": self.claim_client.prompt_version,
            },
        )
    def _claim_runtime_blocker(self) -> str | None:
        if self.claim_client is None:
            return "CLAIM_EXTRACTION_CREDENTIAL_MISSING"
        if self.claim_max_usd_per_1k_total_tokens is None:
            return "CLAIM_EXTRACTION_COST_MODEL_MISSING"
        if self._claim_probe is None:
            self._claim_probe = self.claim_client.probe()
        if not self._claim_probe.healthy:
            if self._claim_probe.reason == "LOCAL_INFERENCE_BUSY":
                self._claim_probe = None
                raise RetryableJob("LOCAL_INFERENCE_BUSY", 60)
            reason = self._claim_probe.reason.replace(" ", "_")[:180]
            return f"CLAIM_EXTRACTION_CANARY_FAILED:{reason}"
        return None
    def extract_claim_window(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        blocker = self._claim_runtime_blocker()
        if blocker:
            raise BlockedJob(blocker)
        expected_hash = str(job.payload.get("input_sha256") or "").strip()
        if not expected_hash:
            raise BlockedJob("CLAIM_WINDOW_HASH_MISSING")
        rows = self.store.canonical_segments(content.content_id)
        windows = build_claim_windows(
            [canonical_segment_from_row(row) for row in rows]
        )
        matches = [window for window in windows if window.input_sha256 == expected_hash]
        if len(matches) != 1:
            raise BlockedJob("CLAIM_WINDOW_SOURCE_DRIFT")
        window = matches[0]
        payload_indices = tuple(
            int(value) for value in job.payload.get("segment_indices") or []
        )
        if payload_indices != window.segment_indices:
            raise BlockedJob("CLAIM_WINDOW_SEGMENT_DRIFT")
        try:
            result = self.claim_client.extract(
                window_text=window.text,
                allowed_segment_indices=window.segment_indices,
            )
        except RuntimeError as exc:
            message = str(exc)
            if ("HTTP_429" in message or "HTTP_503" in message
                    or "timed out" in message or message == "LOCAL_INFERENCE_BUSY"):
                raise RetryableJob(
                    f"CLAIM_PROVIDER_TRANSIENT:{message[:160]}",
                    300,
                ) from exc
            raise BlockedJob(f"CLAIM_PROVIDER_BLOCKED:{message[:180]}") from exc
        except ValueError as exc:
            raise BlockedJob(f"CLAIM_RESPONSE_INVALID:{str(exc)[:180]}") from exc

        segment_id_by_index = {
            int(row["segment_index"]): str(row["id"]) for row in rows
        }
        claim_rows = []
        for claim in result.claims:
            claim_id = deterministic_claim_id(
                content_id=content.content_id,
                window_sha256=window.input_sha256,
                prompt_version=self.claim_client.prompt_version,
                model=self.claim_client.model,
                claim=claim,
            )
            segment_ids = [
                segment_id_by_index[index]
                for index in claim.source_segment_indices
                if index in segment_id_by_index
            ]
            if len(segment_ids) != len(claim.source_segment_indices):
                raise BlockedJob("CLAIM_RESPONSE_SEGMENT_MAPPING_FAILED")
            statement_date = str(
                job.payload.get("statement_date") or ""
            ).strip() or None
            try:
                contract = validate_atomic_claim(
                    claim_id=claim_id,
                    content_id=content.content_id,
                    normalized_claim=claim.normalized_claim,
                    claim_type=claim.claim_type,
                    statement_date=statement_date,
                    check_worthy=claim.check_worthy,
                    source_segment_ids=tuple(segment_ids),
                    metadata={
                        "speaker_label": claim.speaker,
                        "numeric_sensitive": claim.numeric_sensitive,
                        "window_sha256": window.input_sha256,
                        "source_segment_indices": list(
                            claim.source_segment_indices
                        ),
                        "request_id": result.request_id,
                    },
                )
            except ValueError as exc:
                raise BlockedJob(
                    f"CLAIM_CONTRACT_INVALID:{str(exc)[:140]}"
                ) from exc
            claim_rows.append(
                {
                    "id": contract.claim_id,
                    "content_id": content.content_id,
                    "normalized_claim": contract.normalized_claim,
                    "claim_type": contract.claim_type.value,
                    "temporal_scope": {
                        "statement_date": contract.temporal_scope.statement_date,
                        "source_timestamp": claim.source_timestamp,
                        "window_start_ms": window.start_ms,
                        "window_end_ms": window.end_ms,
                    },
                    "check_worthy": contract.check_worthy,
                    "extraction_model": self.claim_client.model,
                    "extraction_version": self.claim_client.prompt_version,
                    "metadata": contract.metadata,
                    "segment_ids": list(contract.source_segment_ids),
                }
            )
        inserted = self.store.insert_atomic_claims(claim_rows)
        if inserted != len(claim_rows):
            raise BlockedJob("CLAIM_REPLAY_CONFLICT")
        estimated = float(job.payload.get("estimated_cost_usd") or 0.0)
        measured = (
            max(float(result.observed_cost_usd), 0.0)
            if result.observed_cost_usd is not None
            else None
        )
        total_tokens = None
        if isinstance(result.usage, dict):
            raw_total_tokens = (
                result.usage.get("total_tokens")
                or result.usage.get("totalTokens")
            )
            if raw_total_tokens is None:
                prompt_tokens = (
                    result.usage.get("prompt_tokens")
                    or result.usage.get("input_tokens")
                    or 0
                )
                completion_tokens = (
                    result.usage.get("completion_tokens")
                    or result.usage.get("output_tokens")
                    or 0
                )
                try:
                    raw_total_tokens = int(prompt_tokens) + int(completion_tokens)
                except (TypeError, ValueError):
                    raw_total_tokens = None
            if raw_total_tokens is not None:
                try:
                    parsed_total_tokens = int(raw_total_tokens)
                except (TypeError, ValueError):
                    parsed_total_tokens = -1
                if parsed_total_tokens >= 0:
                    total_tokens = parsed_total_tokens
        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id=getattr(self.claim_client, "provider_id", "omniroute"),
            model_id=self.claim_client.model,
            operation="CLAIM_EXTRACT",
            request_id=result.request_id,
            input_bytes=len(window.text.encode()),
            input_seconds=None,
            estimated_cost_usd=max(estimated, 0.0),
            measured_cost_usd=measured,
            total_tokens=total_tokens,
            status="SUCCESS",
            receipt={
                "prompt_version": self.claim_client.prompt_version,
                "window_sha256": window.input_sha256,
                "claims_returned": len(result.claims),
                "claims_inserted": inserted,
                "latency_seconds": round(result.latency_seconds, 3),
                "usage": result.usage,
                "quality_gate": "PRIVATE_CANDIDATE_REVIEW_REQUIRED",
                "local_model_sha256": (
                    getattr(self.claim_client, "expected_model_digest", None)
                    if getattr(self.claim_client, "provider_id", None) == "ollama-local"
                    else None
                ),
                "billing_basis": (
                    "LOCAL_COMPUTE_UNMETERED"
                    if getattr(self.claim_client, "provider_id", None) == "ollama-local"
                    else "PROVIDER_USAGE"
                ),
            },
            request_key=window.input_sha256,
        )
        self.store.update_content_status(
            content.content_id,
            "CLAIM_EXTRACTION_IN_PROGRESS",
            {
                "atomic_claim_count": self.store.claim_count(content.content_id),
                "claim_last_window_sha256": window.input_sha256,
            },
        )
    def fetch_evidence_url(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        if self.evidence_fetcher is None:
            raise BlockedJob("EVIDENCE_FETCHER_NOT_CONFIGURED")
        source_id = str(job.payload.get("evidence_source_id") or "").strip()
        url = str(job.payload.get("url") or "").strip()
        claim_id = str(job.payload.get("claim_id") or "").strip()
        retrieval_version = str(
            job.payload.get("retrieval_version") or "evidence-url-v1"
        ).strip()
        retrieval_method = str(
            job.payload.get("retrieval_method") or "EXPLICIT_OFFICIAL_URL"
        ).strip()
        relation_candidate = str(
            job.payload.get("relation_candidate") or "UNKNOWN"
        ).strip()
        if not source_id or not url or not claim_id:
            raise BlockedJob("EVIDENCE_FETCH_PAYLOAD_INCOMPLETE")
        try:
            source = get_evidence_source(
                self.evidence_fetcher.registry, source_id
            )
        except KeyError as exc:
            raise BlockedJob("EVIDENCE_SOURCE_NOT_REGISTERED") from exc
        try:
            result = self.evidence_fetcher.fetch(source_id, url)
        except EvidenceRateLimited as exc:
            raise DeferredJob(
                f"EVIDENCE_RATE_LIMIT:{source_id}",
                max(int(math.ceil(exc.retry_after_seconds)), 1),
            ) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = int(retry_after) if retry_after else 300
                except ValueError:
                    delay = 300
                raise DeferredJob(
                    f"EVIDENCE_HTTP_429:{source_id}", delay
                ) from exc
            if 500 <= exc.code < 600:
                raise RetryableJob(
                    f"EVIDENCE_HTTP_{exc.code}:{source_id}", 300
                ) from exc
            raise BlockedJob(
                f"EVIDENCE_HTTP_{exc.code}:{source_id}"
            ) from exc
        except (EvidencePolicyError, ValueError) as exc:
            raise BlockedJob(
                f"EVIDENCE_POLICY:{str(exc)[:180]}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise RetryableJob(
                f"EVIDENCE_NETWORK:{type(exc).__name__}", 300
            ) from exc
        self._persist_evidence_result(
            job=job,
            content=content,
            source_id=source_id,
            source=source,
            result=result,
            retrieval_method=retrieval_method,
            retrieval_version=retrieval_version,
            relation_candidate=relation_candidate,
        )
    def query_official_evidence(
        self, job: ProcessingJob, content: ContentRecord
    ) -> None:
        if self.evidence_fetcher is None:
            raise BlockedJob("EVIDENCE_FETCHER_NOT_CONFIGURED")
        source_id = str(job.payload.get("evidence_source_id") or "").strip()
        query_kind = str(job.payload.get("query_kind") or "").strip()
        claim_id = str(job.payload.get("claim_id") or "").strip()
        params = job.payload.get("query_params")
        if not source_id or not query_kind or not claim_id:
            raise BlockedJob("EVIDENCE_QUERY_PAYLOAD_INCOMPLETE")
        if not isinstance(params, dict):
            raise BlockedJob("EVIDENCE_QUERY_PARAMS_INVALID")
        try:
            compiled = compile_official_query(source_id, query_kind, params)
            source = get_evidence_source(
                self.evidence_fetcher.registry, source_id
            )
        except (KeyError, ValueError) as exc:
            raise BlockedJob(
                f"EVIDENCE_QUERY_POLICY:{str(exc)[:180]}"
            ) from exc
        try:
            result = self.evidence_fetcher.request(
                compiled.source_id,
                compiled.url,
                method=compiled.method,
                body=compiled.body,
                content_type=compiled.content_type,
            )
        except EvidenceRateLimited as exc:
            raise DeferredJob(
                f"EVIDENCE_RATE_LIMIT:{source_id}",
                max(int(math.ceil(exc.retry_after_seconds)), 1),
            ) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = int(retry_after) if retry_after else 300
                except ValueError:
                    delay = 300
                raise DeferredJob(
                    f"EVIDENCE_HTTP_429:{source_id}", delay
                ) from exc
            if 500 <= exc.code < 600:
                raise RetryableJob(
                    f"EVIDENCE_HTTP_{exc.code}:{source_id}", 300
                ) from exc
            raise BlockedJob(
                f"EVIDENCE_HTTP_{exc.code}:{source_id}"
            ) from exc
        except (EvidencePolicyError, ValueError) as exc:
            raise BlockedJob(
                f"EVIDENCE_POLICY:{str(exc)[:180]}"
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise RetryableJob(
                f"EVIDENCE_NETWORK:{type(exc).__name__}", 300
            ) from exc
        self._persist_evidence_result(
            job=job,
            content=content,
            source_id=source_id,
            source=source,
            result=result,
            retrieval_method=compiled.retrieval_method,
            retrieval_version=compiled.retrieval_version,
            relation_candidate=str(
                job.payload.get("relation_candidate") or "UNKNOWN"
            ).strip(),
        )
    def _persist_evidence_result(
        self,
        *,
        job: ProcessingJob,
        content: ContentRecord,
        source_id: str,
        source: dict[str, Any],
        result,
        retrieval_method: str,
        retrieval_version: str,
        relation_candidate: str,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        if not claim_id:
            raise BlockedJob("EVIDENCE_CLAIM_ID_MISSING")
        receipt = result.receipt
        evidence_id = deterministic_evidence_id(
            source_id,
            receipt.canonical_url,
            receipt.content_sha256,
        )
        rights_status = str(
            job.payload.get("rights_status")
            or source.get("rights_status")
            or "UNKNOWN"
        )
        self.store.upsert_evidence(
            evidence_id=evidence_id,
            canonical_url=receipt.canonical_url,
            publisher=receipt.publisher,
            source_type=receipt.evidence_class,
            publication_date=(
                str(job.payload.get("publication_date") or "").strip()
                or None
            ),
            valid_from=(str(job.payload.get("valid_from") or "").strip() or None),
            valid_until=(str(job.payload.get("valid_until") or "").strip() or None),
            record_status=(
                str(job.payload.get("record_status") or "").strip().upper() or None
            ),
            fetched_at=receipt.fetched_at,
            content_sha256=receipt.content_sha256,
            excerpt=None,
            reference_period=(
                str(job.payload.get("reference_period") or "").strip()
                or None
            ),
            independence_group=(
                str(job.payload.get("independence_group") or source_id).strip()
                or source_id
            ),
            rights_status=rights_status,
            metadata={
                "evidence_source_id": source_id,
                "authoritative": receipt.authoritative,
                "http_status": receipt.http_status,
                "content_type": receipt.content_type,
                "response_bytes": receipt.response_bytes,
                "final_url": receipt.final_url,
                "from_cache": receipt.from_cache,
                "private_body": "CONTENT_ADDRESSED",
                "etag_present": bool(receipt.etag),
                "last_modified": receipt.last_modified,
            },
        )
        self.store.link_claim_evidence(
            claim_id=claim_id,
            evidence_id=evidence_id,
            retrieval_method=retrieval_method,
            retrieval_version=retrieval_version,
            relation_candidate=relation_candidate,
            status="RETRIEVED",
            score=None,
            statement_cutoff=(
                str(job.payload.get("statement_cutoff") or "").strip()
                or None
            ),
            metadata={
                "source_id": source_id,
                "content_sha256": receipt.content_sha256,
                "authoritative": receipt.authoritative,
            },
        )
        self.store.record_receipt(
            job_id=job.job_id,
            content_id=content.content_id,
            provider_id=source_id,
            model_id=None,
            operation="EVIDENCE_FETCH",
            request_id=None,
            input_bytes=None,
            input_seconds=None,
            estimated_cost_usd=0.0,
            status="SUCCESS",
            receipt={
                "evidence_id": evidence_id,
                "content_sha256": receipt.content_sha256,
                "response_bytes": receipt.response_bytes,
                "content_type": receipt.content_type,
                "from_cache": receipt.from_cache,
                "authoritative": receipt.authoritative,
                "retrieval_method": retrieval_method,
                "retrieval_version": retrieval_version,
            },
            request_key=f"{source_id}:{receipt.content_sha256}",
            ledger_scope={"claim_id": claim_id},
        )
    def persist_evidence_observation(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        evidence_id = str(job.payload.get("evidence_id") or "").strip()
        observation_type = str(
            job.payload.get("observation_type") or ""
        ).strip()
        extraction_method = str(
            job.payload.get("extraction_method") or ""
        ).strip()
        extraction_version = str(
            job.payload.get("extraction_version") or ""
        ).strip()
        if not evidence_id or not observation_type:
            raise BlockedJob("EVIDENCE_OBSERVATION_IDENTITY_MISSING")
        if not extraction_method or not extraction_version:
            raise BlockedJob("EVIDENCE_OBSERVATION_EXTRACTOR_MISSING")
        value_numeric = job.payload.get("value_numeric")
        value_text = job.payload.get("value_text")
        if value_numeric is None and value_text is None:
            raise BlockedJob("EVIDENCE_OBSERVATION_VALUE_MISSING")
        try:
            numeric = None if value_numeric is None else float(value_numeric)
        except (TypeError, ValueError) as exc:
            raise BlockedJob("EVIDENCE_OBSERVATION_NUMERIC_INVALID") from exc
        dimensions = job.payload.get("dimensions") or {}
        source_pointer = job.payload.get("source_pointer") or {}
        if not isinstance(dimensions, dict) or not isinstance(source_pointer, dict):
            raise BlockedJob("EVIDENCE_OBSERVATION_POINTER_INVALID")
        observation_id = deterministic_evidence_observation_id(
            evidence_id=evidence_id,
            observation_type=observation_type,
            metric=str(job.payload.get("metric") or "").strip() or None,
            value_numeric=numeric,
            value_text=(
                str(value_text).strip() if value_text is not None else None
            ),
            unit=str(job.payload.get("unit") or "").strip() or None,
            reference_period=(
                str(job.payload.get("reference_period") or "").strip() or None
            ),
            dimensions=dimensions,
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            source_pointer=source_pointer,
        )
        self.store.insert_evidence_observation(
            observation_id=observation_id,
            evidence_id=evidence_id,
            observation_type=observation_type,
            metric=str(job.payload.get("metric") or "").strip() or None,
            value_numeric=numeric,
            value_text=(
                str(value_text).strip() if value_text is not None else None
            ),
            unit=str(job.payload.get("unit") or "").strip() or None,
            reference_period=(
                str(job.payload.get("reference_period") or "").strip() or None
            ),
            dimensions=dimensions,
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            source_pointer=source_pointer,
            # Extraction and approval are deliberately separate actions.
            status="CANDIDATE",
            metadata={
                "job_id": job.job_id,
                "content_id": content.content_id,
            },
        )
