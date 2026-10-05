from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


RESOLVING_RELATIONS = frozenset(
    {
        "REPUBLICATION",
        "SYNDICATION",
        "QUOTATION",
        "PRESS_RELEASE_DERIVED",
    }
)


@dataclass(frozen=True)
class DerivationEdge:
    edge_id: str
    family_id: str
    derived_content_id: str
    origin_content_id: str
    relation_type: str
    status: str = "CANDIDATE"

    def __post_init__(self) -> None:
        for name in (
            "edge_id",
            "family_id",
            "derived_content_id",
            "origin_content_id",
            "relation_type",
            "status",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"DERIVATION_EDGE_{name.upper()}_REQUIRED")
        if self.derived_content_id == self.origin_content_id:
            raise ValueError("DERIVATION_EDGE_SELF_REFUSED")


@dataclass(frozen=True)
class OriginalSourceResolution:
    content_id: str
    status: str
    root_content_id: str | None
    path_content_ids: tuple[str, ...]
    path_edge_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.status in {"SELF_ORIGINAL", "RESOLVED"}


def _edge_from_mapping(value: Mapping[str, Any] | DerivationEdge) -> DerivationEdge:
    if isinstance(value, DerivationEdge):
        return value
    return DerivationEdge(
        edge_id=str(value.get("id") or value.get("edge_id") or ""),
        family_id=str(value.get("family_id") or ""),
        derived_content_id=str(value.get("derived_content_id") or ""),
        origin_content_id=str(value.get("origin_content_id") or ""),
        relation_type=str(value.get("relation_type") or ""),
        status=str(value.get("status") or "CANDIDATE"),
    )


def resolve_original_source(
    content_id: str,
    edges: Iterable[Mapping[str, Any] | DerivationEdge],
    *,
    expected_family_id: str | None = None,
    family_root_content_id: str | None = None,
) -> OriginalSourceResolution:
    """Resolve an approved derivation chain to its original/root Content.

    Only already-approved derivation edges participate. The resolver never turns
    lexical/model similarity into provenance authority. Ambiguous roots, cycles,
    unknown-derivation-only paths, or an expected family root that cannot be reached
    fail closed.
    """

    start = str(content_id or "").strip()
    if not start:
        raise ValueError("ORIGINAL_SOURCE_CONTENT_REQUIRED")
    family_id = str(expected_family_id or "").strip() or None
    expected_root = str(family_root_content_id or "").strip() or None

    approved = []
    for raw in edges:
        edge = _edge_from_mapping(raw)
        if edge.status != "APPROVED":
            continue
        if family_id is not None and edge.family_id != family_id:
            continue
        approved.append(edge)

    by_derived: dict[str, list[DerivationEdge]] = {}
    for edge in approved:
        by_derived.setdefault(edge.derived_content_id, []).append(edge)

    current = start
    content_path = [start]
    edge_path: list[str] = []
    seen = {start}

    if expected_root == start:
        return OriginalSourceResolution(
            content_id=start,
            status="SELF_ORIGINAL",
            root_content_id=start,
            path_content_ids=(start,),
            path_edge_ids=(),
        )

    while True:
        candidates = by_derived.get(current, [])
        resolving = [e for e in candidates if e.relation_type in RESOLVING_RELATIONS]

        if not resolving:
            if candidates:
                return OriginalSourceResolution(
                    content_id=start,
                    status="UNRESOLVED",
                    root_content_id=None,
                    path_content_ids=tuple(content_path),
                    path_edge_ids=tuple(edge_path),
                    blockers=("UNKNOWN_DERIVATION_RELATION",),
                )
            if expected_root is not None and current != expected_root:
                return OriginalSourceResolution(
                    content_id=start,
                    status="UNRESOLVED",
                    root_content_id=None,
                    path_content_ids=tuple(content_path),
                    path_edge_ids=tuple(edge_path),
                    blockers=("EXPECTED_ROOT_NOT_REACHED",),
                )
            return OriginalSourceResolution(
                content_id=start,
                status="SELF_ORIGINAL" if current == start else "RESOLVED",
                root_content_id=current,
                path_content_ids=tuple(content_path),
                path_edge_ids=tuple(edge_path),
            )

        origins = {edge.origin_content_id for edge in resolving}
        if len(origins) != 1:
            return OriginalSourceResolution(
                content_id=start,
                status="UNRESOLVED",
                root_content_id=None,
                path_content_ids=tuple(content_path),
                path_edge_ids=tuple(edge_path),
                blockers=("CONFLICTING_APPROVED_ORIGINS",),
            )

        origin = next(iter(origins))
        selected = sorted(
            (edge for edge in resolving if edge.origin_content_id == origin),
            key=lambda edge: (edge.relation_type, edge.edge_id),
        )[0]

        if origin in seen:
            return OriginalSourceResolution(
                content_id=start,
                status="UNRESOLVED",
                root_content_id=None,
                path_content_ids=tuple(content_path + [origin]),
                path_edge_ids=tuple(edge_path + [selected.edge_id]),
                blockers=("DERIVATION_CYCLE",),
            )

        edge_path.append(selected.edge_id)
        content_path.append(origin)
        seen.add(origin)
        current = origin

        if expected_root is not None and current == expected_root:
            return OriginalSourceResolution(
                content_id=start,
                status="RESOLVED",
                root_content_id=current,
                path_content_ids=tuple(content_path),
                path_edge_ids=tuple(edge_path),
            )


def resolve_reviewed_original_source(
    content_id: str,
    *,
    families: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any] | DerivationEdge],
) -> OriginalSourceResolution:
    """Resolve only when an approved derivation family establishes the root."""

    start = str(content_id or "").strip()
    if not start:
        raise ValueError("ORIGINAL_SOURCE_CONTENT_REQUIRED")
    approved_families = [
        dict(row)
        for row in families
        if str(row.get("status") or "") == "APPROVED"
    ]
    if not approved_families:
        return OriginalSourceResolution(
            content_id=start,
            status="UNRESOLVED",
            root_content_id=None,
            path_content_ids=(start,),
            path_edge_ids=(),
            blockers=("NO_APPROVED_DERIVATION_FAMILY",),
        )
    roots = {
        str(row.get("root_content_id") or "").strip()
        for row in approved_families
        if str(row.get("root_content_id") or "").strip()
    }
    if len(roots) != 1:
        return OriginalSourceResolution(
            content_id=start,
            status="UNRESOLVED",
            root_content_id=None,
            path_content_ids=(start,),
            path_edge_ids=(),
            blockers=("CONFLICTING_APPROVED_FAMILY_ROOTS",),
        )
    root = next(iter(roots))
    if start == root:
        return OriginalSourceResolution(
            content_id=start,
            status="SELF_ORIGINAL",
            root_content_id=root,
            path_content_ids=(start,),
            path_edge_ids=(),
        )
    return resolve_original_source(
        start,
        edges,
        family_root_content_id=root,
    )


__all__ = [
    "DerivationEdge",
    "OriginalSourceResolution",
    "RESOLVING_RELATIONS",
    "resolve_original_source",
    "resolve_reviewed_original_source",
]
