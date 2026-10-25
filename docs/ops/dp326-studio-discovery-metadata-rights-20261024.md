# DP-417 — current private metadata rights in Discovery Inbox (2026-10-24)

Status: **real MiniPC private metadata Run/Hit acceptance PASS** (one pinned
Senato source). Capture, reviewer actions and publication remain HOLD.
The earlier zero-Run/Hit snapshot below records the *pre-install* baseline.
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

**MiniPC pre-install baseline, 2026-10-24**, through
`tools/dp417_inbox_readback.py --database-url dichiarazioni_pubbliche`:
1 PAUSED Garlasco Collection; 0 Manifest; 0 Run; 0 Hit; 0 current rights
records. This is the historical negative receipt before the owner clarified
that the public CC BY 4.0 licence permits this exact private metadata use.
The final consumer readback is documented below; no paid provider, Capture,
public release, or reviewer decision was authorized by the scope.

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

## Real MiniPC consumer readback and schema repair (24 October 2026)

Mac Studio regression, under the mandatory resource guard and `LC_ALL=C`:
**52/52 PASS** across DP-417/PostgreSQL/Discovery and **4/4 PASS** after the
final explicit source/Collection guards. Before implementation the new test
failed for the missing adapter module (RED); after implementation it passed.
Pinned public Git Trees traversal independently returned the exact XML blob
`bec30c067a1a79e8b377af483cfc4bfb44d13896`. XML body was not fetched
for the Discovery run.

The MiniPC production **private** mirror received exactly three source
files with byte-identical staging comparisons:
`tools/dp326_senato_private_discovery.py`,
`poc/dichiarazioni_pubbliche/studio_discovery_inbox_workflow.py`,
`poc/dichiarazioni_pubbliche/studio_discovery_rights_sql.py`.
Other native registry/Discovery files already matched Mac Studio SHA256.
Preimage of the replaced Inbox file is retained in a private `/tmp` rollback
directory; the other two files had no prior installed version.
The running web/gateway processes were not restarted or republished.

The first invocation wrote one genuine Hit and one HEALTHY Attempt, but
failed to append the ledger receipt because MiniPC still retained the old
`provider_receipt_unknown_cost_check`. After a private full PostgreSQL
custom backup (11 MB, SHA256
`ce6ef74d195baf46452c54dd47a3911b75d307d609f2338cd7882edee6d5b8c8`,
`pg_restore --list` PASS), the **pre-existing native** migration
`db/migrations/20261011-allow-unknown-discovery-ceiling.sql`
(SHA256 `4d47dd0b70d780f51c2d65ade5a38241e26ccce95bfe08f35a1c5896aa347920`)
was applied. The old CHECK condition was removed as specified by that
migration; UNKNOWN liability remains UNKNOWN and separately holds paid
dispatch. The original HEALTHY attempt's immutable operation receipt
`receipt:4b0ebdf692f34cd891957f036452b9477b8118883aee353112261406c08c25db`
was appended through the native Discovery store and its original Run
completed. No duplicate attempt, Hit or fabricated ZERO_COST receipt was
introduced.

The final installed-consumer receipt reports:

- Collection `research:senato-akn-dp326` ACTIVE, original
  `research:garlasco` still PAUSED; **2 Collections total**.
- One Manifest (`discovery-manifest:senato-akn-dp326`, digest
  `90cd84fbb70a02bbc7cb3e3ef5c50ba5717cf2361ba2e246389acd8b747f7788`).
- One Run `discovery-run:senato-akn-dp326` COMPLETED, one HEALTHY Attempt,
  exactly one accepted `NEW_CONTENT` Hit
  `discovery-hit:aa80fde6382b8f1b11ad015a97f0a65d523c6c1adcb124c5d049b364145c23f6`.
- Private CURRENT source-rights record
  `private-rights:dc661314e4e2bb91a140595bd8d2660a355e442165f144c61f8a41feccc63422`,
  `DISCOVER_METADATA` only, CC BY 4.0 with official SHA256/attribution,
  expiry and native revocation checks.
- Real Studio Inbox source metadata rights **true**, replay same Run receipt
  **true**, `action_authorized=false`, `publication_authorized=false`,
  `capture_authorized=false`. Remaining blockers concern Content-level
  capture rights and triage action authority, intentionally outside this
  Discovery acceptance.
- Independent `tools/dp417_inbox_readback.py`: **1/1 completed Run**,
  **1 Hit**, **0 blocked/incomplete Runs**, **0 invalid lineage Hits**.

The held Content rights value remains UNKNOWN: no FETCH, STORE_BODY,
candidate extraction, human review or publication decision has been minted.
Use the private backup and the original Inbox preimage for rollback if the
exact installed consumer fails; rollback of application source is separate
from, and does not require erasing, the authentic persisted Run/Hit.
