# DP-229 — donor e riuso (20 ottobre 2026)

- **Riuso principale, codice owner:** `countercase.py`, `challenger_material_inventory.py`, `challenger_research.py`, `publication_eligibility.py` già su main e [PR #236](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/pull/236) a SHA `f2d395878bbc2e9877e7787bf41277015866d972`. Non duplicare compilazione della query e non trasformare READY caller in autorità.
- [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo/commit/3d6cdf20755e9058ef8625c5ca31989bfe51e79c), SHA osservato il 20/10/2026, **MIT**: metodo di red teaming e confronto modelli; **scartata** dipendenza runtime perché manca binding alla review editoriale corrente. Nessun codice importato.
- [allenai/olmes](https://github.com/allenai/olmes/commit/5a51f502d463b8cdc4a2dcad7d7096c41ff1197e), SHA del 24/03/2026, **Apache-2.0**: **adottato metodo** ripetibilità/held-out, nessun codice importato.
- [Reddit LocalLLaMA, 28/06/2026](https://www.reddit.com/r/LocalLLaMA/comments/1uhi81a/i_had_55_llms_blindgrade_each_other_22k_judgments/): codice e dati dichiarati MIT dall'autore, licenza testo non attestata; **adottata cautela** contro bias intra-famiglia, nessun codice copiato.
- [Luca Soldaini su X, 26/11/2024](https://x.com/soldni/status/1861517215344021722): metodo OLMES per eval riproducibili; licenza del post non specificata, repo OLMES Apache-2.0; **adottato metodo** e non testo/payload.

Prima registrazione verificata nella [Ricerca riuso di #40](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/40#issuecomment-6302006492). Nuovo codice owner soltanto per il seam locale di audit mancante; nessuna dipendenza esterna aggiunta.
