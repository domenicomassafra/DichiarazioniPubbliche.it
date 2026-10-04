# Legal & Safety Research — Italia / UE

> Documento preliminare di product/legal research. Non è consulenza legale. Prima del lancio pubblico serve revisione da professionista qualificato.

## Obiettivo

Progettare il prodotto per essere documentabile, verificabile, correggibile, proporzionato, trasparente e rispettoso di privacy e copyright.

Non esiste una garanzia tecnica contro querele o azioni civili.

## Libertà di espressione

Costituzione italiana, art. 21.

Da studiare: diritto di cronaca, diritto di critica, interesse pubblico, verità e continenza nella giurisprudenza.

## Diffamazione

Codice penale, art. 595.

Implicazioni product:

- distinguere falso da ha mentito;
- non attribuire dolo o consapevolezza senza evidence sufficiente;
- ogni fatto determinato deve avere fonti e provenance;
- evitare linguaggio denigratorio non necessario.

## Responsabilità civile

Approfondire art. 2043 c.c., danni reputazionali/non patrimoniali e responsabilità per informazioni inesatte.

## Stampa / rettifica / prodotto editoriale

Legge 47/1948 e normativa collegata. Va capito se e quando il prodotto rientri in categorie editoriali specifiche.

Il meccanismo di replica e rettifica va implementato comunque.

## Privacy / GDPR

Regolamento UE 2016/679 e Codice privacy italiano.

Principi: lawfulness, purpose limitation, minimization, accuracy, storage limitation e accountability.

Persona pubblica non significa nessuna privacy. Raccogliere solo informazioni rilevanti al ruolo o a un interesse pubblico documentabile.

Le regole deontologiche pubblicate dal Garante ribadiscono il principio di essenzialità dell'informazione e specificano che la sfera privata delle persone note o che esercitano funzioni pubbliche deve essere rispettata quando le informazioni non hanno rilievo sul loro ruolo o sulla loro vita pubblica.

Fonte: https://garanteprivacy.it/web/guest/home/docweb/-/docweb-display/docweb/9067692

Da studiare: art. 6, 9, 10, rettifica, cancellazione ed eccezioni, art. 85, regole deontologiche giornalistiche, trattamento automatizzato e profiling.

## Dati giudiziari / casi mediatici

Verticale ad alto rischio. Serve policy separata per atti pubblici, indagati/imputati/condannati, presunzione di innocenza, dati di terzi, minori, vittime e informazioni non necessarie.

## Copyright

Legge 633/1941, incluso art. 70.

Policy proposta: transcript completo solo come dato interno se legalmente acquisibile/conservabile; output pubblico con estratti minimi necessari, link e timestamp; evitare ripubblicazione sostitutiva.

## Scraping / API / ToS

Analisi per piattaforma: YouTube, X, Meta/Instagram, TikTok, broadcaster, giornali e podcast platforms.

Distinguere ciò che è tecnicamente accessibile da ciò che è consentito da API/ToS, legge e diritto di ripubblicazione.

## AI Act

Regolamento UE 2024/1689.

Da verificare gli obblighi di trasparenza per contenuti generati/manipolati da AI destinati a informare il pubblico su materie di interesse pubblico.

Con full automation, progettare disclosure AI, model/version provenance, timestamp, policy version e generation metadata.

Fonte ufficiale EUR-Lex: https://eur-lex.europa.eu/eli/reg/2024/1689/oj/ita

## DSA

Da verificare in base a submission utenti, commenti, repliche, hosting UGC, segnalazioni e moderation.

## Right of reply / correction

Ogni Finding deve offrire:

- contesta;
- proponi fonte;
- rettifica;
- replica;
- status della contestazione;
- nuova analisi;
- changelog.

Mai correzioni silenziose.

## Source policy

Gerarchia proposta:

1. fonti primarie, atti e dataset ufficiali;
2. documenti tecnici/scientifici originali;
3. fonti secondarie qualificate;
4. giornali e agenzie;
5. altri siti;
6. social/user content come fonte della dichiarazione, non automaticamente come prova della verità.

## Terminologia

FACTUALLY_FALSE può essere usato quando il claim è sufficientemente contraddetto.

DELIBERATE_FALSEHOOD, bugia e ha mentito richiedono threshold molto più alto e prova dell'elemento intenzionale o della consapevolezza.

## Legal research backlog

Prima del public beta:

- giurisprudenza Cassazione su cronaca e critica;
- diffamazione online;
- responsabilità editoriale;
- rettifica online;
- GDPR e giornalismo;
- dati giudiziari;
- copyright transcript/audio/video;
- scraping/ToS;
- AI Act art. 50;
- DSA;
- ePrivacy, cookie e analytics;
- terms e privacy policy;
- procedure takedown;
- minori e vittime;
- retention;
- security incident duties;
- eventuale registrazione testata se applicabile.
