# DP-318 / #333 — private same-take relation readback

This read-only diagnostic extends the existing #331 Senate Capture reader.
It compares exactly two explicit speech ordinals from the same pinned,
immutable source. It uses the existing DP-318 scoped Statement relation
evaluator; it writes no Statements, relation candidates or public projection.

Source: Senato della Repubblica, AkomaNtosoBulkData, commit
`bfac144eb5c54820971bc1020fece11aae56ec90`,
`Leg19/Atto00055187/resaula/01457617-ra.akn.xml`,
SHA256 `1cb2b5fc3cbc96701e52f06c34c3ae3cd494eb622aa3f124fb1a93a223e27476`.
The repository declares CC BY 4.0; the Senate legal notice additionally
requires attribution, source integrity and respect for third-party rights:
https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData
https://www.senato.it/guida-al-sito/avviso-legale

On the MiniPC, with the exact CURRENT rights record already created by #357
(including PARSE_TEXT), run:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp331_senato_private_speech_readback.py \
  --database-url dichiarazioni_pubbliche --ordinal 15 --ordinal 19 --compare-relation
```

The reader validates CURRENT rights, immutable Capture bytes and source hash
before parsing, and rechecks the rights after reading. The official source
speaker URI is a **candidate**, not an approved Person binding; the statement
kind, position, proposition and equivalence review are all unverified.
Accordingly the relation must return `HOLD`, zero resolved Persons and
`publication_authority=false`. The two independent source-context bindings
remain inspectable as hashes; no original speech text is emitted.
Neither the private `PARSE_TEXT` grant nor this diagnostic authorizes
`EXTRACT_CANDIDATES`, editorial endorsement or public publication.
For independent same-take/position-change assertions, first obtain verified
speaker attribution, independently reviewed proposition/stance/scope and
current rights for the downstream use, then revalidate the consumer.
