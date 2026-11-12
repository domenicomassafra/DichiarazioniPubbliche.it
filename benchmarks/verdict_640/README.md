# DP #640 — benchmark di verdetti

`statements.jsonl` contiene 40 dichiarazioni reali (8 per etichetta), datate
settembre–novembre 2026. Ogni record ha parole citate letteralmente, persona,
data, origine e almeno due riferimenti motivati. Alcune etichette descrivono
giudizi editoriali: non sono attestazioni automatiche di verità. Un giudizio
`opinione` non è un'accusa di falsità. I riferimenti a fonti secondarie servono
come interpretazione pubblicata, quelli primari a confrontare il fatto; i
pronostici futuri `non verificabile` rimangono tali alla data del benchmark.

Verifica indirizzi e citazioni presenti nei documenti HTML, scaricando le fonti
(per i PDF controlla la risposta HTTP, senza eseguire riconoscimento del testo):

Controllo eseguito il 12 novembre 2026: 30 URL distinti raggiungibili,
40/40 citazioni riscontrate nelle pagine di origine, zero errori. Una citazione
di La Russa sul passaggio di partito del 2010 va letta nel contesto storico
esplicitato dalla fonte: il resoconto distingue l'episodio del 2010 dalla
successiva fondazione di Fratelli d'Italia nel 2012.

```sh
python3 benchmarks/verdict_640/runner.py --check-sources
```

Test del runner con tre casi:

```sh
python3 -m unittest discover -s benchmarks/verdict_640 -p test_runner.py -v
```

Adapter esterno per un singolo record per volta. Il comando legge JSON da stdin
o l'endpoint riceve il medesimo oggetto in HTTP POST:

```json
{"statement":"testo esatto","person":"Nome","date":"2026-11-01","source_url":"https://..."}
```

La risposta è `{"label":"vero","evidence":["https://..."],"model_calls":1}`.
`label` ammette esattamente le cinque etichette in italiano; `model_calls` è
facoltativo e vale 1 per una singola invocazione se omesso. Per adapter con
strumenti, l'adapter deve conteggiare le invocazioni interne; senza quel dato
si misura soltanto l'invocazione esterna. Il riferimento gold e le evidenze del
corpus non vengono consegnati all'adapter durante il test.

```sh
python3 benchmarks/verdict_640/runner.py --command 'python3 /path/to/adapter.py'
python3 benchmarks/verdict_640/runner.py --endpoint http://127.0.0.1:8000/verdict
secret env OMNIROUTE_API_KEY -- python3 benchmarks/verdict_640/runner.py --baseline
```

La baseline usa un solo modello OpenAI-compatible attraverso OmniRoute sul MiniPC
(nessuna chiave di provider), senza capacità di ricerca in diretta. La misura
include risposte sbagliate, fallimenti/timeout (colonna `ERRORE`), tempi e
chiamate per ciascun caso; non certifica l'idoneità alla pubblicazione.
