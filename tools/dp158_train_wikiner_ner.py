"""Train an opt-in Italian spaCy NER from pinned CC BY 4.0 WikiNER data.

The resulting model is local and provisional until independent license review.
No model weights, passage contents or predictions are uploaded by this tool.
"""

from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import random
import re
from pathlib import Path


# Figshare article 5462500, version 1, file 9446344 (it/wp3).
WIKINER_SHA256 = "d702670de515508b7b3341e3e088c9efd882c3647be6930b39f26a920dc4df69"
WIKINER_SOURCE = "https://doi.org/10.6084/m9.figshare.5462500.v1"
WIKINER_REVISION = "figshare-5462500-v1-it-wp3"
def verify_archive(path: Path, expected_sha256: str = WIKINER_SHA256) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1048576), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("WIKINER_ARCHIVE_DIGEST_MISMATCH")


def parse_wikiner_sentence(line: str) -> tuple[str, tuple[tuple[int, int, str], ...]]:
    """Convert WikiNER IOB1 tokens to nonoverlapping character-offset entities."""
    tokens: list[str] = []
    entities: list[tuple[int, int, str]] = []
    active: str | None = None
    start = 0
    cursor = 0
    for field in line.split():
        try:
            token, _, tag = field.rsplit("|", 2)
        except ValueError as exc:
            raise ValueError("WIKINER_ROW_MALFORMED") from exc
        if not token:
            raise ValueError("WIKINER_ROW_MALFORMED")
        kind = tag[2:] if re.fullmatch(r"[BI]-(?:PER|ORG|LOC)", tag) else None
        if active is not None and (kind != active or tag.startswith("B-")):
            entities.append((start, cursor - 1, active))
            active = None
        if kind is not None and active is None:
            start, active = cursor, kind
        tokens.append(token)
        cursor += len(token) + 1
    if active is not None:
        entities.append((start, cursor - 1, active))
    return " ".join(tokens), tuple(entities)


def collect_examples(path: Path, *, count: int, seed: int) -> list[tuple[str, tuple]]:
    """Deterministic reservoir; no training corpus copied to the output model."""
    selected: list[tuple[str, tuple]] = []
    rng = random.Random(seed)
    eligible = 0
    with bz2.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            if len(line) > 8000 or not line.strip():
                continue
            try:
                text, entities = parse_wikiner_sentence(line)
            except ValueError:
                continue
            if not entities or len(text) > 1600:
                continue
            eligible += 1
            if len(selected) < count:
                selected.append((text, entities))
            else:
                index = rng.randrange(eligible)
                if index < count:
                    selected[index] = (text, entities)
    if len(selected) < count:
        raise ValueError("WIKINER_INSUFFICIENT_SAMPLES")
    rng.shuffle(selected)
    return selected


def train_model(archive: Path, target: Path, *, examples: int, epochs: int) -> dict:
    verify_archive(archive)
    if examples < 150 or epochs < 1 or target.exists():
        raise ValueError("WIKINER_TRAINING_ARGUMENT_INVALID")
    import spacy
    from spacy.training import Example

    spacy.util.fix_random_seed(158)
    records = collect_examples(archive, count=examples, seed=158)
    holdout_size = max(30, examples // 10)
    holdout, train_records = records[:holdout_size], records[holdout_size:]
    nlp = spacy.blank("it")
    nlp.add_pipe("ner")
    nlp.meta.update({
        "name": "dp158_wikiner_it_ner",
        "version": "0.1.0",
        "license": "Apache-2.0",
        "tokenizer_policy": "blank-it",
        "description": "Italian spaCy NER trained from WikiNER wp3 CC BY 4.0",
        "sources": [WIKINER_SOURCE],
    })

    def make_example(row: tuple) -> Example:
        text, spans = row
        return Example.from_dict(nlp.make_doc(text), {"entities": list(spans)})

    rng = random.Random(158)
    optimizer = nlp.initialize(get_examples=lambda: (make_example(r) for r in train_records))
    for epoch in range(epochs):
        rng.shuffle(train_records)
        losses: dict[str, float] = {}
        for offset in range(0, len(train_records), 16):
            nlp.update(
                [make_example(r) for r in train_records[offset:offset + 16]],
                sgd=optimizer, drop=0.25, losses=losses,
            )
        print(f"epoch={epoch + 1} examples={len(train_records)} ner_loss={losses.get('ner', 0):.2f}")

    # Holdout is only a same-source diagnostic, never a claim of editorial quality.
    tp = fp = fn = 0
    for text, gold in holdout:
        predicted = {(e.start_char, e.end_char, e.label_) for e in nlp(text).ents}
        expected = set(gold)
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    target.parent.mkdir(parents=True, exist_ok=True)
    # The tokenizer is the untrained spaCy Italian factory tokenizer: rebuild
    # it on load instead of serializing platform-sensitive special rule hashes.
    nlp.to_disk(target, exclude=["tokenizer"])
    reloaded = spacy.load(target, exclude=["tokenizer"])
    manifest = {
        "source_url": WIKINER_SOURCE,
        "revision": WIKINER_REVISION,
        "license_id": "Apache-2.0",
        "training_data_license": "CC-BY-4.0",
        "training_data_sha256": WIKINER_SHA256,
        "pipeline_sha256": hashlib.sha256(reloaded.to_bytes()).hexdigest(),
        "tokenizer_policy": "blank-it",
        "spacy_version": spacy.__version__,
        "train_examples": len(train_records),
        "holdout_examples": len(holdout),
        "epochs": epochs,
        "holdout_exact_tp_fp_fn": [tp, fp, fn],
        "license_review": "PENDING_INDEPENDENT_CHECK_AND_APPROVAL",
    }
    (target / "dp158-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--examples", type=int, default=4000)
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(train_model(
        args.archive, args.output, examples=args.examples, epochs=args.epochs
    ), sort_keys=True))


if __name__ == "__main__":
    main()
