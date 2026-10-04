# Brand & Naming v0 — Dichiarazioni Pubbliche

Data: 2026-09-22

## Decisione

> **Superseded 2026-10-03.** Questo documento nasceva come esplorazione v0. La decisione
> owner attuale è definitiva a livello di naming di prodotto: **Dichiarazioni Pubbliche**,
> con label dominio canonica `dichiarazionipubbliche.it`. Registrazione dominio, handle e
> trademark/legal clearance restano gate separati e non sono implicati dalla decisione di naming.

**Dichiarazioni Pubbliche**

Tagline v0:

**Memoria verificabile delle dichiarazioni pubbliche.**

Il nome descrive il prodotto come record verificabile e longitudinale, non come arbitro politico o macchina che assegna un punteggio di verità alle persone.

## Perché adesso

Il naming non viene più deciso su un'idea astratta. Esistono già:

- un ContentAudit reale;
- un modello dati e una tassonomia;
- provenance e publication gate;
- transcript routing e retention policy;
- PostgreSQL schema + queue;
- un secondo contenuto long-form acquisito caption-first;
- una direzione UX definita attorno a person, topic, content audit e discrepancy view.

Questo è sufficiente per fissare un'identità di lavoro senza congelare prematuramente logo o design system.

## Perché “Dichiarazioni Pubbliche”

Il nome richiama naturalmente l'idea di mettere qualcosa **on the record**:

- ciò che è stato detto resta consultabile;
- la formulazione originale resta separata dalla normalizzazione;
- le fonti restano collegate;
- correzioni e diritto di replica non cancellano la storia;
- cambi di posizione e contraddizioni possono essere mostrati nel tempo;
- il brand non implica automaticamente che una persona abbia mentito.

È quindi coerente con il differenziatore del prodotto: **temporal public-record graph + provenance + publication policy + UX/API**.

## Posizionamento minimo

Nome: **Dichiarazioni Pubbliche**

Tagline: **Memoria verificabile delle dichiarazioni pubbliche.**

Descrizione breve:

> Dichiarazioni pubbliche, fonti, contesto, verifiche, cambi e correzioni in un record consultabile e versionato.

Descrizione repository:

> Open-source infrastructure for a verifiable, source-linked and versioned record of public statements.

## Tone of voice

Il brand deve essere:

- documentale, non accusatorio;
- preciso, non moralista;
- leggibile, non burocratico;
- trasparente sulle incertezze;
- source-first;
- neutrale rispetto a partiti, persone e schieramenti.

Evitare come promessa di brand:

- “scopriamo chi mente”;
- “la verità sulla politica”;
- ranking di affidabilità personale;
- linguaggio da tribunale mediatico;
- visual identity partisan o da breaking-news outrage.

## Cutover tecnico approvato — 2026-10-03

L'owner ha autorizzato il rename tecnico completo del workspace locale. La mappatura
canonica è:

- directory repo: `/Users/domenico/Code/DichiarazioniPubbliche.it`;
- mirror MiniPC target: `/home/udodo/src/DichiarazioniPubbliche.it`;
- package Python: `dichiarazioni_pubbliche`;
- distribution/CLI/systemd prefix: `dichiarazioni-pubbliche`;
- ticket prefix: `DP-`;
- database target: `dichiarazioni_pubbliche`;
- domain label: `dichiarazionipubbliche.it`.

I dati persistiti e il runtime MiniPC richiedono migrazione/prova separata prima di poter
dichiarare il cutover production completo. Il rename non modifica le invarianti di
provenance, review o publication gate.

## Visual identity: non ancora definitiva

Prima dei tre prototipi UX non fissare un logo complesso o un design system rigido.

Per i prototipi basta un wordmark tipografico **Dichiarazioni Pubbliche** e una UI editoriale sobria. Il simbolo definitivo deve emergere dopo aver visto se il prodotto funziona meglio come newsroom, evidence graph o interactive media timeline.

## Clearance ancora necessaria

Le verifiche preliminari del 2026-09-22 non hanno mostrato un prodotto omonimo evidente nello stesso spazio e i domini principali controllati non risolvevano via DNS; i controlli WHOIS puntuali davano `dichiarazionipubbliche.it` come disponibile e `.org` / `.com` come non trovati.

Questi segnali NON costituiscono una ricerca marchi o una garanzia di disponibilità. Prima del lancio pubblico:

1. ricerca professionale/ufficiale UIBM + EUIPO/TMview sulle classi pertinenti;
2. registrazione o prenotazione dei domini desiderati;
3. verifica handle social/GitHub;
4. verifica del cutover tecnico locale e del successivo cutover runtime MiniPC;
5. review legale insieme al resto della launch policy.

## Stato

**Naming product-level: APPROVATO dall'owner — Dichiarazioni Pubbliche (2026-10-03).**

**Domain registration / handle reservation / trademark & legal clearance: OPEN.**

**Logo/design system definitivo: DEFERRED fino ai prototipi UX.**
