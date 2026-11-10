# DichiarazioniPubbliche.it — istruzioni del repository

Leggere prima `~/.dstack/contracts/shared-root/AGENTS.md` e la issue GitHub assegnata con tutti i commenti. GitHub Issues è la fonte per criteri e stato; `PLAN.md` e `docs/tickets/DP-*.md` documentano specifiche storiche. Non aggiornare i loro stati. Seguire anche `PRODUCT.md`, `CONTEXT.md`, `ARCHITECTURE.md` e gli ADR pertinenti.

## Architettura e ambienti

- Backend Python: `poc/dichiarazioni_pubbliche/`; test: `tests/`; contratti/API: `docs/api/`; configurazione fonti: `config/`.
- Flusso: fonte → acquisizione/trascrizione → statement/claim → evidenze → verifica → revisione → proiezione pubblica.
- PostgreSQL conserva stato operativo e code quando previsto; il web Astro in `web/` legge solo una proiezione esplicitamente approvata.
- Git autorevole: `domenicomassafra/DichiarazioniPubbliche.it`, branch `main`. Lavorare sul Mac Studio in `~/Code/.worktrees/DichiarazioniPubbliche.it-<issue>` da `origin/main`; il checkout condiviso potrebbe contenere WIP di altri.
- Consumer MiniPC: mirror non-Git `/home/udodo/src/DichiarazioniPubbliche.it`; servizio `dichiarazioni-pubbliche-web.service` su `127.0.0.1:18090`. GitHub CI non installa il consumer.

## Comandi di verifica

Toolchain: Python 3.11–3.14 e Node 24. Eseguire `npm ci`, test e build solo sul Mac Studio, sempre tramite `python3 ~/.local/share/controlcenter/resource-guard/workload_launcher.py build -- <comando>`; il MiniPC è riservato a runtime Linux, servizi e verifiche di readback.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest tests.test_repository_contract -v
python3 tools/check_repository_contract.py
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q poc tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_contributor_acceptance.py
cd web && npm run check && DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 npm run build && npm run check:projection-boundary
```

Per ogni modifica eseguire prima i test mirati dell'area, poi i gate pertinenti. Prima del push verificare `git diff --check`. Per pubblicare: verificare il diff e gli eventuali conflitti reali, pushare la PR e rileggere lo SHA remoto; non aggiornare un head pulito e mergeable solo per inseguire `origin/main`. Installare con la procedura candidata → verifica → swap con rollback prevista dal runbook del consumer.

Readback runtime:

```bash
systemctl --user is-active dichiarazioni-pubbliche-web.service
curl -fsS --max-time 5 http://127.0.0.1:18090/api/v1/health
curl -fsS --max-time 10 -o /dev/null -w 'http=%{http_code}\n' https://dichiarazionipubbliche.it/
```

## Confini del prodotto

- Pubblicazione, provenienza, diritti, privacy e review sono gate obbligatori; un output AI resta candidato finché non supera i controlli automatici ripetuti da un agente indipendente.
- Niente punteggi delle persone, identificazione biometrica, profili politici inferiti o contenuti privati esposti nel web.
- Niente proiezione demo in produzione, né modifica di DB live per passare i test.
- **Owner decision 49, 10 November 2026, supersedes the universal review count in the 25 October decision.** Canonical contract: `config/autopublish.v1.json`, sourced from `/Users/domenico/.dstack/docs/evidence/orchestrator-owner-decisions.md`. Automatically publish a verified, publicable record after source, exact quote, public-person attribution, rights/privacy and **one authenticated editorial review**, with no per-record owner GO. Only *genuinely uncertain* records require 2 independent reviews plus a distinct third audit; HOLD them until complete. A decision about the workflow grants no source-specific quotation or GDPR permission. Any revoked permission, challenge or correction immediately fences the public record; independent readback remains required. Physical actions and personal choices belong to #300.
- Riusare implementazioni esistenti e upstream compatibili; registrare licenze e provenienza dei donor.
- Decisioni owner e autorizzazioni specifiche sono nelle issue; non inventare permessi o costi. Il design visivo finale è riservato a un intervento successivo dell'owner.

## LLMs for review and audit

For agent reviews and audits, follow only `~/.dstack/contracts/shared-root/AGENTS.md`. Historical model names and catalog aliases do not prove availability or authorization.

The **product** escalation requirement applies when a specific record has unresolved uncertainty: its 2+1 requires three genuinely different upstream model identities, proven by execution receipts. Ordinary records require one genuine, authenticated editorial review. Multiple accounts, aliases, and tiers of the same model do not count as different models. A code or OmniRoute allowlist does not prove entitlement, quota or permission to execute; without the current witness, HOLD and never POST.

**Owner decision 25 October 2026, DP#300, updated 2 November in #413/#468/#98:** extraction uses only genuinely available, verified Google AI Pro subscription connections through OmniRoute, with a DP key scoped to current connections and no fallback. Stop extraction when subscription quota runs out; no metered calls or alternative providers. Before every POST, the consumer must verify account, model, quota, and blocking of paid routes. General authorization does not replace consumer proof.

## Senato Akoma Ntoso: fonte aperta, sola Discovery privata (owner 24/10/2026)

Per il solo commit `bfac144eb5c54820971bc1020fece11aae56ec90`
di `SenatoDellaRepubblica/AkomaNtosoBulkData`, README/Licenza ufficiali
CC BY 4.0 e blob esatto verificati automaticamente bastano per registrare
`DISCOVER_METADATA` privato e attribuzione; non inventare un attestatore
umano o una nuova firma personale. Usare il registro versionato/revocabile,
le evidenze hash e il perimetro di `docs/ops/dp326-studio-discovery-metadata-rights-20261024.md`.
Questa decisione non concede capture del body, modelli, review o pubblicazione;
fonti differenti continuano a seguire i loro controlli specifici.

## Fonti (decisione owner del 25/10/2026)

Niente «fonti di prova»: ogni fonte è reale. DichiarazioniPubbliche deve raccogliere tutte le dichiarazioni pubbliche reperibili di persone note (politici, attori, cantanti, produttori, influencer, YouTuber, TikToker e simili), senza un limite: più sono, meglio è. Restano fuori le persone comuni, salvo quando parlano in televisione o in un contesto pubblico. Gli agenti scelgono le fonti in autonomia e non chiedono lautorizzazione

## Real sources, rights and usability — owner decision 2026-10-25

- Agents independently select as many **real**, attributable public statements by
  well-known public figures as the task needs. Do not create synthetic source
  material as a substitute for acceptance and do not request a source-by-source
  owner choice or approval. Preserve source-specific identity and timestamps.
- Agents conduct and cite source-specific legal, licensing, copyright and privacy
  reviews, register the permitted uses and current rights evidence, and enforce
  revocation and all existing publication gates. A verified origin alone is not
  a license. Record only physical actions, secrets/password setup, or genuinely
  personal decisions in this repository's "Prove personali" issue (#300) with
  precise instructions; complete the remaining technical work autonomously.
- Reuse existing native acquisition and review tools. For media transcripts,
  prioritize the free instantaneous services ordered by DStack issue #166 when
  that canonical inventory is available, before local transcription; respect
  the approved provider routes and stop conditions.
- Measure operator usability against actual source-linked data. Defer visual
  redesign from issues #84, #324 and #349 until all other issues are finished.
