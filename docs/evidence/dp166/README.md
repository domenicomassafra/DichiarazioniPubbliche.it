# #166 — stato verificato dell'adapter pyannote e cosa manca davvero (23/10/2026)

Questa consegna integra il codice opt-in di #166 e #231 su `main` e chiude la
parte verificabile sui computer raggiungibili. Il benchmark reale **non** è
eseguibile oggi: dipende da tre gesti che nessun agente può fare al posto
dell'owner. Qui c'è la prova di cosa è verificato, cosa no e dove è tracciato.

## Cosa è integrato e provato

- `diarization_candidate_adapter.py`: adapter opzionale con envelope di
  autorizzazione obbligatorio — decisione DP-208 `GO`/`GO_BOUNDED` con ricevuta e
  hash, `reviewer_ref`, hash dei pesi e della loro licenza, hash del file WAV,
  diritti `STORE_BODY` + `ASR_MEDIA` sulla fonte specifica, budget di durata,
  tempo, RSS e cache. Senza tutti questi riferimenti non chiama il modello.
- `diarization_candidate_process.py`: esecuzione in un interprete separato con
  `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_CORE=0`, `RLIMIT_FSIZE`, timeout esterno,
  kill del process group, `bubblewrap --unshare-net` sul Linux e output JSON
  anonimo limitato a 96 KiB. Il server non modifica i propri resource limit.
- `diarization_candidate_benchmark.py`: DER/missed/false alarm/confusion/F1 con
  collar 250 ms e verdetti bloccanti.
- Solo etichette `TURN_00`, `TURN_01`: nessuna identità biometrica, nessuna
  `Person`, nessun embedding, nessuna pubblicazione.

Test eseguiti su **Omarchy** (Python 3.14.8), senza pesi, senza audio reale e
senza rete verso i modelli:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest \
  tests.test_dp166_postrun_integrity tests.test_diarization_candidate_adapter \
  tests.test_diarization_benchmark tests.test_speaker_runtime
```

`Ran 51 tests, OK`, ripetuto due volte per stabilità. Suite completa
`unittest discover -s tests` → `Ran 3782, OK (skipped=113)`, exit 0, più
`compileall`, benchmark **5/5**, contributor acceptance, repository contract.

### Correzione di test trovata eseguendo su un host lento

`test_memory_hog_is_bounded_in_child_only` usava `max_elapsed_ms=800`: il figlio
importa il modulo di test prima di allocare, quindi su un host carico scadeva il
wall deadline (`ENGINE_TIMEOUT`) invece del limite di memoria
(`ENGINE_FAILED_OR_LIMIT`). La conteninzione era corretta, la diagnosi no. La
scadenza è ora 5000 ms: il limite di memoria vince, e il test verifica la
proprietà giusta (conteninzione nel figlio, RLIMIT del padre invariati).

## Cosa non è provato e perché (non dipende dagli agenti)

1. **Pesi pyannote.** La pipeline `pyannote/speaker-diarization-community-1` è
   CC-BY-4.0 con **accesso gated**: serve accettare i termini con un account
   Hugging Face e fornire una credenziale. Nel catalogo `secret` non esiste alcun
   token Hugging Face. Senza pesi non esiste inferenza.
2. **Audio reale a due parlanti.** Serve un file italiano con due parlanti e
   overlap, con diritto specifico corrente `STORE_BODY` + `ASR_MEDIA`, hash e
   retention dichiarati. Nessuna fonte autorizzata con questi diritti è
   disponibile oggi; il registro privato dei diritti è vuoto.
3. **Decisione DP-208.** #37 è OPEN: senza `GO`/`GO_BOUNDED` registrato
   l'adapter resta `POLICY_HOLD` per contratto, e non è un blocco tecnico
   aggirabile.

Questi tre punti sono registrati nella issue **Prove personali** del repository e
nella checklist [controlcenter#484](https://github.com/domenicomassafra/controlcenter/issues/484).

## Riuso e licenze

`pyannote.audio` 4.0.7 (MIT) e `notch-up/diarize` 0.1.2 (Apache-2.0) sono
documentati in `docs/donors/pyannote-diarization.md`; i pesi hanno licenza
separata (CC-BY-4.0, gated). Nessun codice di terze parti è stato copiato o
modificato, nessun peso scaricato, nessun provider a pagamento interrogato.
