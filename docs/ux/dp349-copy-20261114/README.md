# DP-349 · Metodo e Home sul sito pubblico · 14 novembre 2026

Catture reali di `https://dichiarazionipubbliche.it` (agent-browser, Chrome, pagina intera, 1440 e 390 px),
fatte dopo la release della PR #647.

| Pagina | 1440 px | 390 px |
| --- | --- | --- |
| Home | [home-1440.png](home-1440.png) | [home-390.png](home-390.png) |
| Metodo | [metodo-1440.png](metodo-1440.png) | [metodo-390.png](metodo-390.png) |

- **Metodo**: premessa di una frase, le quattro fasi con i nomi del design (Dichiarazione, Fonte
  originale, Confronto, Giudizio) allineate sulla stessa linea, esempio concreto con la dicitura «Dato fittizio».
- **Home**: lo stato vuoto compare una volta sola, nella colonna dove il design mette la dichiarazione
  in evidenza; la striscia dei percorsi è senza frecce flottanti.

Release `07328c2c8f7106b64470d0176316c5a3e1bb6ff09672bb4cbe835d55046caee5`, sorgente `2918ce67`,
commutata con CAS da `a953c2bc…`. `code_sha256` invariato (`05da9ac0…`): cambia solo il payload statico.
`verify --origin http://127.0.0.1:18090` → `PASS`. Le sei pagine pubbliche (`/`, `/metodo/`, `/esplora/`,
`/correzioni/`, `/dati/`, `/progetto/`) servite via HTTPS sono byte-identiche alla build locale.
Nessuno scroll orizzontale a 390 px.
