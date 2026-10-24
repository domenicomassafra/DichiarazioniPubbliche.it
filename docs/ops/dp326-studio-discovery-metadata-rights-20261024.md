# DP-417 — current private metadata rights in Discovery Inbox (2026-10-24)

Status: **source implementation; production runtime acceptance HOLD**.
Original product contract: [issue #32](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/32).
Recovery scope: [issue #326](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/326).
The #330 source canary fix was already merged via PR #361 at `218a858a`
and was not edited.

The private Inbox previously returned
`PRIVATE_SOURCE_RIGHTS_REVIEW_NOT_EVALUATED` even when PostgreSQL contained a
single **CURRENT, unsuperseded**, exact Content/source-family/URL rights record
for `DISCOVER_METADATA`. The Inbox now reads the existing append-only
`private_source_rights_record` in its scoped PostgreSQL query. The
`source_metadata_rights_current` boolean becomes true only with one current
leaf, `CLEARED`, a private record with receipt and reviewer, a past review
time, a future explicit expiry, and the exact permitted private metadata use.
An expired, revoked, absent, duplicate, unrelated, or superseded record
cannot make the flag true. The rights flag participates in the Inbox snapshot
hash, so a changed rights decision invalidates a prior selected row.

The response continues to set `action_authorized=false`,
`rights_clearance=false`, `publication_authority=false`, `read_only=true`.
The reviewer authority blocker is retained. This predicate is a scoped
registry observation: it is **not** a legal determination of source rights,
reviewer identity, extraction eligibility, or authority for bulk actions.

Regression uses a disposable Mac Studio PostgreSQL database, the source
family, source ID and exact pinned Senato Akoma Ntoso locator already named by
the #330 canary. Synthetic fixture rights and revocation are **not** an
approval of that real document. The test exercises current rights, replay,
revocation and the authenticated read-only Studio loopback HTTP consumer.
Other existing tests cover Run/Hit deduplication and triage replay.

Independent real source metadata observation on GitHub REST, 2026-10-24:
`SenatoDellaRepubblica/AkomaNtosoBulkData` pinned `README.MD`,
current `bfac144eb5c54820971bc1020fece11aae56ec90`:
Git blob SHA `c10e853289033409f0e230385a0cd23c3f00b33b`;
historical `6995905a8291f7c8135c6d0aab711da326619b08`:
Git blob SHA `8336d96ad4b4f594ed869dd49a816207e8b79270`.
The #330 canary applies version-specific terms; a public URL alone never
becomes a current signed source-use grant.

**Actual MiniPC read-only census, 2026-10-24**, through
`tools/dp417_inbox_readback.py --database-url dichiarazioni_pubbliche`:
1 Collection; 0 Manifest; 0 Run; 0 Hit; 0 completed runs; no runtime
acceptance. Separately `SELECT count(*) FROM private_source_rights_record`
in a `READ ONLY` transaction returned **0**. Thus there is no current
qualified private rights record or persisted real accepted Hit in that
consumer. A permitted real Run/Hit and production acceptance must stay HOLD;
any qualified source decision belongs to [issue #300](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/300).
No provider execution, paid usage, production write or public release is
authorized by this slice.

## Owner decision for this exact official metadata source (24 October 2026)

The Senato AkomaNtosoBulkData repository at commit
`bfac144eb5c54820971bc1020fece11aae56ec90` declares **CC BY 4.0**
in its pinned `README.MD` (SHA256
`cd01c53874c63df20d18ea151b3e5528af329dbc64ee573be4d480368f5a34dc`)
and `LICENSE.MD` (SHA256
`9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411`).
These are source-specific licence evidence, distinct from the CC BY 3.0
notice on the separate dati.senato.it portal. The owner accepts the
automatically verified official grant to DISCOVER_METADATA for one exact
pinned document without inventing a qualified human reviewer or an
additional personal source-use attestation.

`tools/dp326_senato_private_discovery.py` reuses the native
`verify_pinned_official_license`, `attest_licence_use`,
`PrivateRightsRegistryStore`, relevance authority and the standard
Discovery Run/Hit + Studio Inbox readers. It verifies the official
commit/tree/blob through GitHub metadata; no XML body, model, paid provider,
publication or bulk ingestion is involved. The scoped rights record has
`DISCOVER_METADATA` as its **only** permitted use, CC BY 4.0 source and
attribution evidence, a machine-labelled licence-verification provenance,
an expiry and the existing append-only revocation/supersession checks.
The machine label identifies the software check, never a human signature.
This narrow decision does not authorize FETCH, STORE_BODY, a review
decision, candidate extraction or GO-PUBLIC.

The only preexisting consumer Research Collection, `research:garlasco`,
is PAUSED and concerns a different investigation; do not activate or
modify it to perform this source canary. A dedicated, clearly scoped
`research:senato-akn-dp326` Collection holds one pinned metadata Hit.
Replay keeps the original Run/Hit identifiers and private provenance.
The existing private rights and publication gates still refuse
unverified, expired, superseded and unrelated sources.
