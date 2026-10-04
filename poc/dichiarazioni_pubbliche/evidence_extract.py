from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any


@dataclass(frozen=True)
class StructuredObservation:
    value: float | int | str
    dimensions: dict[str, str]
    labels: dict[str, str]
    status: str | None
    reference_period: str | None
    unit: str | None


@dataclass(frozen=True)
class NormattivaActHit:
    codice_redazionale: str
    denominazione_atto: str
    numero_atto: str
    data_gu: str
    numero_gu: str
    data_emanazione: str
    titolo_atto: str
    descrizione_atto: str


def _category_positions(dimension: dict[str, Any]) -> tuple[dict[int, str], dict[str, str]]:
    category = dimension.get("category") or {}
    raw_index = category.get("index") or {}
    labels = category.get("label") or {}
    positions: dict[int, str] = {}
    if isinstance(raw_index, dict):
        for code, position in raw_index.items():
            try:
                positions[int(position)] = str(code)
            except (TypeError, ValueError):
                continue
    elif isinstance(raw_index, list):
        positions = {index: str(code) for index, code in enumerate(raw_index)}
    return positions, {str(key): str(value) for key, value in labels.items()}


def _decode_flat_index(index: int, sizes: list[int]) -> list[int]:
    if index < 0:
        raise ValueError("JSONSTAT_NEGATIVE_INDEX")
    coordinates = [0] * len(sizes)
    remaining = index
    for position in range(len(sizes) - 1, -1, -1):
        size = sizes[position]
        if size <= 0:
            raise ValueError("JSONSTAT_INVALID_DIMENSION_SIZE")
        coordinates[position] = remaining % size
        remaining //= size
    if remaining:
        raise ValueError("JSONSTAT_INDEX_OUT_OF_RANGE")
    return coordinates


def extract_jsonstat_observations(
    payload: dict[str, Any],
    *,
    selectors: dict[str, set[str] | list[str] | tuple[str, ...] | str] | None = None,
    max_results: int = 1000,
) -> list[StructuredObservation]:
    if payload.get("class") != "dataset":
        raise ValueError("JSONSTAT_DATASET_REQUIRED")
    dimensions = payload.get("id")
    sizes = payload.get("size")
    dimension_meta = payload.get("dimension")
    values = payload.get("value")
    if not isinstance(dimensions, list) or not isinstance(sizes, list):
        raise ValueError("JSONSTAT_DIMENSION_CONTRACT_INVALID")
    if len(dimensions) != len(sizes):
        raise ValueError("JSONSTAT_DIMENSION_SIZE_MISMATCH")
    if not isinstance(dimension_meta, dict) or not isinstance(values, dict):
        raise ValueError("JSONSTAT_PAYLOAD_INVALID")
    if not 1 <= max_results <= 100_000:
        raise ValueError("JSONSTAT_MAX_RESULTS_INVALID")

    selector_sets: dict[str, set[str]] = {}
    for key, raw in (selectors or {}).items():
        if key not in dimensions:
            raise ValueError(f"JSONSTAT_SELECTOR_UNKNOWN_DIMENSION:{key}")
        values_list = raw if isinstance(raw, (list, tuple, set)) else [raw]
        selector_sets[str(key)] = {str(value) for value in values_list}

    dimension_positions: dict[str, dict[int, str]] = {}
    dimension_labels: dict[str, dict[str, str]] = {}
    for dimension_id in dimensions:
        meta = dimension_meta.get(dimension_id)
        if not isinstance(meta, dict):
            raise ValueError(f"JSONSTAT_DIMENSION_METADATA_MISSING:{dimension_id}")
        positions, labels = _category_positions(meta)
        dimension_positions[str(dimension_id)] = positions
        dimension_labels[str(dimension_id)] = labels

    status_map = payload.get("status") or {}
    output: list[StructuredObservation] = []
    for raw_index, raw_value in values.items():
        try:
            flat_index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise ValueError("JSONSTAT_VALUE_INDEX_INVALID") from exc
        coordinates = _decode_flat_index(flat_index, [int(size) for size in sizes])
        codes: dict[str, str] = {}
        labels: dict[str, str] = {}
        for dimension_id, coordinate in zip(dimensions, coordinates):
            dimension_id = str(dimension_id)
            code = dimension_positions[dimension_id].get(coordinate)
            if code is None:
                raise ValueError(
                    f"JSONSTAT_CATEGORY_POSITION_MISSING:{dimension_id}:{coordinate}"
                )
            codes[dimension_id] = code
            labels[dimension_id] = dimension_labels[dimension_id].get(code, code)
        if any(
            codes.get(dimension_id) not in allowed
            for dimension_id, allowed in selector_sets.items()
        ):
            continue
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, str)):
            raise ValueError("JSONSTAT_VALUE_TYPE_INVALID")
        status = status_map.get(raw_index) if isinstance(status_map, dict) else None
        output.append(
            StructuredObservation(
                value=raw_value,
                dimensions=codes,
                labels=labels,
                status=str(status) if status is not None else None,
                reference_period=codes.get("time"),
                unit=codes.get("unit"),
            )
        )
        if len(output) >= max_results:
            break
    return output


def extract_normattiva_hits(
    payload: dict[str, Any],
    *,
    max_results: int = 100,
) -> list[NormattivaActHit]:
    rows = payload.get("listaAtti")
    if not isinstance(rows, list):
        raise ValueError("NORMATTIVA_LISTA_ATTI_MISSING")
    if not 1 <= max_results <= 1000:
        raise ValueError("NORMATTIVA_MAX_RESULTS_INVALID")
    hits: list[NormattivaActHit] = []
    for row in rows[:max_results]:
        if not isinstance(row, dict):
            raise ValueError("NORMATTIVA_ACT_INVALID")
        code = str(row.get("codiceRedazionale") or "").strip()
        if not code:
            raise ValueError("NORMATTIVA_CODICE_REDazionale_MISSING")
        hits.append(
            NormattivaActHit(
                codice_redazionale=code,
                denominazione_atto=str(row.get("denominazioneAtto") or "").strip(),
                numero_atto=str(
                    row.get("numeroAttoAlfanumerico")
                    or row.get("numeroAtto")
                    or ""
                ).strip(),
                data_gu=str(row.get("dataGUStr") or row.get("dataGU") or "").strip(),
                numero_gu=str(row.get("numeroGU") or "").strip(),
                data_emanazione=str(row.get("dataEmanazione") or "").strip(),
                titolo_atto=str(row.get("titoloAtto") or "").strip(),
                descrizione_atto=str(row.get("descrizioneAtto") or "").strip(),
            )
        )
    return hits


class _VisibleTextParser(HTMLParser):
    def __init__(self, max_characters: int) -> None:
        super().__init__(convert_charrefs=True)
        self.max_characters = max_characters
        self.hidden_depth = 0
        self.parts: list[str] = []
        self.characters = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg", "template"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg", "template"}:
            self.hidden_depth = max(self.hidden_depth - 1, 0)

    def handle_data(self, data: str) -> None:
        if self.hidden_depth:
            return
        value = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if not value:
            return
        projected = self.characters + len(value) + 1
        if projected > self.max_characters:
            remaining = self.max_characters - self.characters
            if remaining > 0:
                self.parts.append(value[:remaining])
                self.characters += min(len(value), remaining)
            return
        self.parts.append(value)
        self.characters = projected


def extract_visible_html_text(
    body: bytes,
    *,
    encoding: str = "utf-8",
    max_characters: int = 2_000_000,
) -> str:
    if not 1 <= max_characters <= 10_000_000:
        raise ValueError("HTML_TEXT_LIMIT_INVALID")
    text = body.decode(encoding, errors="replace")
    parser = _VisibleTextParser(max_characters)
    parser.feed(text)
    parser.close()
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def exact_phrase_excerpt(
    text: str,
    phrase: str,
    *,
    context_characters: int = 240,
) -> str | None:
    phrase = re.sub(r"\s+", " ", phrase).strip()
    if not phrase:
        raise ValueError("PHRASE_REQUIRED")
    if len(phrase) > 1000:
        raise ValueError("PHRASE_TOO_LONG")
    if not 0 <= context_characters <= 2000:
        raise ValueError("PHRASE_CONTEXT_INVALID")
    normalized_text = re.sub(r"\s+", " ", text)
    match = re.search(re.escape(phrase), normalized_text, flags=re.IGNORECASE)
    if match is None:
        return None
    start = max(match.start() - context_characters, 0)
    end = min(match.end() + context_characters, len(normalized_text))
    return normalized_text[start:end].strip()
