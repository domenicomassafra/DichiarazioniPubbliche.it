"""Bounded private NER inference on one independently licensed Senato speech.

Reads an exact-hash public AKN document and a local candidate model. Outputs
offsets and hashes, never speech text, names, a DB record or approved identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_spacy_private import (  # noqa: E402
    ApprovedSpaCyModel, SpaCyItalianPrivateAdapter,
)

SENATO_SHA256 = "1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476"
SENATO_URL = (
    "https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/"
    "bfac144eb5c54820971bc1020fece11aae56ec90/"
    "Leg19/Atto00055187/resaula/01457617-ra.akn.xml"
)
SENATO_BLOB = "bec30c067a1a79e8b377af483cfc4bfb44d13896"


def load_speech(path: Path, ordinal: int) -> str:
    if hashlib.sha256(path.read_bytes()).hexdigest() != SENATO_SHA256:
        raise ValueError("SENATO_SOURCE_DIGEST_MISMATCH")
    speeches = ET.parse(path).getroot().findall(".//{*}speech")
    if not 1 <= ordinal <= len(speeches):
        raise ValueError("SENATO_SPEECH_NOT_FOUND")
    # Transient normalization for this model probe, not a persisted Passage.
    text = " ".join(" ".join(speeches[ordinal - 1].itertext()).split())
    if not text or len(text) > 32000:
        raise ValueError("SENATO_SPEECH_LENGTH_INVALID")
    return text


def run(document: Path, model_dir: Path, ordinal: int) -> dict:
    manifest = json.loads((model_dir / "dp158-manifest.json").read_text("utf-8"))
    if (manifest.get("license_review") != "PENDING_INDEPENDENT_CHECK_AND_APPROVAL"
            or manifest.get("training_data_sha256") !=
            "d702670de515508b7b3341e3e088c9efd882c3647be6930b39f26a920dc4df69"):
        raise ValueError("DP158_PROVISIONAL_MODEL_RECEIPT_INVALID")
    approval = ApprovedSpaCyModel(**{
        field: manifest[field]
        for field in ("source_url", "revision", "license_id", "pipeline_sha256",
                      "tokenizer_policy")
    })
    adapter = SpaCyItalianPrivateAdapter.load(model_dir, approval=approval)
    text = load_speech(document, ordinal)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    entities = adapter.propose(text=text, text_sha256=digest, language="it")
    return {
        "status": "PRIVATE_CANDIDATES_ONLY_LICENSE_REVIEW_PENDING",
        "source_url": SENATO_URL,
        "source_blob": SENATO_BLOB,
        "source_sha256": SENATO_SHA256,
        "source_license": "CC-BY-4.0",
        "source_speech_ordinal": ordinal,
        "passage_sha256": digest,
        "pipeline_sha256": manifest["pipeline_sha256"],
        "entity_count": len(entities),
        "labels": {label: sum(e.label == label for e in entities)
                   for label in ("PER", "ORG", "LOC")},
        "spans": [{"start": e.start_char, "end": e.end_char,
                   "label": e.label, "text_sha256": e.text_sha256}
                  for e in entities[:20]],
        "rights_limit": "NO_DB_COMMIT_NO_IDENTITY_APPROVAL_NO_PUBLICATION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--speech-ordinal", type=int, default=40)
    args = parser.parse_args()
    print(json.dumps(run(args.document, args.model, args.speech_ordinal), sort_keys=True))


if __name__ == "__main__":
    main()
