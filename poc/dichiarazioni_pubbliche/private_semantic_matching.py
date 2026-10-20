"""DP-157: private, bounded semantic hints; deterministic matching is authority.

No stored vectors, model download, database writes or public outputs. The only
runtime backend is an opt-in isolated MiniPC process loading local verified
Sentence Transformers weights. A missing provider or receipt fails closed.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from dichiarazioni_pubbliche.candidate_matching import MatchingInput, rank_candidate_matches
from dichiarazioni_pubbliche.proposition_clustering import normalize_proposition


ADAPTER_VERSION = "dp157-private-semantic-hold-v1"
DONOR_VERSION = "6.1.0"
MIN_SIMILARITY = 0.82
MAX_TARGETS = 32
MAX_CHARS = 400
MAX_MODEL_BYTES = 384 * 1024 * 1024
MAX_FILES = 128
MAX_DIMENSIONS = 1024
MAX_SECONDS = 40
MAX_ADDRESS_SPACE_BYTES = 4 * 1024 * 1024 * 1024
_HASH = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_NEGATION = frozenset({"non", "no", "mai", "nessuno", "nessuna", "nessun", "senza", "ne"})
_NUMBER = re.compile(r"\b\d+(?:[,.]\d+)?\b")
_LICENSES = frozenset({"Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause"})
_ALLOWED_FILE_EXTENSIONS = frozenset({".json", ".txt", ".model", ".vocab", ".safetensors", ".md"})


@dataclass(frozen=True)
class SemanticHint:
    target_type: str
    target_id: str
    similarity: float
    match_class: str = "UNCERTAIN"
    disposition: str = "HOLD"
    method: str = "MODEL_SUGGESTION"


@dataclass(frozen=True)
class SemanticHintRun:
    state: str
    reason: str
    hints: tuple[SemanticHint, ...] = ()
    adapter_version: str = ADAPTER_VERSION
    model_id: str | None = None
    revision: str | None = None
    receipt_sha256: str | None = None


def _gate_reason(candidate: MatchingInput, target: MatchingInput) -> str | None:
    left, right = candidate.proposition, target.proposition
    if (left.member_type, left.member_id) == (right.member_type, right.member_id):
        return "SELF_MATCH"
    if normalize_proposition(left.normalized_text) == normalize_proposition(right.normalized_text):
        return "DETERMINISTIC_EXACT"
    if not candidate.claim_type or candidate.claim_type != target.claim_type:
        return "CLAIM_TYPE_MISSING_OR_DIFFERENT"
    if (not candidate.temporal_scope or not target.temporal_scope
            or candidate.temporal_scope != target.temporal_scope):
        return "TEMPORAL_SCOPE_MISSING_OR_DIFFERENT"
    if left.entity_keys and right.entity_keys and set(left.entity_keys) != set(right.entity_keys):
        return "IDENTITY_DIFFERENT"
    if (bool(left.entity_keys) != bool(right.entity_keys)):
        return "IDENTITY_UNVERIFIED"
    if (_NUMBER.findall(left.normalized_text) != _NUMBER.findall(right.normalized_text)):
        return "NUMERIC_SCOPE_DIFFERENT"
    left_tokens = normalize_proposition(left.normalized_text).split()
    right_tokens = normalize_proposition(right.normalized_text).split()
    if ([token for token in left_tokens if token in _NEGATION]
            != [token for token in right_tokens if token in _NEGATION]):
        return "NEGATION_DIFFERENT"
    if (any(c in left.normalized_text for c in ('"', "«", "»", "“", "”"))
            != any(c in right.normalized_text for c in ('"', "«", "»", "“", "”"))):
        return "QUOTATION_DIFFERENT"
    return None


def _cosine(a: Sequence[float], b: Sequence[float]) -> float | None:
    if not a or len(a) != len(b) or len(a) > MAX_DIMENSIONS:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (*a, *b)):
        return None
    try:
        # SentenceTransformer.encode(normalize_embeddings=True) returns values
        # in [-1, 1]; reject corrupted or unnormalized model output.
        if any(abs(v) > 1.000001 for v in (*a, *b)):
            return None
        if any(not math.isfinite(v) for v in (*a, *b)):
            return None
        norm_a = math.hypot(*a)
        norm_b = math.hypot(*b)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(norm_a) or not math.isfinite(norm_b) or norm_a < 1e-8 or norm_b < 1e-8:
        return None
    # Normalize first: finite embedding elements can overflow their dot product.
    similarity = math.fsum((x / norm_a) * (y / norm_b) for x, y in zip(a, b))
    if not math.isfinite(similarity):
        return None
    return max(-1.0, min(1.0, similarity))


def hints_from_vectors(
    candidate: MatchingInput,
    targets: Sequence[MatchingInput],
    vectors: Sequence[Sequence[float]],
) -> tuple[SemanticHint, ...]:
    """Pure testable seam: mock embeddings never acquire matching authority."""
    if not 1 <= len(targets) <= MAX_TARGETS or len(vectors) != len(targets) + 1:
        return ()
    if any(len(item.proposition.normalized_text) > MAX_CHARS for item in (candidate, *targets)):
        return ()
    baseline = rank_candidate_matches(candidate, targets)
    by_id = {(row.target.proposition.member_type, row.target.proposition.member_id): row
             for row in baseline}
    output: list[SemanticHint] = []
    for target, vector in zip(targets, vectors[1:]):
        deterministic = by_id.get((target.proposition.member_type, target.proposition.member_id))
        if (deterministic is None or deterministic.disposition == "PROPOSE_CLUSTER"
                or _gate_reason(candidate, target) is not None):
            continue
        similarity = _cosine(vectors[0], vector)
        if similarity is not None and similarity >= MIN_SIMILARITY:
            output.append(SemanticHint(target.proposition.member_type, target.proposition.member_id,
                                       round(similarity, 6)))
    return tuple(sorted(output, key=lambda row: (-row.similarity, row.target_type, row.target_id)))


def _verified_receipt(manifest_path: str) -> tuple[dict[str, Any], str]:
    """Verify EVERY local model file and its reviewed license, without fetching."""
    path = Path(manifest_path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("MODEL_RECEIPT_INVALID")
    data = path.read_bytes()
    receipt = json.loads(data)
    if not isinstance(receipt, dict):
        raise ValueError("MODEL_RECEIPT_INVALID")
    if (not isinstance(receipt.get("model_id"), str) or not receipt["model_id"]
            or not isinstance(receipt.get("revision"), str)
            or not _COMMIT.fullmatch(receipt["revision"])
            or receipt.get("license_spdx") not in _LICENSES
            or receipt.get("license_reviewed") is not True
            or not isinstance(receipt.get("license_source_url"), str)
            or not receipt["license_source_url"].startswith("https://")
            or not isinstance(receipt.get("model_dir"), str)):
        raise ValueError("MODEL_LICENSE_OR_REVISION_BLOCKED")
    root = Path(receipt["model_dir"])
    files = receipt.get("files")
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or not isinstance(files, dict) or not 2 <= len(files) <= MAX_FILES
            or "LICENSE" not in files or not any(k.endswith(".safetensors") for k in files)):
        raise ValueError("MODEL_FILES_BLOCKED")
    declared: set[str] = set()
    total = 0
    for name, digest in files.items():
        if (not isinstance(name, str) or not isinstance(digest, str)
                or not _HASH.fullmatch(digest) or name.startswith("/") or "\\" in name
                or any(part in ("", ".", "..") for part in name.split("/"))
                or Path(name).suffix not in _ALLOWED_FILE_EXTENSIONS and name != "LICENSE"):
            raise ValueError("MODEL_MANIFEST_PATH_OR_DIGEST_INVALID")
        candidate = root / name
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("MODEL_FILE_MISSING_OR_SYMLINK")
        size = candidate.stat().st_size
        total += size
        if total > MAX_MODEL_BYTES:
            raise ValueError("MODEL_MEMORY_BUDGET_EXCEEDED")
        hasher = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        if hasher.hexdigest() != digest:
            raise ValueError("MODEL_SHA256_MISMATCH")
        declared.add(name)
    actual = set()
    for folder, dirs, filenames in os.walk(root, followlinks=False):
        for dirname in dirs:
            if (Path(folder) / dirname).is_symlink():
                raise ValueError("MODEL_DIRECTORY_SYMLINK")
        for filename in filenames:
            actual.add((Path(folder) / filename).relative_to(root).as_posix())
    if actual != declared:
        raise ValueError("MODEL_FILE_INVENTORY_MISMATCH")
    return receipt, hashlib.sha256(data).hexdigest()


def _limits() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE_BYTES, MAX_ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_SECONDS, MAX_SECONDS))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _encode_local(manifest_path: str, texts: Sequence[str]) -> list[list[float]]:
    receipt, _ = _verified_receipt(manifest_path)
    if importlib.metadata.version("sentence-transformers") != DONOR_VERSION:
        raise ValueError("SENTENCE_TRANSFORMERS_VERSION_MISMATCH")
    # Offline mode must be in effect BEFORE importing the transformers stack.
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_DATASETS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
                       "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(receipt["model_dir"], device="cpu", local_files_only=True,
                                trust_remote_code=False, backend="torch")
    max_tokens = min(int(model.max_seq_length), 128)
    if max_tokens < 2:
        raise ValueError("SEMANTIC_TOKEN_BUDGET_INVALID")
    # SentenceTransformers silently truncates to max_seq_length. A 400-char
    # Italian input can still exceed 128 wordpieces; refuse that whole batch
    # rather than suggest a match using an embedding missing its final words.
    for text in texts:
        try:
            token_ids = model.tokenizer(text, truncation=False,
                                        add_special_tokens=True)["input_ids"]
        except (AttributeError, KeyError, TypeError) as exc:
            raise ValueError("SEMANTIC_TOKEN_COUNT_UNAVAILABLE") from exc
        if not isinstance(token_ids, (list, tuple)) or not 1 <= len(token_ids) <= max_tokens:
            raise ValueError("SEMANTIC_TOKEN_BUDGET_EXCEEDED")
    model.max_seq_length = max_tokens
    vectors = model.encode(list(texts), batch_size=8, convert_to_numpy=True,
                           normalize_embeddings=True, show_progress_bar=False, device="cpu")
    return [row.tolist() for row in vectors]


def _worker() -> None:
    # An isolated child owns the heavyweight runtime and its strict resource caps.
    if os.getenv("DP_PRIVATE_SEMANTIC_ENABLED") != "1":
        raise ValueError("EXPLICIT_OPT_IN_REQUIRED")
    payload = json.loads(sys.stdin.read(20000))
    texts = payload["texts"]
    if (platform.system() != "Linux" or platform.node() != "udodo"
            or not isinstance(texts, list) or not 2 <= len(texts) <= MAX_TARGETS + 1
            or any(not isinstance(s, str) or not s or len(s) > MAX_CHARS for s in texts)):
        raise ValueError("SEMANTIC_WORKER_INPUT_BLOCKED")
    print(json.dumps(_encode_local(payload["manifest"], texts), separators=(",", ":")))


def run_private_semantic_matching(candidate: MatchingInput, targets: Sequence[MatchingInput],
                                  *, manifest_path: str | None = None) -> SemanticHintRun:
    if os.getenv("DP_PRIVATE_SEMANTIC_ENABLED") != "1":
        return SemanticHintRun("DISABLED", "EXPLICIT_OPT_IN_REQUIRED")
    if platform.system() != "Linux" or platform.node() != "udodo":
        return SemanticHintRun("BLOCKED", "MINIPC_ONLY")
    if not 1 <= len(targets) <= MAX_TARGETS:
        return SemanticHintRun("BLOCKED", "TARGET_BUDGET_EXCEEDED")
    inputs = (candidate, *targets)
    if any(len(item.proposition.normalized_text) > MAX_CHARS for item in inputs):
        return SemanticHintRun("BLOCKED", "TEXT_BUDGET_EXCEEDED")
    path = manifest_path or os.getenv("DP_SEMANTIC_MODEL_RECEIPT")
    if not path:
        return SemanticHintRun("BLOCKED", "MODEL_RECEIPT_REQUIRED")
    try:
        receipt, digest = _verified_receipt(path)
        if importlib.metadata.version("sentence-transformers") != DONOR_VERSION:
            return SemanticHintRun("BLOCKED", "PROVIDER_VERSION_MISMATCH")
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError,
            importlib.metadata.PackageNotFoundError) as exc:
        return SemanticHintRun("BLOCKED", str(exc) or type(exc).__name__)
    texts = [item.proposition.normalized_text for item in inputs]
    try:
        # Never pass the service's credentials or unrelated provider variables
        # to the optional third-party model process.
        child_env = {key: os.environ[key] for key in
                     ("PATH", "HOME", "VIRTUAL_ENV", "PYTHONPATH", "LANG", "LC_ALL", "TMPDIR")
                     if key in os.environ}
        child_env.update({"DP_PRIVATE_SEMANTIC_ENABLED": "1", "HF_HUB_OFFLINE": "1",
                          "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                          "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "1",
                          "MKL_NUM_THREADS": "1"})
        output = subprocess.run(
            [sys.executable, "-m", "dichiarazioni_pubbliche.private_semantic_matching", "--worker"],
            input=json.dumps({"manifest": path, "texts": texts}),
            text=True, capture_output=True, check=False,
            timeout=MAX_SECONDS + 5, preexec_fn=_limits,
            env=child_env,
        )
        if output.returncode != 0 or len(output.stdout) > 1_000_000:
            return SemanticHintRun("BLOCKED", "MODEL_WORKER_FAILED")
        vectors = json.loads(output.stdout)
        hints = hints_from_vectors(candidate, targets, vectors)
        return SemanticHintRun("HOLD", "PRIVATE_REVIEW_ONLY", hints,
                               model_id=receipt["model_id"], revision=receipt["revision"],
                               receipt_sha256=digest)
    except (OSError, ValueError, subprocess.SubprocessError, TypeError, json.JSONDecodeError):
        return SemanticHintRun("BLOCKED", "MODEL_WORKER_UNAVAILABLE")


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
