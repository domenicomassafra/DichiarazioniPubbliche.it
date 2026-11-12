# DP-349 · confronto con il Figma finale del proprietario · 11 novembre 2026

**Riferimento unico:** [Dichiarazioni Pubbliche — Redesign editoriale V1](https://www.figma.com/design/emKLEdxy5o1R5e2tDOsafZ/) indicato dal proprietario il 11 novembre alle 22:45 Europe/Rome. Sostituisce i riferimenti grafici precedenti per la #349.

**Origine degli screenshot:** lato sinistro: frame reali del file Figma, acquisiti tramite l'embed Figma ufficiale in Chrome isolato con rendering WebGL; lato destro: screenshot reali Chrome della build Astro dimostrativa. La prima serie fissa la PR #629 al commit `a7054406` (prima della nuova implementazione); la seconda serie mostra il candidato successivo nella stessa branch. Lo screenshot a destra della seconda serie è generato dallo stesso runner che verifica 24 rotte, viewport mobile, zoom browser reale al 200%, tastiera e assenza di richieste esterne.

Le immagini fotografiche di Figma sono **oscurate nelle copie affiancate** per non redistribuire ritratti con licenza non chiarita. Gli screenshot locali originali non sono parte di questa consegna. I contenuti demo nelle immagini del prodotto sono fittizi e visibilmente segnalati; i numeri e le citazioni del frame Figma non sono stati copiati nella proiezione pubblica.

| Schermata | Figma vs PR #629 precedente | Figma vs candidata aggiornata | Scelta e limite |
| --- | --- | --- | --- |
| Dichiarazione | [prima](statement-figma-vs-pr629.png) | [dopo](statement-figma-vs-implementation.png) | Identità a sinistra e lettura a destra. Il vincolo del prodotto richiede **provenienza prima dell'esito**. Niente citazione diretta o grafico numerico senza proiezione autorizzata. |
| Home | [prima](home-figma-vs-pr629.png) | [dopo](home-figma-vs-implementation.png) | Titolo e densità Figma, ricerca, evidenza da dossier pubblicato, quattro percorsi immediatamente sotto. Stato vuoto senza record approvati. |
| Persona | [prima](person-figma-vs-pr629.png) | [dopo](person-figma-vs-implementation.png) | Identità nella colonna sinistra, cronologia e filtri in quella destra. Nessun ritratto inventato; il punteggio rimane riferito alla sola dichiarazione. |
| Tema | [prima](topic-figma-vs-pr629.png) | [dopo](topic-figma-vs-implementation.png) | Testata ridotta e dichiarazioni leggibili come registro cronologico. Indici di fonti e persone restano consultabili. |
| Esplora | [prima](explore-figma-vs-pr629.png) | [dopo](explore-figma-vs-implementation.png) | Ricerca, schede di tipo, filtro laterale e righe compatte senza l'effetto card. |
| Fonte | [prima](content-figma-vs-pr629.png) | [candidata precedente](content-figma-vs-implementation.png) · [desktop aggiornato](after-matrix/content-desktop.png) · [telefono aggiornato](after-matrix/content-phone.png) | Dal 12/11 media ed estratto affiancati con dichiarazioni selezionabili sotto, come nel Figma; a 375px il contenuto segue il media. La selezione mostra il passaggio e aggiorna `?momento=`. Nessun play senza media pubblico autorizzato. |
| Metodo | [prima](method-figma-vs-pr629.png) | [dopo](method-figma-vs-implementation.png) | Testata più breve e quattro fasi editoriali in prima schermata. Il metodo mantiene informazioni su limiti, correzioni e diritti. |

Le catture correnti complete a 1440px e 375px per nove famiglie sono in [after-matrix](after-matrix/). I frame Figma presentano un esempio ipotetico con citazione, percentuali e un volto: nessuno di questi elementi è abilitato per la pubblicazione senza approvazione della fonte, della formulazione verbatim e dei diritti.

## Verifiche e acceptance ancora aperte

**Delta del 12 novembre, Fonte:** riordinate le sezioni nel DOM secondo l'ordine editoriale, eliminate le compressioni CSS desktop della pagina, conservate attribuzione/diritti, selezione dei passaggi e disclosure. Il browser verifica posizione delle colonne e della lista a 1440/375px, selezione e URL, più lo zoom 200% sulle nove famiglie. Le immagini aggiornate sopra provengono dalla stessa build di verifica isolata. Il resto del confronto Figma resta da confermare schermata per schermata prima di dichiarare parità totale.

- [x] Verificato Figma originale e confronto prima/dopo delle sette schermate, con ritratti oscurati per la documentazione.
- [x] Implementati principali cambi di composizione, mantenendo etichette e dati dalla proiezione pubblica approvata.
- [x] Chrome QA demo: desktop e telefono, nessun overflow, zoom reale 200%, riduzione animazioni, 0 richieste esterne.
- [x] Contratti di rotte, design, accessibilità e barriera proiezione/demo.
- [ ] Conferma visiva del proprietario sull'implementazione, inclusa l'assenza delle fotografie e dei grafici Figma non autorizzati.
- [ ] GitHub required CI verde sulla testa finale della PR e merge squash con readback di `main`.
- [ ] Preview privata MiniPC aggiornata all'head integrato mediante procedura supportata, con readback reale.
- [ ] Promozione pubblica autorizzata, record autentici pubblicabili e verifica consumer reale; questo passaggio dipende dai gate editoriali #413/#468/#98.

Le schermate comparate riguardano struttura e comportamento. Non dimostrano autorizzazione alla pubblicazione, presenza di record reali o accettazione estetica del proprietario.
