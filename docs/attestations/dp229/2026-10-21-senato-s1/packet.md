# DP-229 — dossier congelato per due controrevisioni AI (21 ottobre 2026)

**Uso:** canary documentale privato per la issue #40; non è un Finding pubblicabile e non attesta la presenza nel database operativo. La versione `candidate-senato-s1-v1` e gli identificatori sotto sono locali al dossier. Non esiste un `claim_id` canonico approvato, un inventario material-v3 del DB riferito a questa fonte, una receipt DP-228 di query eseguite o un packet incorporato in una Verification Run.

## Fonte primaria, versioni e diritti

- Autorità: Senato della Repubblica — Servizio dell'Informatica, repository ufficiale [AkomaNtosoBulkData](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData), commit [`2da7d887c8125286312e88c6913fa194feb1c6ce`](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/commit/2da7d887c8125286312e88c6913fa194feb1c6ce).
- Documento primario: [`Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml`](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/Leg19/Atto00055177/ddlpres/01360967-ft.akn.xml), file di 13.036 byte scaricato dal `raw.githubusercontent.com` pinned, SHA-256 `57fcd8ae860d3e4593686567612e251dc0f40a4d1842bddb6eeac68bdb7ad929` (21/10/2026).
- Diritti: [README.MD](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/README.MD) dichiara autore `Senato della Repubblica - Servizio dell'Informatica` e licenza **CC BY 4.0**; [LICENSE.MD](https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/2da7d887c8125286312e88c6913fa194feb1c6ce/LICENSE.MD) contiene il testo CC BY 4.0. **Clearance AI limitata:** si può ispezionare e citare con attribuzione il file di quel commit alle condizioni della licenza; nessuna concessione inferita per media o contenuti esterni; nessuna receipt canonical source-rights del prodotto è stata emessa. Privacy: documento legislativo pubblico, nessun dato privato necessario nel dossier; resta vincolante il gate sorgente/privacy live.
- Testo e metadata XML: `FRBRnumber=1`, `FRBRdate=2022-10-13`, `FRBRsubtype=DDLPRES`, `FRBRname=disegno di legge`, `FRBRuri=http://dati.senato.it/osr/Ddl/2022-10-13/1`.

## Ipotesi esatta da sfidare

`claim-candidate-senato-s1-v1`: «Il 13 ottobre 2022 fu presentato al Senato il disegno di legge S.1, iniziativa del senatore Parrini, che proponeva, tra l'altro, di modificare la composizione di alcuni organismi bicamerali».

Passaggi limitati al controllo dell'ipotesi, attribuiti al Senato (fonte XML sopra): titolo «Disposizioni per l'adeguamento della composizione degli organismi bicamerali alla riduzione del numero dei parlamentari di cui alla legge costituzionale 19 ottobre 2020, n. 1»; intestazione «d'iniziativa del senatore PARRINI» e «COMUNICATO ALLA PRESIDENZA IL 13 OTTOBRE 2022»; articolo 1, comma 1, formula **«sono sostituite»** per una proposta di modifica da 15+15 a 10+10; articolo 1, comma 8, prevede entrata in vigore successiva a pubblicazione in Gazzetta Ufficiale.

**Controtesi da indagare:** il testo è una *proposta presentata* (`DDLPRES`), non dimostra approvazione, promulgazione, pubblicazione in Gazzetta o entrata in vigore. La formula «sono sostituite» appartiene all'articolato proposto, non a una legge accertata. La presenza del file su GitHub non prova lo stato attuale dell'iter. La presentazione del 2022 non coincide con una verifica aggiornata al 2026.

## Superfici esaminate e limiti

- `E-PRIMARY-XML`: documento primario versionato, SHA sopra, candidato per ruolo `CONTEXT`/proposta ufficiale. La licenza è verificata documentalmente sul repository; l'approvazione nel registro del prodotto è **assente**.
- `E-README-RIGHTS`: README e LICENSE del medesimo repository, verifica limitata a licenza e tipo documento; **stesso origin group** della fonte XML, quindi non contarli come fonte indipendente sulla vicenda legislativa.
- `E-ITER-OFFICIAL`: [scheda ufficiale S.1 XIX legislatura](https://www.senato.it/leggi-e-documenti/disegni-di-legge/scheda-ddl?did=55177), reperita attraverso una ricerca pubblica del 21/10/2026 successiva all'avvio dei due reviewer. Indica **presentato il 13/10/2022**, annunciato nella seduta n. 1, **assegnato il 23/11/2022 (non ancora iniziato l'esame)**. Corrobora l'identità e aggiunge cronologia, ma la medesima amministrazione è l'origin group; il testo corrente della pagina non è una prova che nessun evento sia mai avvenuto dopo. Link e risultato aggiunti **dopo il congelamento del prompt** e quindi non attestati come letti da entrambi i revisori.
- Nessuna evidenza `CONTRADICT`/`LIMITATION` ammessa e indipendente è presente nel DB per questo dossier. Nessun inventario `challenger-material-inventory-v3` riletto su questa specifica claim; budget massimo DP-229 **32 query aggregate**, ricerche effettuate dal canale DP-228 **0**, costo fatturato **UNKNOWN** (non dedurre `0` dalle chiamate CLI incluse).
- Ciascun revisore riceve lo stesso packet e prompt; non riceve la risposta dell'altro. Le sue proposte di fonti aggiuntive sono solo lead, finché intake/diritti/provenienza non le ammettono. Conflitti dichiarati tra modelli/host/prompts e possibile parentela della famiglia GPT con il generatore GPT-6 devono essere registrati.

**Gate deterministico atteso:** `HOLD`, `publication_authority=false`. Non dichiarare `research_complete`, `material_approved`, `reviewer_independent` o `incorporated` sulla base di questa sola revisione.
