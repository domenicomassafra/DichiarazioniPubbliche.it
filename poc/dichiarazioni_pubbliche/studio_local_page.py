"""Static, login-only HTML shell for the local read-only operator API.

There is no embedded secret, source body, external asset, third-party script or
persistent browser credential. The operator pastes a token into memory only.
All server results use textContent; never innerHTML.
"""

from __future__ import annotations

import re

_NONCE = re.compile(r"^[0-9a-f]{32}$")

_PAGE = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive,nosnippet">
  <title>Studio locale · Dichiarazioni Pubbliche</title>
  <style nonce="__NONCE__">
    :root{font-family:system-ui,sans-serif;color:#182130;background:#f4f5f2;line-height:1.5}
    *{box-sizing:border-box}
    body{max-width:70rem;margin:auto;padding:1.5rem}
    h1{font-size:1.7rem;margin:0}h2{font-size:1.25rem}
    p{max-width:55rem;overflow-wrap:anywhere}
    .quiet{color:#354256;font-size:.93rem}
    .rules{border-block:1px solid #7d8580;padding:1rem 0;margin:1rem 0}
    .controls{display:flex;flex-wrap:wrap;gap:1rem;align-items:end}
    label{display:grid;gap:.2rem;min-width:14rem;max-width:100%;font-weight:600;font-size:.9rem}
    input,select,textarea,button{font:inherit;padding:.65rem;border:1px solid #4d5861;border-radius:0;min-height:2.5rem;background:white;color:inherit}
    input,select,textarea{width:100%}button{cursor:pointer}
    button[aria-pressed=true],button[type=submit]{background:#182130;color:white}
    :focus-visible{outline:3px solid #0f46b0;outline-offset:2px}
    [hidden]{display:none!important}
    .pane{margin-top:1rem;padding:1rem;border:1px solid #9ca3a0}
    .notice{font-weight:600}
    #member-links{display:grid;gap:.4rem;margin:1rem 0}
    #member-links button{text-align:left;overflow-wrap:anywhere}
    #collection-links{display:grid;gap:.4rem;margin:1rem 0}
    #collection-links button{text-align:left;overflow-wrap:anywhere}
    #claim-links{display:grid;gap:.4rem;margin:1rem 0}
    #claim-links button{text-align:left;overflow-wrap:anywhere}
    #corpus-links{display:grid;gap:.4rem;margin:1rem 0}
    #corpus-links button{text-align:left;overflow-wrap:anywhere}
    #corpus-inspector{border:1px solid #68747c;padding:1rem;margin-top:1rem}
    #corpus-inspector dl{display:grid;grid-template-columns:minmax(8rem,12rem) minmax(0,1fr);gap:.45rem}
    #corpus-inspector dd{margin:0;overflow-wrap:anywhere}
    #collection-lineage-links,#capture-queue-links,#collection-navigation-links{display:grid;gap:.4rem;margin:1rem 0}
    #collection-lineage-links button,#capture-queue-links button,#collection-navigation-links button{text-align:left;overflow-wrap:anywhere}
    pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e9ebe6;padding:1rem;font-size:.86rem}
    @media(max-width:40rem){body{padding:.8rem}.controls,label{display:grid;width:100%}}
  </style>
</head>
<body>
  <header>
    <p class="quiet">Studio · accesso locale protetto · sola lettura</p>
    <h1>Esplora i riferimenti privati</h1>
    <p>Operazioni sui dati persistiti senza mostrare testi privati o autorizzare revisioni. Accessibile solo dalla macchina locale o tramite tunnel SSH autorizzato.</p>
  </header>
  <section class="rules" aria-labelledby="accesso">
    <h2 id="accesso">Accesso temporaneo</h2>
    <div class="controls">
      <label for="token">Token operatore (rimane solo nella memoria di questa pagina)
        <input id="token" type="password" autocomplete="off" spellcheck="false" minlength="64" maxlength="128" required>
      </label>
      <button id="clear" type="button">Cancella token</button>
    </div>
    <p class="quiet">La pagina non usa cookie, LocalStorage né connessioni esterne. Chiudendo la scheda, il token non viene salvato.</p>
  </section>
  <nav class="controls" aria-label="Workspace Studio">
    <button type="button" aria-pressed="true" data-panel="corpus">Corpus</button>
    <button type="button" aria-pressed="false" data-panel="collections">Collections</button>
    <button type="button" aria-pressed="false" data-panel="inbox">Inbox</button>
    <button type="button" aria-pressed="false" data-panel="matches">Match</button>
    <button type="button" aria-pressed="false" data-panel="captures">Catture</button>
  </nav>
  <main>
    <section class="pane" id="corpus">
      <h2>Ricerca nel corpus</h2><p>Ricerca lessicale sul database privato. I risultati contengono soltanto ID e riferimenti.</p>
      <form data-endpoint="/v1/corpus/search">
        <div class="controls"><label>Termini di ricerca<input name="query" maxlength="128" required></label>
        <label>Tipo di risultato
          <select name="kind">
            <option value="">Tutti i tipi</option>
            <option value="CONTENT">Content</option>
            <option value="PASSAGE">Passage</option>
            <option value="STATEMENT_CANDIDATE">Statement Candidate</option>
            <option value="CLAIM_CANDIDATE">Claim Candidate</option>
            <option value="ATOMIC_CLAIM">Atomic Claim</option>
            <option value="PERSON">Persona</option>
            <option value="ORGANIZATION">Organizzazione</option>
            <option value="TOPIC">Tema</option>
            <option value="EVENT">Evento</option>
            <option value="COLLECTION">Raccolta</option>
          </select>
        </label>
        <label>ID raccolta (facoltativo)<input name="collection_id" maxlength="180" autocomplete="off"></label>
        <label>ID sorgente (facoltativo)<input name="source_id" maxlength="180" autocomplete="off"></label>
        <label>ID persona (facoltativo)<input name="person_id" maxlength="180" autocomplete="off"></label>
        <label>ID tema (facoltativo)<input name="topic_id" maxlength="180" autocomplete="off"></label>
        <label>ID evento (facoltativo)<input name="event_id" maxlength="180" autocomplete="off"></label>
        <label>Dal giorno (UTC)<input name="from_date" type="date"></label>
        <label>Al giorno (UTC)<input name="to_date" type="date"></label>
        <label>Stato (facoltativo)<input name="status" maxlength="180" autocomplete="off"></label>
        <label>Tipo di claim (facoltativo)<input name="claim_type" maxlength="180" autocomplete="off"></label>
        <label>Da verificare
          <select name="check_worthy"><option value="">Qualsiasi stato</option>
            <option value="true">Sì</option><option value="false">No</option>
          </select>
        </label>
        <label>Limite (1–20)<input name="limit" type="number" min="1" max="20" value="20" required></label>
        <button type="submit">Cerca</button></div>
      </form>
      <div id="corpus-list" role="region" aria-label="Risultati del corpus">
        <p role="status" id="corpus-summary" aria-live="polite">Nessuna ricerca eseguita.</p>
        <div id="corpus-links" role="group" aria-label="Seleziona un risultato da ispezionare"></div>
      </div>
      <section id="corpus-inspector" aria-labelledby="corpus-inspector-title" hidden>
        <h3 id="corpus-inspector-title" tabindex="-1">Riferimenti del risultato selezionato</h3>
        <p class="quiet">Solo identificativi persistiti; nessun testo sorgente, attribuzione approvata o permesso di pubblicazione.</p>
        <dl id="corpus-references"></dl>
        <button type="button" id="corpus-source-jump" hidden>Verifica Content e sorgente nella raccolta</button>
        <p id="corpus-jump-status" role="status" aria-live="polite"></p>
        <button type="button" id="corpus-back">Torna ai risultati</button>
      </section>
    </section>
    <section class="pane" id="collections" hidden>
      <h2>Raccolte persistite</h2><p>Stato, riferimenti e numero dei contenuti inclusi. Nessuna affermazione di copertura completa.</p>
      <form data-endpoint="/v1/collections/list">
        <div class="controls"><label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Mostra raccolte</button></div>
      </form>
      <p id="collection-list-summary" role="status" aria-live="polite">Nessuna raccolta selezionata.</p>
      <div id="collection-links" role="group" aria-label="Seleziona una raccolta persistita"></div>
      <h2>Carico operativo privato della raccolta (canary PostgreSQL)</h2>
      <p>Contenuti inclusi, Capture corrente, Passage e candidati: conta blocchi e controlli da fare, non persone da approvare. Modalità sorgente PostgreSQL locale esplicitamente configurata; nessuna decisione di verità, foto o pubblicazione.</p>
      <form data-endpoint="/v1/operator/workload" aria-describedby="workload-summary">
        <div class="controls">
          <label>ID raccolta<input name="collection_id" maxlength="180" required></label>
          <label>Content per pagina (1–20)<input name="limit" type="number" min="1" max="20" value="10" required></label>
          <label>Cursore della pagina precedente<input name="after" maxlength="2048"></label>
          <button type="submit">Leggi blocchi e contenuti da ispezionare</button>
        </div>
      </form>
      <p id="workload-summary" role="status" aria-live="polite">Nessuna coda operativa letta.</p>
      <div id="workload-links" role="group" aria-label="Content operativi selezionabili"></div>
      <h2 id="collection-navigation-heading" tabindex="-1">Percorso persistito Collection → Capture → Passage → Candidate</h2>
      <p>Un'unica lettura PostgreSQL coerente di Content inclusi, cattura più recente, selettori scritti e candidati. Solo hash, ID e stati; nessun estratto o permesso. Seleziona un Passage per aprire il dettaglio completo con i Claim Candidate.</p>
      <form data-endpoint="/v1/collections/navigate">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Content per pagina (1–10)<input name="limit" type="number" min="1" max="10" value="10" required></label>
        <label>Dopo Content ID<input name="after_content_id" maxlength="180"></label>
        <button type="submit">Naviga percorso persistito</button></div>
      </form>
      <p id="collection-navigation-summary" role="status" aria-live="polite">Nessuna navigazione caricata.</p>
      <div id="collection-navigation-links" role="group" aria-label="Content e Passage persistiti selezionabili"></div>
      <h2>Contenuti inclusi</h2><p>Seleziona una raccolta per leggere solo i riferimenti persistiti. Il dettaglio indica i collegamenti verificati e gli elementi ancora assenti.</p>
      <form data-endpoint="/v1/collections/members">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Content ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Elenca contenuti</button></div>
      </form>
      <p id="collection-member-summary" role="status" aria-live="polite">Nessun Content caricato.</p>
      <div id="member-links" role="group" aria-label="Contenuti persistiti selezionabili"></div>
      <h2>Dettaglio Content</h2>
      <form data-endpoint="/v1/collections/member">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Limite claim (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo claim ID<input name="after_claim_id" maxlength="180"></label>
        <button type="submit">Ispeziona fonte e claim</button></div>
      </form>
      <div id="claim-links" role="group" aria-label="Claim storici selezionabili"></div>
      <h2>Versioni di cattura per Content incluso</h2>
      <p>Solo hash, date e stati persistiti. Nessun URL, corpo, estratto o autorizzazione di acquisizione. La raccolta e il Content devono risultare collegati nel database.</p>
      <form data-endpoint="/v1/collections/captures">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Limite (1–20)<input name="limit" type="number" min="1" max="20" value="20" required></label>
        <label>Dopo Capture ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Mostra versioni persistite</button></div>
      </form>
      <p id="collection-capture-summary" role="status" aria-live="polite">Nessun Content selezionato per le catture.</p>
      <div id="collection-capture-links" role="group" aria-label="Catture e selettori privati per Content"></div>
      <h2 id="collection-lineage-heading" tabindex="-1">Passage scritto e candidati persistiti</h2>
      <p>Seleziona una cattura e poi un Passage: il dettaglio è vincolato a raccolta, Content e versione di cattura. Stati e hash non conferiscono diritti o approvazione.</p>
      <form data-endpoint="/v1/collections/passage-lineage">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" required></label>
        <label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Capture ID<input name="capture_id" maxlength="180" required></label>
        <label>Passage ID<input name="passage_id" maxlength="180" required></label>
        <label>Limite Statement (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Statement ID<input name="after_statement_id" maxlength="180"></label>
        <button type="submit">Ispeziona collegamenti persistiti</button></div>
      </form>
      <p id="collection-lineage-summary" role="status" aria-live="polite">Nessun Passage scritto selezionato.</p>
      <div id="collection-lineage-links" role="group" aria-label="Statement e Claim Candidate privati della versione selezionata"></div>
      <section id="collection-lineage-inspector" aria-label="Dettaglio del candidato selezionato" hidden>
        <h3 id="collection-candidate-heading" tabindex="-1">Collegamenti del candidato</h3>
        <p id="collection-candidate-detail"></p>
      </section>
      <h2>Decisione privata persistita (storico)</h2>
      <p>Rilettura di una ricevuta PostgreSQL firmata separatamente dal revisore. Il token Studio serve solo a consultarne gli ID e lo stato corrente della fonte, non ad approvarla, creare Claim o pubblicare.</p>
      <form data-endpoint="/v1/candidate/decision-receipt">
        <div class="controls">
          <label>Claim Candidate ID<input name="candidate_id" maxlength="180" required></label>
          <label>MatchRun ID<input name="run_id" maxlength="180" required></label>
          <label>Capture ID<input name="capture_id" maxlength="180" required></label>
          <label>Passage ID<input name="passage_id" maxlength="180" required></label>
          <label>Request key ricevuta<input name="request_key" maxlength="180" required></label>
          <button type="submit">Leggi ricevuta senza modifiche</button>
        </div>
      </form>
      <p id="collection-decision-summary" role="status" aria-live="polite">Nessuna ricevuta letta.</p>
      <h2>Registra una decisione privata già attestata (modalità operatore separata)</h2>
      <p>È richiesta una firma DP-310 già emessa esternamente, vincolata a questo preciso Candidate, MatchRun, Capture/Passage, versione, scelta, revisione e identità. Il token Studio da solo non firma decisioni. HOLD/REJECT/REVIEW_CREATE/REVIEW_LINK sono **intenzioni storiche**, non promozione, creazione Claim, equivalenza verificata o pubblicazione.</p>
      <form data-endpoint="/v1/candidate/decision-annotate" aria-describedby="candidate-write-summary">
        <div class="controls">
          <label>Claim Candidate ID<input name="candidate_id" maxlength="180" required></label>
          <label>MatchRun ID<input name="run_id" maxlength="180" required></label>
          <label>MatchRun input SHA-256<input name="input_fingerprint" minlength="64" maxlength="64" required></label>
          <label>Passage ID<input name="passage_id" maxlength="180" required></label>
          <label>Capture ID<input name="capture_id" maxlength="180" required></label>
          <label>Capture SHA-256<input name="capture_sha256" minlength="64" maxlength="64" required></label>
          <label>Request key immutabile<input name="request_key" maxlength="180" required></label>
          <label>Intenzione<select name="decision"><option>HOLD</option><option>REJECT</option><option>REVIEW_CREATE</option><option>REVIEW_LINK</option></select></label>
          <label>Revisione prevista<input name="expected_revision" type="number" min="0" step="1" value="0" required></label>
          <label>Actor reference<input name="actor_ref" maxlength="180" required></label>
          <label>Target type (solo REVIEW_LINK)<input name="target_type" maxlength="180"></label>
          <label>Target ID (solo REVIEW_LINK)<input name="target_id" maxlength="180"></label>
          <label>Credential ID locale<input name="credential_id" maxlength="128" required></label>
          <label>Ricevuta di identità firmata<input name="authority_receipt_id" maxlength="180" required></label>
          <label style="min-width:0;width:100%;flex:1 1 20rem">ReviewEvent integrale già firmato, JSON (rimane nella sessione)
            <textarea name="review_event_json" rows="5" maxlength="3000" required spellcheck="false" autocomplete="off"></textarea>
          </label>
          <label>Conferma solo intenzione privata<select name="confirm_private_decision" required><option value="">Seleziona</option><option value="true">Confermo: nessuna promozione o pubblicazione</option></select></label>
          <button type="submit">Registra intenzione firmata con CAS</button>
        </div>
      </form>
      <p id="candidate-write-summary" role="status" aria-live="polite">Nessuna intenzione candidata inviata. Richiede l'avvio esplicito del writer.</p>
      <h2>Provenienza di un claim storico</h2>
      <p>Stati e hash di attribuzione persistiti. APPROVED indica lo stato del record di attribuzione, non autorizza la riproduzione della fonte o la pubblicazione.</p>
      <form data-endpoint="/v1/collections/claim-provenance">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Claim ID<input name="claim_id" maxlength="180" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo provenance ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Verifica provenienza</button></div>
      </form>
    </section>
    <section class="pane" id="inbox" hidden>
      <h2>Discovery Inbox</h2><p>Record di discovery e codici di blocco senza URL, corpi o titoli non revisionati.</p>
      <h2>Coda privata delle catture cambiate o bloccate</h2>
      <p>Eccezioni persistite per raccolta; nessuna decisione di revisione o azione di cattura viene autorizzata.</p>
      <form data-endpoint="/v1/discovery/capture-queue">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Capture ID<input name="after_capture_id" maxlength="180"></label>
        <button type="submit">Mostra eccezioni delle catture</button></div>
      </form>
      <p id="capture-queue-summary" role="status" aria-live="polite">Nessuna coda letta.</p>
      <div id="capture-queue-links" role="group" aria-label="Catture bloccate o cambiate"></div>
      <h2>Catalogo Discovery per raccolta</h2>
      <p>Provenienza, stato della raccolta, diritti e motivi di blocco dal database. Nessuna azione di revisione, cattura o pubblicazione è abilitata da questa pagina.</p>
      <form data-endpoint="/v1/discovery/inbox">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Discovery Hit ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Consulta Inbox persistita</button></div>
      </form>
      <p id="inbox-annotation-summary" role="status" aria-live="polite">Nessun Hit caricato.</p>
      <div id="inbox-annotation-links" role="group" aria-label="Discovery Hit selezionabili per lo storico e l'annotazione privata"></div>
      <h2>Verifica compatibilità selezione multipla</h2>
      <p>Controllo sullo stesso snapshot SQL per massimo 10 Hit. Anteprima soltanto, senza approvazioni, rifiuti o scritture.</p>
      <form data-endpoint="/v1/discovery/bulk-preview">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Hit ID separati da virgole<input name="hit_ids_csv" maxlength="1809" required></label>
        <label>Annotazione non vincolante<select name="decision"><option value="NEEDS_REVIEW">NEEDS_REVIEW</option><option value="DEFERRED">DEFERRED</option></select></label>
        <button type="submit">Verifica senza modificare</button></div>
      </form>
      <form data-endpoint="/v1/discovery/list">
        <div class="controls"><label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Mostra coda</button></div>
      </form>
      <h2>Provenienza del risultato</h2>
      <p>Controllo puntuale di run, tentativo, query, manifest, Collection e autorizzazioni. Gli sblocchi elencati sono interventi da verificare: non approvazioni automatiche.</p>
      <form data-endpoint="/v1/discovery/inspect">
        <div class="controls">
          <label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
          <label>ID Discovery Hit<input name="hit_id" maxlength="180" required></label>
          <button type="submit">Ispeziona provenienza</button>
        </div>
      </form>
      <h2>Storico annotazioni Discovery (sola lettura)</h2>
      <p>Decisioni private persistite, non autorizzazioni: ogni risultato resta soggetto a identità del revisore e diritti sulle fonti da verificare. L'archivio è disponibile soltanto dopo la migrazione SQL.</p>
      <form data-endpoint="/v1/discovery/triage-history">
        <div class="controls">
          <label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
          <label>ID Discovery Hit<input name="hit_id" maxlength="180" required></label>
          <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
          <label>Dopo revisione<input name="after_revision" type="number" min="0" step="1" value="0" required></label>
          <button type="submit">Leggi annotazioni</button>
        </div>
      </form>
      <h2 id="triage-write-heading" tabindex="-1">Annotazione privata firmata (modalità operatore separata)</h2>
      <p>Richiede l'avvio manuale del servizio di annotazione e una ricevuta HMAC già emessa fuori dal browser per questo esatto Hit, revisione, decisione e attore. Il token da solo non abilita scritture. Questa annotazione NON rifiuta realmente la fonte, NON avvia Capture e NON approva o pubblica candidati.</p>
      <form data-endpoint="/v1/discovery/triage-annotate">
        <div class="controls">
          <label>Collection ID<input name="collection_id" maxlength="180" required></label>
          <label>Discovery Hit ID<input name="hit_id" maxlength="180" required></label>
          <label>Request key nuova o da riprodurre<input name="request_key" maxlength="128" autocomplete="off" required></label>
          <label>Annotazione privata<select name="decision"><option value="NEEDS_REVIEW">NEEDS_REVIEW</option><option value="DEFERRED">DEFERRED</option><option value="REJECTED">REJECTED (solo annotazione)</option></select></label>
          <label>Revisione corrente prevista<input name="expected_revision" type="number" min="0" step="1" value="0" required></label>
          <label>Actor reference<input name="actor_ref" maxlength="128" autocomplete="off" required></label>
          <label>Ricevuta firmata privata<input name="receipt_id" maxlength="110" autocomplete="off" required></label>
          <label>Conferma esplicita<select name="confirm_private_annotation" required><option value="">Seleziona</option><option value="true">Confermo solo annotazione privata</option></select></label>
          <button type="submit">Registra annotazione firmata con CAS</button>
        </div>
      </form>
      <p id="triage-write-summary" role="status" aria-live="polite">Nessuna annotazione inviata. Il server predefinito è di sola lettura.</p>
    </section>
    <section class="pane" id="matches" hidden>
      <h2>Candidati e corrispondenze</h2><p>Le classificazioni non conferiscono autorizzazione. La verifica approfondita confronta il run con input persistiti e contesto attuale DP-117, mostrando i blocchi prima di qualunque azione.</p>
      <form data-endpoint="/v1/candidate/matches">
        <div class="controls"><label>ID match run<input name="run_id" maxlength="180" required></label>
        <label>ID candidato<input name="claim_candidate_id" maxlength="180" required></label>
        <button type="submit">Ispeziona match</button></div>
      </form>
      <form data-endpoint="/v1/candidate/review-readiness">
        <div class="controls"><label>ID match run<input name="run_id" maxlength="180" required></label>
        <label>ID candidato<input name="claim_candidate_id" maxlength="180" required></label>
        <button type="submit">Verifica attualità e blocchi promozione</button></div>
      </form>
      <h2>Richiesta di revisione già registrata</h2>
      <p>Rilegge unicamente un handoff persistito su disco e configurato dall'operatore. Non è una decisione umana e non rivalida la sua attualità; identificativi del revisore esclusi.</p>
      <form data-endpoint="/v1/candidate/handoff-receipt">
        <div class="controls"><label>ID handoff<input name="handoff_id" maxlength="81" required></label>
        <label>ID match run<input name="run_id" maxlength="180" required></label>
        <label>ID candidato<input name="claim_candidate_id" maxlength="180" required></label>
        <button type="submit">Rileggi richiesta persistita</button></div>
      </form>
    </section>
    <section class="pane" id="captures" hidden>
      <h2>Confronto catture</h2><p>Due hash esatti dello stesso Content, in ordine temporale delle osservazioni persistite (precedente, poi successiva). I risultati sono metadati, non attestazioni di diritti o anteprime di testo.</p>
      <form data-endpoint="/v1/capture/compare">
        <div class="controls"><label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>SHA-256 precedente<input name="earlier_hash" minlength="64" maxlength="64" required></label>
        <label>SHA-256 successivo<input name="later_hash" minlength="64" maxlength="64" required></label>
        <button type="submit">Confronta</button></div>
      </form>
      <div id="capture-links" role="group" aria-label="Catture confrontate: ispeziona selettori"></div>
      <p id="capture-selector-diff-summary" role="status" aria-live="polite">Nessun confronto di selettori eseguito.</p>
      <h2>Selettori dei passaggi</h2>
      <p>Passaggi scritti collegati a una singola versione di cattura. Gli eventuali segmenti multimediali appartengono al Content logico e non vengono attribuiti artificialmente a questa versione.</p>
      <form data-endpoint="/v1/capture/passages">
        <div class="controls"><label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>SHA-256 cattura<input name="capture_hash" minlength="64" maxlength="64" required></label>
        <label>Limite (1–20)<input name="limit" type="number" min="1" max="20" value="20" required></label>
        <label>Dopo Passage ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Mostra selettori</button></div>
      </form>
      <div id="capture-passage-links" role="group" aria-label="Passaggi selezionabili dalla cattura"></div>
      <h2>Candidati collegati a un Passage</h2>
      <p>Richiede un Content incluso e un Passage persistito. Mostra solo identificativi e stati: una proposta o un claim storico non implicano approvazione editoriale.</p>
      <form data-endpoint="/v1/collections/passage-candidates">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" required></label>
        <label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Passage ID<input name="passage_id" maxlength="180" required></label>
        <label>Limite (1–20)<input name="limit" type="number" min="1" max="20" value="20" required></label>
        <label>Dopo Statement Candidate ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Cerca candidati di questo Passage</button></div>
      </form>
      <div id="passage-candidate-links" role="group" aria-label="Statement, Claim Candidate e Claim storici collegati"></div>
      <p id="passage-candidate-summary" role="status" aria-live="polite">Nessun Passage selezionato.</p>
      <h2>Passaggio multimediale e segmento canonico</h2>
      <p>Verifica il collegamento persistito tra candidato, Passage multimediale e intervallo del segmento canonico. Nessun testo, identificazione certa del parlante, riproduzione media o permesso di pubblicazione.</p>
      <form data-endpoint="/v1/media/segment">
        <div class="controls"><label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Statement Candidate ID<input name="statement_candidate_id" maxlength="180" required></label>
        <label>Passage ID<input name="passage_id" maxlength="180" required></label>
        <button type="submit">Localizza segmento</button></div>
      </form>
      <h2>Contesto cattura e durata di un segmento multimediale</h2>
      <p>Seleziona la cattura e il Passage canonico persistiti dello stesso Content: vengono mostrati intervallo, conservazione e blocchi, NON una falsa appartenenza del segmento alla cattura. Nessun seek o riproduzione consentiti senza un legame e diritti attestati.</p>
      <form data-endpoint="/v1/media/capture-context">
        <div class="controls"><label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Statement Candidate ID<input name="statement_candidate_id" maxlength="180" required></label>
        <label>Passage ID<input name="passage_id" maxlength="180" required></label>
        <label>Capture ID<input name="capture_id" maxlength="180" required></label>
        <label>Capture SHA-256<input name="capture_sha256" minlength="64" maxlength="64" required></label>
        <button type="submit">Confronta timeline e conservazione</button></div>
      </form>
      <p id="media-capture-context-summary" role="status" aria-live="polite">Nessun contesto cattura verificato.</p>
      <h2>Ricevuta persistita Capture → Segment (metadati soltanto)</h2>
      <p>L'attestazione locale conserva Capture SHA, segmento e revisioni di revoca. È una dichiarazione di provenienza da verificare indipendentemente: non concede diritti o riproduzione e non espone il media.</p>
      <form data-endpoint="/v1/media/binding" aria-describedby="media-binding-summary">
        <div class="controls"><label>Binding ID<input name="binding_id" maxlength="180" required></label>
        <button type="submit">Rileggi stato corrente e revoche</button></div>
      </form>
      <p id="media-binding-summary" role="status" aria-live="polite">Nessun binding verificato.</p>
      <p id="media-locator" role="status" aria-live="polite">Nessun segmento selezionato.</p>
    </section>
    <section class="pane" aria-labelledby="esito">
      <h2 id="esito">Esito</h2><p role="status" id="status" class="notice" aria-live="polite">Nessuna richiesta eseguita.</p>
      <pre id="results" aria-label="Risultati del runtime privato">Solo dati di sola lettura</pre>
    </section>
  </main>
  <script nonce="__NONCE__">
    'use strict';
    const token = document.getElementById('token');
    const results = document.getElementById('results');
    const status = document.getElementById('status');
    const collectionForm = document.querySelector('form[data-endpoint="/v1/collections/list"]');
    const workloadForm = document.querySelector('form[data-endpoint="/v1/operator/workload"]');
    const workloadSummary = document.getElementById('workload-summary');
    const workloadLinks = document.getElementById('workload-links');
    const collectionLinks = document.getElementById('collection-links');
    const collectionListSummary = document.getElementById('collection-list-summary');
    const collectionNavigationForm = document.querySelector('form[data-endpoint="/v1/collections/navigate"]');
    const collectionNavigationLinks = document.getElementById('collection-navigation-links');
    const collectionNavigationSummary = document.getElementById('collection-navigation-summary');
    const collectionNavigationHeading = document.getElementById('collection-navigation-heading');
    const collectionMembersForm = document.querySelector('form[data-endpoint="/v1/collections/members"]');
    const collectionMemberSummary = document.getElementById('collection-member-summary');
    const memberLinks = document.getElementById('member-links');
    const claimLinks = document.getElementById('claim-links');
    const captureLinks = document.getElementById('capture-links');
    const captureSelectorDiffSummary = document.getElementById('capture-selector-diff-summary');
    const capturePassageLinks = document.getElementById('capture-passage-links');
    const passageCandidateLinks = document.getElementById('passage-candidate-links');
    const passageCandidateSummary = document.getElementById('passage-candidate-summary');
    const collectionCaptureLinks = document.getElementById('collection-capture-links');
    const collectionCaptureSummary = document.getElementById('collection-capture-summary');
    const collectionCaptureForm = document.querySelector('form[data-endpoint="/v1/collections/captures"]');
    const lineageForm = document.querySelector('form[data-endpoint="/v1/collections/passage-lineage"]');
    const lineageLinks = document.getElementById('collection-lineage-links');
    const lineageSummary = document.getElementById('collection-lineage-summary');
    const lineageHeading = document.getElementById('collection-lineage-heading');
    const lineageInspector = document.getElementById('collection-lineage-inspector');
    const candidateHeading = document.getElementById('collection-candidate-heading');
    const candidateDetail = document.getElementById('collection-candidate-detail');
    const decisionForm = document.querySelector('form[data-endpoint="/v1/candidate/decision-receipt"]');
    const decisionSummary = document.getElementById('collection-decision-summary');
    const candidateWriteForm = document.querySelector('form[data-endpoint="/v1/candidate/decision-annotate"]');
    const candidateWriteSummary = document.getElementById('candidate-write-summary');
    const captureQueueForm = document.querySelector('form[data-endpoint="/v1/discovery/capture-queue"]');
    const captureQueueLinks = document.getElementById('capture-queue-links');
    const captureQueueSummary = document.getElementById('capture-queue-summary');
    const inboxForm = document.querySelector('form[data-endpoint="/v1/discovery/inbox"]');
    const inboxAnnotationSummary = document.getElementById('inbox-annotation-summary');
    const inboxAnnotationLinks = document.getElementById('inbox-annotation-links');
    const triageHistoryForm = document.querySelector('form[data-endpoint="/v1/discovery/triage-history"]');
    const triageWriteForm = document.querySelector('form[data-endpoint="/v1/discovery/triage-annotate"]');
    const triageWriteSummary = document.getElementById('triage-write-summary');
    const compareForm = document.querySelector('form[data-endpoint="/v1/capture/compare"]');
    const corpusForm = document.querySelector('form[data-endpoint="/v1/corpus/search"]');
    const corpusList = document.getElementById('corpus-list');
    const corpusLinks = document.getElementById('corpus-links');
    const corpusSummary = document.getElementById('corpus-summary');
    const corpusInspector = document.getElementById('corpus-inspector');
    const corpusReferences = document.getElementById('corpus-references');
    const corpusInspectorTitle = document.getElementById('corpus-inspector-title');
    const corpusBack = document.getElementById('corpus-back');
    const corpusSourceJump = document.getElementById('corpus-source-jump');
    const corpusJumpStatus = document.getElementById('corpus-jump-status');
    const SEARCH_KINDS = new Set(['CONTENT', 'PASSAGE', 'STATEMENT_CANDIDATE',
      'CLAIM_CANDIDATE', 'ATOMIC_CLAIM', 'PERSON', 'ORGANIZATION', 'TOPIC', 'EVENT', 'COLLECTION']);
    const SAFE_REF = /^[A-Za-z0-9_:/.-]{1,180}$/;
    const SAFE_SHA256 = /^[0-9a-f]{64}$/;
    let selectedCorpusButton = null;
    let selectedCorpusReference = null;
    const mediaLocator = document.getElementById('media-locator');
    const capturePassageForm = document.querySelector('form[data-endpoint="/v1/capture/passages"]');
    const passageCandidateForm = document.querySelector('form[data-endpoint="/v1/collections/passage-candidates"]');
    const mediaForm = document.querySelector('form[data-endpoint="/v1/media/segment"]');
    const mediaContextForm = document.querySelector('form[data-endpoint="/v1/media/capture-context"]');
    const mediaContextSummary = document.getElementById('media-capture-context-summary');
    const mediaBindingForm = document.querySelector('form[data-endpoint="/v1/media/binding"]');
    const mediaBindingSummary = document.getElementById('media-binding-summary');
    const memberDetailForm = document.querySelector('form[data-endpoint="/v1/collections/member"]');
    const provenanceForm = document.querySelector('form[data-endpoint="/v1/collections/claim-provenance"]');
    const panels = document.querySelectorAll('main > section[id]');
    let requestGeneration = 0;
    let activeRequest = null;
    let scopedCaptureReference = null;
    function invalidateRequest() {
      requestGeneration += 1;
      if (activeRequest) activeRequest.abort();
      activeRequest = null;
    }
    function clearCorpusResults(clearForm) {
      corpusLinks.replaceChildren();
      corpusReferences.replaceChildren();
      corpusInspector.hidden = true;
      corpusList.hidden = false;
      corpusSummary.textContent = 'Nessuna ricerca eseguita.';
      selectedCorpusButton = null;
      selectedCorpusReference = null;
      corpusSourceJump.hidden = true;
      corpusJumpStatus.textContent = '';
      if (clearForm) {
        for (const field of corpusForm.querySelectorAll('input,select')) {
          if (field.name === 'limit') field.value = '20';
          else field.value = '';
        }
      }
    }
    function safeSearchData(receipt) {
      if (!receipt || receipt.contract_version !== 'studio-local-readonly-api-v1') return null;
      const data = receipt.data;
      if (!data || data.contract_version !== 'studio-operator-search-v1'
          || data.private_only !== true || data.publication_authority !== false
          || !SAFE_SHA256.test(data.query_sha256) || !Array.isArray(data.results)
          || !Number.isInteger(data.result_count) || data.result_count !== data.results.length
          || data.results.length > 20) return null;
      const keys = ['id', 'kind', 'content_id', 'passage_id', 'source_id'];
      for (const record of data.results) {
        if (!record || typeof record !== 'object' || Array.isArray(record)
            || Object.keys(record).some(key => !keys.includes(key))
            || !SEARCH_KINDS.has(record.kind) || !SAFE_REF.test(record.id)
            || ['content_id', 'passage_id', 'source_id'].some(
              key => record[key] !== null && record[key] !== undefined && !SAFE_REF.test(record[key])
            )) return null;
      }
      return data;
    }
    function inspectCorpusResult(record, button) {
      if (!corpusLinks.contains(button)) return;
      selectedCorpusButton = button;
      corpusReferences.replaceChildren();
      for (const [label, value] of [
        ['Tipo', record.kind], ['ID', record.id], ['Content ID', record.content_id],
        ['Passage ID', record.passage_id], ['Source ID', record.source_id],
      ]) {
        if (value === null || value === undefined) continue;
        const title = document.createElement('dt');
        title.textContent = label;
        const ref = document.createElement('dd');
        ref.textContent = value;
        corpusReferences.append(title, ref);
      }
      const collection = corpusForm.elements.namedItem('collection_id').value;
      selectedCorpusReference = SAFE_REF.test(collection) && SAFE_REF.test(record.content_id)
        && SAFE_REF.test(record.source_id)
        ? {collection_id: collection, content_id: record.content_id, source_id: record.source_id}
        : null;
      corpusSourceJump.hidden = !selectedCorpusReference;
      corpusJumpStatus.textContent = '';
      corpusList.hidden = true;
      corpusInspector.hidden = false;
      corpusInspectorTitle.focus();
    }
    corpusSourceJump.addEventListener('click', async () => {
      if (!selectedCorpusReference || !/^[0-9a-f]{64,128}$/.test(token.value)) return;
      invalidateRequest();
      const generation = requestGeneration;
      const selected = {...selectedCorpusReference};
      const controller = new AbortController();
      activeRequest = controller;
      corpusJumpStatus.textContent = 'Controllo collegamento persistito in corso…';
      try {
        const response = await fetch('/v1/collections/member', {
          method: 'POST', credentials: 'omit', redirect: 'error',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token.value},
          signal: controller.signal,
          body: JSON.stringify({collection_id: selected.collection_id, content_id: selected.content_id, limit: 1}),
        });
        const receipt = await response.json();
        if (generation !== requestGeneration) return;
        activeRequest = null;
        const member = receipt?.data;
        if (!response.ok || receipt.contract_version !== 'studio-local-readonly-api-v1'
            || member?.private_only !== true || member?.publication_authority !== false
            || member?.collection_id !== selected.collection_id
            || member?.content_id !== selected.content_id
            || member?.source_id !== selected.source_id || member?.source_exists !== true) {
          corpusJumpStatus.textContent = 'Collegamento non verificabile: nessun dettaglio mostrato.';
          return;
        }
        corpusJumpStatus.textContent = 'Collegamento persistito verificato: raccolta '
          + selected.collection_id + ' · Content ' + selected.content_id
          + ' · sorgente ' + selected.source_id
          + '. L’identità della sorgente non conferisce diritti di riproduzione o pubblicazione.';
      } catch (_) {
        if (generation !== requestGeneration) return;
        activeRequest = null;
        corpusJumpStatus.textContent = 'Collegamento non disponibile.';
      }
    });
    corpusBack.addEventListener('click', () => {
      corpusInspector.hidden = true;
      corpusList.hidden = false;
      corpusReferences.replaceChildren();
      corpusJumpStatus.textContent = '';
      if (selectedCorpusButton && corpusLinks.contains(selectedCorpusButton)) selectedCorpusButton.focus();
      else corpusForm.elements.namedItem('query').focus();
    });
    function showCorpusResults(data) {
      clearCorpusResults(false);
      corpusSummary.textContent = data.result_count === 0
        ? 'Nessun riferimento corrispondente. La ricerca lessicale non ha prodotto risultati.'
        : data.result_count + ' riferimenti privati. Seleziona un risultato per ispezionare gli ID.';
      for (const record of data.results) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = record.kind + ' · ' + record.id;
        button.addEventListener('click', () => inspectCorpusResult(record, button));
        corpusLinks.append(button);
      }
    }
    function hidePrivateLocators() {
      clearCorpusResults(true);
      memberLinks.replaceChildren();
      collectionLinks?.replaceChildren();
      workloadLinks?.replaceChildren();
      if (workloadSummary) workloadSummary.textContent = 'Nessuna coda operativa letta.';
      if (workloadForm) {
        workloadForm.elements.namedItem('collection_id').value = '';
        workloadForm.elements.namedItem('limit').value = '10';
        workloadForm.elements.namedItem('after').value = '';
      }
      collectionNavigationLinks?.replaceChildren();
      if (collectionNavigationSummary) collectionNavigationSummary.textContent = 'Nessuna navigazione caricata.';
      if (collectionListSummary) collectionListSummary.textContent = 'Nessuna raccolta selezionata.';
      if (collectionMemberSummary) collectionMemberSummary.textContent = 'Nessun Content caricato.';
      claimLinks.replaceChildren();
      captureLinks.replaceChildren();
      captureSelectorDiffSummary.textContent = 'Nessun confronto di selettori eseguito.';
      capturePassageLinks.replaceChildren();
      passageCandidateLinks.replaceChildren();
      passageCandidateSummary.textContent = 'Nessun Passage selezionato.';
      scopedCaptureReference = null;
      collectionCaptureLinks.replaceChildren();
      collectionCaptureSummary.textContent = 'Nessun Content selezionato per le catture.';
      lineageLinks?.replaceChildren();
      if (lineageSummary) lineageSummary.textContent = 'Nessun Passage scritto selezionato.';
      if (lineageInspector) lineageInspector.hidden = true;
      if (candidateDetail) candidateDetail.textContent = '';
      if (decisionSummary) decisionSummary.textContent = 'Nessuna ricevuta letta.';
      if (candidateWriteSummary) candidateWriteSummary.textContent = 'Nessuna intenzione candidata inviata.';
      if (decisionForm) {
        for (const field of decisionForm.querySelectorAll('input,select')) field.value = '';
      }
      if (candidateWriteForm) {
        for (const field of candidateWriteForm.querySelectorAll('input,select,textarea')) {
          if (field.name === 'expected_revision') field.value = '0';
          else if (field.name === 'decision') field.value = 'HOLD';
          else field.value = '';
        }
      }
      captureQueueLinks?.replaceChildren();
      inboxAnnotationLinks?.replaceChildren();
      if (inboxAnnotationSummary) inboxAnnotationSummary.textContent = 'Nessun Hit caricato.';
      if (captureQueueSummary) captureQueueSummary.textContent = 'Nessuna coda letta.';
      if (triageWriteSummary) triageWriteSummary.textContent = 'Nessuna annotazione inviata. Il server predefinito è di sola lettura.';
      if (triageWriteForm) {
        for (const field of triageWriteForm.querySelectorAll('input,select')) {
          if (field.name === 'expected_revision') field.value = '0';
          else if (field.name === 'decision') field.value = 'NEEDS_REVIEW';
          else field.value = '';
        }
      }
      for (const form of [lineageForm, captureQueueForm]) {
        if (!form) continue;
        for (const field of form.querySelectorAll('input,select')) {
          field.value = field.name === 'limit' ? '20' : '';
        }
      }
      if (collectionNavigationForm) collectionNavigationForm.elements.namedItem('after_content_id').value = '';
      mediaLocator.textContent = 'Nessun segmento selezionato.';
      if (mediaContextSummary) mediaContextSummary.textContent = 'Nessun contesto cattura verificato.';
      if (mediaBindingSummary) mediaBindingSummary.textContent = 'Nessun binding verificato.';
      if (mediaBindingForm) mediaBindingForm.elements.namedItem('binding_id').value = '';
    }
    document.getElementById('clear').addEventListener('click', () => {
      token.value = '';
      invalidateRequest();
      hidePrivateLocators();
      results.textContent = 'Token cancellato dalla pagina.';
      status.textContent = 'Accesso disconnesso.';
    });
    token.addEventListener('input', () => {
      // Replacing a token changes the operator session even before a request
      // completes; never retain private rows from the previous credential.
      invalidateRequest();
      hidePrivateLocators();
      results.textContent = 'Nessun risultato per il token corrente.';
      status.textContent = 'Token aggiornato: seleziona di nuovo il workspace.';
    });
    for (const button of document.querySelectorAll('[data-panel]')) {
      button.addEventListener('click', () => {
        invalidateRequest();
        for (const other of document.querySelectorAll('[data-panel]')) {
          other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
        }
        for (const panel of panels) panel.hidden = panel.id !== button.dataset.panel;
        results.textContent = 'Nessuna richiesta per il workspace selezionato.';
        status.textContent = 'Pronto per una query.';
        hidePrivateLocators();
      });
    }
    for (const form of document.querySelectorAll('form[data-endpoint]')) {
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        invalidateRequest();
        if (!/^[0-9a-f]{64,128}$/.test(token.value)) {
          hidePrivateLocators();
          results.textContent = 'Nessun risultato.';
          status.textContent = 'Token mancante o non valido.';
          return;
        }
        const generation = requestGeneration;
        const controller = new AbortController();
        activeRequest = controller;
        const data = {};
        for (const [key, value] of new FormData(form).entries()) {
          if (value === '') continue;
          if (key === 'kind') data.kinds = [value];
          else if (key === 'hit_ids_csv') data.hit_ids = value.split(',').map(item => item.trim());
          else if (key === 'from_date') data.from_at = value + 'T00:00:00Z';
          else if (key === 'to_date') data.to_at = value + 'T23:59:59Z';
          else if (key === 'check_worthy') data.check_worthy = value === 'true';
          else if (key === 'review_event_json') {
            try {
              const eventData = JSON.parse(value);
              if (!eventData || typeof eventData !== 'object' || Array.isArray(eventData)) throw Error();
              data.review_event = eventData;
            } catch {
              status.textContent = 'ReviewEvent JSON non valido: nessuna richiesta inviata.';
              return;
            }
          }
          else data[key] = key === 'limit' || key === 'after_revision' || key === 'expected_revision'
            ? Number(value) : ['confirm_private_annotation','confirm_private_decision'].includes(key)
            ? value === 'true' : value;
        }
        status.textContent = 'Richiesta locale in corso…';
        results.textContent = 'Nessun risultato ancora disponibile.';
        if (form === corpusForm) clearCorpusResults(false);
        if (form === collectionForm) {
          collectionLinks.replaceChildren();
          collectionListSummary.textContent = 'Caricamento delle raccolte…';
        }
        if (form === workloadForm) {
          workloadLinks.replaceChildren();
          workloadSummary.textContent = 'Carico e diritti correnti in lettura…';
        }
        if (form === collectionNavigationForm) {
          collectionNavigationLinks.replaceChildren();
          collectionNavigationSummary.textContent = 'Verifica di un solo snapshot PostgreSQL in corso…';
        }
        if (form.dataset.endpoint === '/v1/collections/members') {
          memberLinks.replaceChildren();
          claimLinks.replaceChildren();
          if (collectionMemberSummary) collectionMemberSummary.textContent = 'Caricamento dei Content inclusi…';
        }
        if (form.dataset.endpoint === '/v1/collections/member') {
          claimLinks.replaceChildren();
          collectionCaptureLinks.replaceChildren();
          collectionCaptureSummary.textContent = 'Caricamento del Content selezionato.';
        }
        if (form === collectionCaptureForm) {
          collectionCaptureLinks.replaceChildren();
          collectionCaptureSummary.textContent = 'Ricerca versioni in corso…';
        }
        if (form === lineageForm) {
          lineageLinks.replaceChildren();
          lineageInspector.hidden = true;
          candidateDetail.textContent = '';
          lineageSummary.textContent = 'Controllo dei collegamenti persistiti in corso…';
        }
        if (form === decisionForm) {
          decisionSummary.textContent = 'Verifica ricevuta e fonte corrente in corso…';
        }
        if (form === candidateWriteForm) {
          candidateWriteSummary.textContent = 'Verifica della firma esterna e del CAS PostgreSQL in corso…';
        }
        if (form === captureQueueForm) {
          captureQueueLinks.replaceChildren();
          captureQueueSummary.textContent = 'Lettura della coda in corso…';
        }
        if (form === inboxForm) {
          inboxAnnotationLinks.replaceChildren();
          inboxAnnotationSummary.textContent = 'Lettura di stato e revisioni Discovery in corso…';
        }
        if (form === triageWriteForm) {
          triageWriteSummary.textContent = 'Invio al servizio privato con controllo CAS e ricevuta pre-emessa…';
        }
        if (form.dataset.endpoint === '/v1/capture/compare') {
          captureLinks.replaceChildren();
          captureSelectorDiffSummary.textContent = 'Confronto selettori in corso…';
        }
        if (form === capturePassageForm) {
          capturePassageLinks.replaceChildren();
          passageCandidateLinks.replaceChildren();
          passageCandidateSummary.textContent = 'Ricerca selettori in corso…';
        }
        if (form === passageCandidateForm) {
          passageCandidateLinks.replaceChildren();
          passageCandidateSummary.textContent = 'Ricerca candidati in corso…';
        }
        if (form.dataset.endpoint === '/v1/media/segment') {
          mediaLocator.textContent = 'Intervallo canonico non verificato.';
        }
        if (form === mediaContextForm) mediaContextSummary.textContent = 'Verifica legami persistiti e durata in corso…';
        if (form === mediaBindingForm) mediaBindingSummary.textContent = 'Rilettura della revoca corrente in corso…';
        try {
          const response = await fetch(form.dataset.endpoint, {
            method: 'POST', credentials: 'omit', redirect: 'error',
            headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token.value},
            signal: controller.signal,
            body: JSON.stringify(data),
          });
          const receipt = await response.json();
          if (generation !== requestGeneration) return;
          activeRequest = null;
          if (form === corpusForm) {
            const safe = response.ok ? safeSearchData(receipt) : null;
            if (!safe) {
              clearCorpusResults(false);
              status.textContent = 'Ricerca non disponibile o risposta non conforme.';
              results.textContent = 'Nessun riferimento visualizzabile.';
            } else {
              showCorpusResults(safe);
              status.textContent = 'Ricerca lessicale privata completata.';
              results.textContent = 'Solo riferimenti disponibili nel riquadro Corpus.';
            }
            return;
          }
          if (form === workloadForm) {
            results.textContent = 'Solo ID e contatori verificati; nessuna fonte o decisione privata.';
            const load = receipt?.data;
            const allowRef = value => typeof value === 'string' && SAFE_REF.test(value);
            const count = value => Number.isSafeInteger(value) && value >= 0 && value <= 500000;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && load?.version === 'studio-operator-workload-pg-v1'
              && load.collection_id === data.collection_id
              && ['ACTIVE','PAUSED','ARCHIVED'].includes(load.collection_state)
              && load.dispatch_authorized === false && load.publication_authority === false
              && load.image_approval_authority === false
              && load.text_review_authority === false && load.source_rights_attested === false
              && ['total_members','blocked_members','review_only_members','capture_count',
                  'passage_count','statement_candidate_count','claim_candidate_count']
                  .every(key => count(load[key]))
              && load.total_members <= 500
              && load.blocked_members + load.review_only_members === load.total_members
              && Array.isArray(load.rows) && load.rows.length <= data.limit
              && load.rows.every((item,i) => allowRef(item.content_id)
                && (item.capture_id == null || allowRef(item.capture_id))
                && ['BLOCKED','REVIEW_ONLY'].includes(item.state)
                && allowRef(item.reason)
                && count(item.capture_count) && count(item.passage_count)
                && count(item.statement_candidates) && count(item.claim_candidates)
                && (i === 0 || item.content_id > load.rows[i-1].content_id))
              && Array.isArray(load.blocked_queue)
              && load.blocked_queue.length <= load.rows.length
              && load.blocked_queue.every(item => allowRef(item.content_id)
                && allowRef(item.reason) && allowRef(item.next_action)
                && load.rows.some(row => row.content_id === item.content_id
                  && row.state === 'BLOCKED' && row.reason === item.reason))
              && (load.next_cursor == null ||
                typeof load.next_cursor === 'string' &&
                /^[A-Za-z0-9_-]{20,2048}$/.test(load.next_cursor) &&
                load.rows.length === data.limit);
            if (!valid) {
              workloadSummary.textContent = 'Carico non disponibile o snapshot non verificabile.';
              status.textContent = 'Coda privata non verificabile.';
              return;
            }
            workloadSummary.textContent = load.total_members + ' Content inclusi; '
              + load.blocked_members + ' bloccati e ' + load.review_only_members
              + ' da ispezionare; ' + load.capture_count + ' Capture e '
              + load.passage_count + ' Passage. Nessun permesso di pubblicazione.';
            for (const item of load.rows) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = item.content_id + ' · ' + item.state + ' · ' + item.reason
                + ' · ' + item.passage_count + ' Passage · ' + item.claim_candidates + ' Claim Candidate';
              button.addEventListener('click', () => {
                if (!workloadLinks.contains(button)) return;
                collectionCaptureForm.elements.namedItem('collection_id').value = load.collection_id;
                collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                collectionCaptureForm.elements.namedItem('after_id').value = '';
                collectionCaptureForm.requestSubmit();
              });
              workloadLinks.append(button);
            }
            if (load.next_cursor) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva (stesso snapshot corrente)';
              more.addEventListener('click', () => {
                if (!workloadLinks.contains(more)) return;
                workloadForm.elements.namedItem('after').value = load.next_cursor;
                workloadForm.requestSubmit();
              });
              workloadLinks.append(more);
            }
            status.textContent = 'Carico privato letto; seleziona un Content per l’ispezione.';
            return;
          }
          if (form === collectionForm) {
            results.textContent = 'Solo ID persistiti della pagina Collections.';
            const listing = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && listing?.contract_version === 'studio-operator-queues-v1'
              && listing.private_only === true && listing.publication_authority === false
              && Array.isArray(listing.results) && listing.results.length <= data.limit
              && listing.results.every(item => SAFE_REF.test(item.id)
                && SAFE_REF.test(item.state) && Number.isSafeInteger(item.included_content_count)
                && item.included_content_count >= 0)
              && (listing.next_after_id == null || (SAFE_REF.test(listing.next_after_id)
                && listing.results.length === data.limit
                && listing.next_after_id === listing.results.at(-1)?.id));
            if (!valid) {
              status.textContent = 'Raccolte non verificabili.';
              collectionListSummary.textContent = 'Risposta non conforme: nessuna raccolta visualizzabile.';
              return;
            }
            status.textContent = 'Raccolte persistite caricate.';
            collectionListSummary.textContent = listing.results.length + ' raccolte in questa pagina. Seleziona una raccolta per vedere i Content inclusi.';
            for (const item of listing.results) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = 'Collection ' + item.id + ' · ' + item.state
                + ' · ' + item.included_content_count + ' Content inclusi';
              button.addEventListener('click', () => {
                if (!collectionLinks.contains(button)) return;
                collectionMembersForm.elements.namedItem('collection_id').value = item.id;
                collectionMembersForm.elements.namedItem('after_id').value = '';
                collectionMembersForm.requestSubmit();
              });
              collectionLinks.append(button);
            }
            if (listing.next_after_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva delle raccolte';
              more.addEventListener('click', () => {
                collectionForm.elements.namedItem('after_id').value = listing.next_after_id;
                collectionForm.requestSubmit();
              });
              collectionLinks.append(more);
            }
            return;
          }
          if (form === collectionNavigationForm) {
            results.textContent = 'Navigazione privata con soli riferimenti validati.';
            const tree = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && tree?.contract_version === 'studio-collection-navigation-v1'
              && tree.private_only === true && tree.read_only === true
              && tree.publication_authority === false && tree.rights_clearance === false
              && tree.review_authority === false && tree.collection_id === data.collection_id
              && SAFE_REF.test(tree.collection_state)
              && Array.isArray(tree.members) && tree.members.length <= data.limit
              && tree.members.every(item =>
                SAFE_REF.test(item.content_id) && (item.source_id === null || SAFE_REF.test(item.source_id))
                && item.source_exists === Boolean(item.source_id)
                && SAFE_REF.test(item.rights_status) && SAFE_REF.test(item.processing_status)
                && Number.isSafeInteger(item.capture_count) && item.capture_count >= 0
                && item.source_preview_authorized === false && item.review_authority === false
                && Array.isArray(item.blockers) && item.blockers.every(code => SAFE_REF.test(code))
                && (item.latest_capture == null ? item.capture_count === 0
                  : SAFE_REF.test(item.latest_capture.id)
                    && SAFE_SHA256.test(item.latest_capture.content_sha256)
                    && SAFE_REF.test(item.latest_capture.status)
                    && SAFE_REF.test(item.latest_capture.hold_status)
                    && SAFE_REF.test(item.latest_capture.rights_status)
                    && Number.isSafeInteger(item.latest_capture.passage_count)
                    && typeof item.latest_capture.passages_truncated === 'boolean'
                    && Array.isArray(item.latest_capture.passages)
                    && item.latest_capture.passages.length <= 3
                    && item.latest_capture.passage_count >= item.latest_capture.passages.length
                    && item.latest_capture.passages.every(passage =>
                      SAFE_REF.test(passage.id) && SAFE_SHA256.test(passage.text_sha256)
                      && ['TEXT_POSITION','PAGE_RANGE'].includes(passage.selector_type)
                      && Number.isSafeInteger(passage.candidate_count)
                      && passage.candidate_count >= 0
                      && (passage.candidate_count === 0 ? passage.first_candidate_id === null
                        : SAFE_REF.test(passage.first_candidate_id)))))
              && (tree.next_after_content_id == null
                ? tree.has_more === false
                : tree.has_more === true && tree.members.length === data.limit
                  && tree.next_after_content_id === tree.members.at(-1)?.content_id);
            if (!valid) {
              collectionNavigationLinks.replaceChildren();
              collectionNavigationSummary.textContent = 'Snapshot non conforme: nessun riferimento visualizzabile.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            collectionNavigationSummary.textContent = tree.members.length
              + ' Content inclusi, ' + tree.collection_state
              + '. Nessuna fonte riproducibile né revisione approvata.';
            for (const item of tree.members) {
              const parent = document.createElement('button');
              parent.type = 'button';
              parent.textContent = 'Content ' + item.content_id
                + ' · fonte ' + (item.source_id || 'non collegata')
                + ' · ' + item.capture_count + ' Capture'
                + ' · ' + item.blockers.join(', ');
              parent.addEventListener('click', () => {
                if (!collectionNavigationLinks.contains(parent)) return;
                collectionCaptureForm.elements.namedItem('collection_id').value = tree.collection_id;
                collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                collectionCaptureForm.elements.namedItem('after_id').value = '';
                collectionCaptureForm.requestSubmit();
              });
              collectionNavigationLinks.append(parent);
              const capture = item.latest_capture;
              if (!capture || !item.source_exists) continue;
              for (const passage of capture.passages) {
                const next = document.createElement('button');
                next.type = 'button';
                next.textContent = 'Capture ' + capture.id + ' → Passage ' + passage.id
                  + ' · ' + passage.candidate_count + ' Statement Candidate'
                  + ' · primo ' + (passage.first_candidate_id || 'assente');
                next.addEventListener('click', () => {
                  if (!collectionNavigationLinks.contains(next)) return;
                  scopedCaptureReference = {
                    collection_id: tree.collection_id, content_id: item.content_id,
                    capture_id: capture.id, capture_sha256: capture.content_sha256,
                    source_id: item.source_id,
                  };
                  lineageForm.elements.namedItem('collection_id').value = tree.collection_id;
                  lineageForm.elements.namedItem('content_id').value = item.content_id;
                  lineageForm.elements.namedItem('capture_id').value = capture.id;
                  lineageForm.elements.namedItem('passage_id').value = passage.id;
                  lineageForm.elements.namedItem('limit').value = '20';
                  lineageForm.elements.namedItem('after_statement_id').value = '';
                  lineageForm.requestSubmit();
                });
                collectionNavigationLinks.append(next);
              }
            }
            if (tree.next_after_content_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva dei Content inclusi';
              more.addEventListener('click', () => {
                collectionNavigationForm.elements.namedItem('after_content_id').value = tree.next_after_content_id;
                collectionNavigationForm.requestSubmit();
              });
              collectionNavigationLinks.append(more);
            }
            collectionNavigationHeading.focus();
            return;
          }
          if (form === decisionForm) {
            results.textContent = 'Solo stato e hash della ricevuta privata verificata.';
            const decision = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && decision?.contract_version === 'studio-candidate-decision-receipt-v1'
              && decision.private_only === true && decision.historical_only === true
              && decision.review_authority === false && decision.promotion_authority === false
              && decision.publication_authority === false && decision.rights_clearance === false
              && ['HOLD','REJECT','REVIEW_CREATE','REVIEW_LINK'].includes(decision.decision)
              && ['HISTORICAL_SOURCE_CURRENT','HISTORICAL_SOURCE_WITHDRAWN'].includes(decision.status)
              && Number.isSafeInteger(decision.revision) && decision.revision > 0
              && SAFE_SHA256.test(decision.receipt_sha256)
              && ['candidate_id','run_id','capture_id','passage_id','request_key'].every(
                name => decision[name] === data[name] && SAFE_REF.test(decision[name]));
            if (!valid) {
              decisionSummary.textContent = 'Ricevuta assente, non configurata o non verificabile.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            decisionSummary.textContent = 'Decisione ' + decision.decision
              + ' · revisione ' + decision.revision
              + ' · ricevuta SHA-256 ' + (decision.receipt_sha256 || 'non prodotta')
              + ' · ' + decision.status
              + '. Storico soltanto: nessuna promozione o pubblicazione autorizzata.';
            return;
          }
          if (form === candidateWriteForm) {
            results.textContent = 'Solo stato sanitizzato dell’intenzione privata firmata.';
            const decision = receipt?.data;
            const code = decision?.result_code;
            const confirmed = ['CREATED','REPLAY'].includes(code);
            const valid = receipt?.contract_version === 'studio-private-candidate-decision-api-v1'
              && decision?.contract_version === 'studio-private-candidate-decision-write-v1'
              && decision.private_only === true && decision.mutation_kind === 'REVIEW_INTENT_ONLY'
              && decision.candidate_id === data.candidate_id && decision.run_id === data.run_id
              && decision.capture_id === data.capture_id && decision.passage_id === data.passage_id
              && decision.decision === data.decision
              && decision.promoted === false && decision.promotion_authority === false
              && decision.publication_authority === false && decision.source_rights_approved === false
              && Number.isSafeInteger(decision.revision) && decision.revision >= 0
              && (confirmed ? SAFE_SHA256.test(decision.receipt_sha256)
                : decision.receipt_sha256 == null || SAFE_SHA256.test(decision.receipt_sha256))
              && ['CREATED','REPLAY','HELD_SOURCE','REVISION_CONFLICT','IDEMPOTENCY_CONFLICT'].includes(code)
              && response.ok === confirmed;
            if (!valid) {
              candidateWriteSummary.textContent = 'Intenzione non attestata. Nessun salvataggio confermato.';
              status.textContent = 'Writer non disponibile o firma/sorgente non verificabile.';
              return;
            }
            candidateWriteSummary.textContent = code + ' · revisione ' + decision.revision
              + ' · ricevuta SHA-256 ' + decision.receipt_sha256
              + '. Storico privato soltanto: nessun Claim creato o pubblicazione autorizzata.';
            if (confirmed) {
              decisionForm.elements.namedItem('candidate_id').value = data.candidate_id;
              decisionForm.elements.namedItem('run_id').value = data.run_id;
              decisionForm.elements.namedItem('capture_id').value = data.capture_id;
              decisionForm.elements.namedItem('passage_id').value = data.passage_id;
              decisionForm.elements.namedItem('request_key').value = data.request_key;
              status.textContent = 'Intenzione persistita: rileggi lo storico e i diritti correnti.';
            }
            return;
          }
          if (form === lineageForm) {
            // Never dump unvalidated data into the shared results panel.
            results.textContent = 'Solo riferimenti validati nel dettaglio della raccolta.';
            const match = receipt?.data;
            const scope = scopedCaptureReference;
            const validScope = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && match?.contract_version === 'studio-operator-queues-v1'
              && match.private_only === true && match.rights_clearance === false
              && match.review_authority_evaluated === false && match.publication_authority === false
              && match.collection_id === data.collection_id && match.content_id === data.content_id
              && match.capture_id === data.capture_id && match.passage?.id === data.passage_id
              && scope?.collection_id === data.collection_id && scope?.content_id === data.content_id
              && scope?.capture_id === data.capture_id
              && match.capture_sha256 === scope?.capture_sha256
              && SAFE_SHA256.test(match.capture_sha256) && SAFE_SHA256.test(match.passage?.text_sha256)
              && SAFE_REF.test(match.source_id) && match.source_id === scope.source_id
              && match.source_exists === true && SAFE_REF.test(match.rights_status)
              && SAFE_REF.test(match.processing_status) && SAFE_REF.test(match.collection_state)
              && ['TEXT_POSITION', 'PAGE_RANGE'].includes(match.passage?.selector_type)
              && Array.isArray(match.blockers) && match.blockers.every(code => SAFE_REF.test(code))
              && Array.isArray(match.candidates) && match.candidates.length <= data.limit;
            const validCandidates = validScope && match.candidates.every(candidate =>
              SAFE_REF.test(candidate.id) && SAFE_REF.test(candidate.status)
              && SAFE_SHA256.test(candidate.statement_text_hash)
              && candidate.review_authority_evaluated === false
              && Number.isInteger(candidate.claim_candidate_count)
              && candidate.claim_candidate_count >= 0
              && typeof candidate.claim_candidates_truncated === 'boolean'
              && Array.isArray(candidate.claim_candidates) && candidate.claim_candidates.length <= 5
              && candidate.claim_candidate_count >= candidate.claim_candidates.length
              && candidate.claim_candidates_truncated ===
                (candidate.claim_candidate_count > candidate.claim_candidates.length)
              && candidate.claim_candidates.every(claim =>
                SAFE_REF.test(claim.id) && SAFE_REF.test(claim.status)
                && claim.promotion_authority_evaluated === false
                && (claim.status === 'PROMOTED'
                  ? SAFE_REF.test(claim.recorded_promoted_claim_id)
                    && SAFE_REF.test(claim.promotion_receipt_id)
                  : !claim.recorded_promoted_claim_id && !claim.promotion_receipt_id)));
            const validCursor = validScope && (match.next_after_statement_id == null
              || (match.candidates.length === data.limit
                  && SAFE_REF.test(match.next_after_statement_id)
                  && match.next_after_statement_id === match.candidates.at(-1)?.id
                  && (!data.after_statement_id || match.next_after_statement_id > data.after_statement_id)));
            if (!validCandidates || !validCursor) {
              status.textContent = 'Dati non verificabili.';
              lineageSummary.textContent = 'Collegamento non verificabile o risposta non conforme.';
              return;
            }
            status.textContent = 'Collegamenti persistiti recuperati, senza approvazione.';
            const passage = match.passage;
            const position = passage.selector_type === 'TEXT_POSITION'
              ? 'caratteri ' + passage.start_char + '–' + passage.end_char
              : 'pagine ' + passage.page_start + '–' + passage.page_end;
            const validPosition = passage.selector_type === 'TEXT_POSITION'
              ? Number.isInteger(passage.start_char) && passage.start_char >= 0
                && Number.isInteger(passage.end_char) && passage.end_char > passage.start_char
              : Number.isInteger(passage.page_start) && passage.page_start >= 1
                && Number.isInteger(passage.page_end) && passage.page_end >= passage.page_start;
            if (!validPosition) {
              lineageSummary.textContent = 'Selettore scritto non conforme.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            lineageSummary.textContent = 'Collection ' + match.collection_id + ' · Content ' + match.content_id
              + ' · fonte ' + match.source_id + ' · Capture ' + match.capture_id
              + ' · Passage ' + passage.id + ' (' + position + ') · diritti '
              + match.rights_status + ' · blocchi: ' + match.blockers.join(', ')
              + ' · pagina di ' + match.candidates.length
              + ' Statement. Revisione e pubblicazione non autorizzate.';
            for (const candidate of match.candidates) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = 'Statement ' + candidate.id + ' · ' + candidate.status
                + ' · Claim Candidate ' + (candidate.claim_candidates.map(claim =>
                  claim.id + ' (' + claim.status + ')'
                  + (claim.status === 'PROMOTED' ? ' → Claim ' + claim.recorded_promoted_claim_id : '')
                ).join(', ') || 'nessuno')
                + (candidate.claim_candidates_truncated ? ' · altri Claim Candidate non caricati' : '');
              button.addEventListener('click', () => {
                if (!lineageLinks.contains(button)) return;
                candidateDetail.textContent = 'Statement ' + candidate.id
                  + ' · hash ' + candidate.statement_text_hash
                  + ' · ' + candidate.claim_candidate_count + ' Claim Candidate persistiti'
                  + ' · ricevute promozione: ' + (candidate.claim_candidates
                    .filter(claim => claim.status === 'PROMOTED')
                    .map(claim => claim.promotion_receipt_id).join(', ') || 'nessuna')
                  + '. Stato registrato; nessuna autorità di revisione o pubblicazione.';
                lineageInspector.hidden = false;
                candidateHeading.focus();
              });
              lineageLinks.append(button);
              for (const claim of candidate.claim_candidates) {
                if (claim.status !== 'CANDIDATE') continue;
                const prepare = document.createElement('button');
                prepare.type = 'button';
                prepare.textContent = 'Prepara intenzione privata per Claim Candidate ' + claim.id;
                prepare.addEventListener('click', () => {
                  if (!lineageLinks.contains(prepare)) return;
                  // A persisted provenance path can *populate scope IDs* only:
                  // no MatchRun fingerprint, CAS revision or reviewer signature
                  // is derived from this historical read-only inspection.
                  for (const field of candidateWriteForm.querySelectorAll('input,select,textarea')) {
                    if (field.name === 'decision') field.value = 'HOLD';
                    else if (field.name === 'expected_revision') field.value = '0';
                    else field.value = '';
                  }
                  candidateWriteForm.elements.namedItem('candidate_id').value = claim.id;
                  candidateWriteForm.elements.namedItem('capture_id').value = match.capture_id;
                  candidateWriteForm.elements.namedItem('capture_sha256').value = match.capture_sha256;
                  candidateWriteForm.elements.namedItem('passage_id').value = match.passage.id;
                  candidateWriteSummary.textContent = 'Scope copiato da Collection e Passage persistiti. Inserisci MatchRun, fingerprint, revisione e firma indipendente; nessuna intenzione autorizzata.';
                  candidateWriteForm.elements.namedItem('run_id').focus();
                });
                lineageLinks.append(prepare);
              }
            }
            if (match.next_after_statement_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva degli Statement Candidate';
              more.addEventListener('click', () => {
                lineageForm.elements.namedItem('after_statement_id').value = match.next_after_statement_id;
                lineageForm.requestSubmit();
              });
              lineageLinks.append(more);
            }
            lineageHeading.focus();
            return;
          }
          if (form === captureQueueForm) {
            results.textContent = 'Solo metadati validati nella coda delle catture.';
            const queue = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && queue?.contract_version === 'studio-capture-triage-queue-v1'
              && queue.private_only === true && queue.read_only === true
              && queue.publication_authority === false && queue.rights_clearance === false
              && queue.triage_action_authorized === false
              && queue.collection_id === data.collection_id && SAFE_REF.test(queue.collection_status)
              && Array.isArray(queue.results) && queue.results.length <= data.limit
              && queue.results.every(item => item.collection_id === data.collection_id
                && SAFE_REF.test(item.content_id) && SAFE_REF.test(item.capture_id)
                && ['BLOCKED_CAPTURE', 'CHANGED_CAPTURE'].includes(item.queue_family)
                && ['BLOCKED', 'NEEDS_REVIEW'].includes(item.state)
                && Array.isArray(item.blockers) && item.blockers.length > 0
                && item.blockers.every(code => SAFE_REF.test(code)))
              && (queue.next_after_capture_id == null || (SAFE_REF.test(queue.next_after_capture_id)
                && queue.results.length === data.limit
                && queue.next_after_capture_id === queue.results.at(-1)?.capture_id));
            if (!valid) {
              captureQueueSummary.textContent = 'Coda non verificabile o risposta non conforme.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            captureQueueSummary.textContent = queue.results.length + ' eccezioni persistite in questa pagina'
              + ' · raccolta ' + queue.collection_id + ' (' + queue.collection_status
              + '). Nessuna azione di triage autorizzata.';
            for (const item of queue.results) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = item.queue_family + ' · Content ' + item.content_id
                + ' · Capture ' + item.capture_id + ' · ' + item.state
                + ' · blocchi: ' + item.blockers.join(', ');
              button.addEventListener('click', () => {
                if (!captureQueueLinks.contains(button)) return;
                collectionCaptureForm.elements.namedItem('collection_id').value = queue.collection_id;
                collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                collectionCaptureForm.elements.namedItem('after_id').value = '';
                for (const panel of panels) panel.hidden = panel.id !== 'collections';
                for (const panelButton of document.querySelectorAll('[data-panel]')) {
                  panelButton.setAttribute('aria-pressed', panelButton.dataset.panel === 'collections' ? 'true' : 'false');
                }
                collectionCaptureForm.requestSubmit();
              });
              captureQueueLinks.append(button);
            }
            if (queue.next_after_capture_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva della coda delle catture';
              more.addEventListener('click', () => {
                captureQueueForm.elements.namedItem('after_capture_id').value = queue.next_after_capture_id;
                captureQueueForm.requestSubmit();
              });
              captureQueueLinks.append(more);
            }
            return;
          }
          if (form === inboxForm) {
            results.textContent = 'Solo riferimenti Discovery validati nell’Inbox.';
            const inbox = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && inbox?.contract_version === 'studio-discovery-inbox-v2'
              && inbox.collection_id === data.collection_id
              && inbox.private_only === true && inbox.read_only === true
              && inbox.action_authorized === false && inbox.publication_authority === false
              && Array.isArray(inbox.rows) && inbox.rows.length <= data.limit
              && inbox.rows.every(row =>
                row.collection_id === data.collection_id && SAFE_REF.test(row.hit_id)
                && row.private_only === true && row.read_only === true
                && row.action_authorized === false && row.publication_authority === false
                && (row.annotation_revision === null ||
                  Number.isSafeInteger(row.annotation_revision) && row.annotation_revision >= 0)
                && Array.isArray(row.blockers) && row.blockers.every(code => SAFE_REF.test(code)))
              && (inbox.next_after_id === null || SAFE_REF.test(inbox.next_after_id));
            if (!valid) {
              inboxAnnotationSummary.textContent = 'Inbox non verificabile, nessun Hit navigabile.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            inboxAnnotationSummary.textContent = inbox.rows.length
              + ' Hit persistiti; seleziona per aprire lo storico e preparare una decisione firmata esternamente.';
            for (const row of inbox.rows) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = 'Hit ' + row.hit_id + ' · revisione '
                + (row.annotation_revision === null ? 'lineage non verificata' : row.annotation_revision)
                + ' · blocchi: ' + row.blockers.join(', ');
              button.addEventListener('click', () => {
                if (!inboxAnnotationLinks.contains(button)) return;
                triageHistoryForm.elements.namedItem('collection_id').value = inbox.collection_id;
                triageHistoryForm.elements.namedItem('hit_id').value = row.hit_id;
                triageHistoryForm.elements.namedItem('after_revision').value = '0';
                triageWriteForm.elements.namedItem('collection_id').value = inbox.collection_id;
                triageWriteForm.elements.namedItem('hit_id').value = row.hit_id;
                triageWriteForm.elements.namedItem('expected_revision').value =
                  row.annotation_revision === null ? '' : String(row.annotation_revision);
                triageWriteForm.elements.namedItem('request_key').value = '';
                triageWriteForm.elements.namedItem('receipt_id').value = '';
                triageWriteForm.elements.namedItem('confirm_private_annotation').value = '';
                triageHistoryForm.requestSubmit();
              });
              inboxAnnotationLinks.append(button);
            }
            return;
          }
          if (form === triageWriteForm) {
            results.textContent = 'Solo stato dell’annotazione privata, senza ricevuta HMAC o identità.';
            const signed = receipt?.data;
            const valid = receipt?.contract_version === 'studio-private-annotation-api-v1'
              && signed?.contract_version === 'studio-private-triage-annotation-v1'
              && signed.private_only === true && signed.mutation_kind === 'ANNOTATION_ONLY'
              && signed.collection_id === data.collection_id && signed.hit_id === data.hit_id
              && signed.decision === data.decision && signed.capture_authorized === false
              && signed.triage_action_authorized === false && signed.promotion_authority === false
              && signed.publication_authority === false
              && Number.isSafeInteger(signed.revision) && signed.revision >= 0
              && SAFE_SHA256.test(signed.payload_sha256)
              && ['CREATED','REPLAY','REVISION_CONFLICT','IDEMPOTENCY_CONFLICT','SCOPE_NOT_FOUND']
                 .includes(signed.result_code)
              && response.ok === ['CREATED','REPLAY'].includes(signed.result_code)
              && signed.actor_attested === response.ok;
            if (!valid) {
              triageWriteSummary.textContent = 'Nessuna annotazione confermata. Servizio non attivo, attestazione mancante o risposta non valida.';
              status.textContent = 'Scrittura privata non confermata.';
              return;
            }
            triageWriteSummary.textContent = signed.result_code + ' · revisione '
              + signed.revision + ' · fingerprint ' + signed.payload_sha256
              + '. Solo storico privato: nessuna approvazione, Capture o pubblicazione.';
            if (response.ok && captureQueueSummary) {
              status.textContent = 'Annotazione salvata; rileggi lo storico per la conferma indipendente.';
            }
            return;
          }
          if (form === mediaContextForm) {
            results.textContent = 'Solo selettori, hash, intervalli e blocchi: nessun media riprodotto.';
            const timeline = receipt?.data;
            const segment = timeline?.canonical_segment;
            const capture = timeline?.capture;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && timeline?.contract_version === 'studio-media-capture-context-v1'
              && timeline.private_only === true && timeline.publication_authority === false
              && timeline.rights_clearance === false && timeline.seek_authorized === false
              && timeline.capture_segment_binding === 'UNPROVEN'
              && segment && SAFE_REF.test(segment.id)
              && Number.isSafeInteger(segment.start_ms) && segment.start_ms >= 0
              && Number.isSafeInteger(segment.end_ms) && segment.end_ms > segment.start_ms
              && capture?.id === data.capture_id && capture.content_sha256 === data.capture_sha256
              && SAFE_SHA256.test(capture.content_sha256)
              && timeline.statement_candidate_id === data.statement_candidate_id
              && timeline.content_id === data.content_id && timeline.passage_id === data.passage_id
              && Array.isArray(timeline.hold_reasons)
              && timeline.hold_reasons.includes('STUDIO_MEDIA_CAPTURE_SEGMENT_BINDING_UNPROVEN')
              && timeline.hold_reasons.every(code => SAFE_REF.test(code));
            if (!valid) {
              mediaContextSummary.textContent = 'Contesto multimediale non verificabile o fuori scope.';
              status.textContent = 'Nessun seek autorizzato.';
              return;
            }
            mediaContextSummary.textContent = 'Segmento ' + segment.id + ' · intervallo '
              + (segment.start_ms / 1000) + '–' + (segment.end_ms / 1000) + ' s'
              + ' · cattura ' + capture.id + ' · stato ' + capture.status
              + ' · corpo ' + capture.body_state + ' · conservazione '
              + capture.retention_class + ' · blocchi: ' + timeline.hold_reasons.join(', ')
              + '. Provenienza segmento↔cattura non attestata. Riproduzione negata.';
            return;
          }
          if (form === mediaBindingForm) {
            results.textContent = 'Solo Capture, Segment, versione, revoche e blocchi.';
            const binding = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && binding?.contract_version === 'studio-capture-segment-binding-pg-v1'
              && binding.private_only === true && binding.publication_authority === false
              && binding.rights_clearance === false && binding.seek_authorized === false
              && binding.capture_segment_binding === 'OPERATOR_ATTESTED_METADATA_ONLY'
              && binding.binding_id === data.binding_id
              && SAFE_REF.test(binding.content_id) && SAFE_REF.test(binding.capture_id)
              && SAFE_REF.test(binding.canonical_segment_id)
              && SAFE_SHA256.test(binding.capture_sha256)
              && Number.isSafeInteger(binding.start_ms) && binding.start_ms >= 0
              && Number.isSafeInteger(binding.end_ms) && binding.end_ms > binding.start_ms
              && Number.isSafeInteger(binding.revision) && binding.revision > 0
              && ['ATTESTED','HELD','REVOKED'].includes(binding.binding_state)
              && Array.isArray(binding.hold_reasons) && binding.hold_reasons.length > 0
              && binding.hold_reasons.every(code => SAFE_REF.test(code));
            if (!valid) {
              mediaBindingSummary.textContent = 'Nessuna attestazione valida. Nessun media autorizzato.';
              return;
            }
            mediaBindingSummary.textContent = 'Binding ' + binding.binding_id
              + ' · Capture ' + binding.capture_id + ' (' + binding.capture_sha256 + ')'
              + ' · segmento ' + binding.canonical_segment_id
              + ' · ' + (binding.start_ms / 1000) + '–' + (binding.end_ms / 1000) + ' s'
              + ' · revisione ' + binding.revision + ' · ' + binding.binding_state
              + ' · blocchi: ' + binding.hold_reasons.join(', ')
              + '. Solo metadati di operatore, nessuna riproduzione o autorità editoriale.';
            return;
          }
          status.textContent = response.ok ? 'Dati privati di sola lettura recuperati.' : 'Accesso negato o dati non disponibili.';
          results.textContent = JSON.stringify(receipt, null, 2);
          if (response.ok && form.dataset.endpoint === '/v1/media/segment'
              && receipt.data?.canonical_segment) {
            const segment = receipt.data.canonical_segment;
            mediaLocator.textContent = 'Segmento ' + segment.id + ' · '
              + (segment.start_ms / 1000) + '–' + (segment.end_ms / 1000)
              + ' secondi · stato ' + segment.transcript_status
              + (segment.publication_blocked ? ' · pubblicazione bloccata' : '')
              + ' · sola posizione interna, non permesso di riprodurre';
          }
          if (response.ok && form.dataset.endpoint === '/v1/capture/compare') {
            const comparison = receipt.data?.selector_comparison;
            if (receipt.data?.private_only === true && receipt.data?.rights_clearance === false
                && receipt.data?.publication_authority === false && comparison?.complete === true
                && comparison.status === 'COMPLETE' && comparison.counts
                && ['UNCHANGED', 'CHANGED', 'ADDED', 'REMOVED'].every(
                  key => Number.isInteger(comparison.counts[key]) && comparison.counts[key] >= 0)) {
              captureSelectorDiffSummary.textContent = 'Selettori delle catture: '
                + comparison.counts.UNCHANGED + ' invariati, '
                + comparison.counts.CHANGED + ' modificati, '
                + comparison.counts.ADDED + ' aggiunti, '
                + comparison.counts.REMOVED + ' rimossi. '
                + 'Confronto di soli hash e coordinate, nessun permesso di riproduzione.';
            } else if (comparison?.status === 'TRUNCATED' && comparison.complete === false) {
              captureSelectorDiffSummary.textContent = 'Confronto non completo: oltre 20 selettori in almeno una versione. '
                + 'Aprire i selettori paginati per ispezionarli. Nessuna differenza totale deducibile.';
            } else {
              captureSelectorDiffSummary.textContent = 'Confronto di selettori non disponibile.';
            }
            for (const position of ['earlier', 'later']) {
              const capture = receipt.data?.[position];
              if (typeof capture?.content_sha256 !== 'string' || typeof receipt.data?.content_id !== 'string') continue;
              const link = document.createElement('button');
              link.type = 'button';
              link.textContent = (position === 'earlier' ? 'Precedente' : 'Successiva') + ' · selettori di ' + capture.id;
              link.addEventListener('click', () => {
                capturePassageForm.elements.namedItem('content_id').value = receipt.data.content_id;
                capturePassageForm.elements.namedItem('capture_hash').value = capture.content_sha256;
                capturePassageForm.elements.namedItem('after_id').value = '';
                capturePassageForm.requestSubmit();
              });
              captureLinks.append(link);
            }
          }
          if (form === capturePassageForm && response.ok && Array.isArray(receipt.data?.selectors)) {
            const dataForPassages = receipt.data;
            if (scopedCaptureReference && scopedCaptureReference.content_id === data.content_id
                && dataForPassages.contract_version === 'studio-capture-inspection-v1'
                && receipt.contract_version === 'studio-local-readonly-api-v1'
                && dataForPassages.private_only === true
                && dataForPassages.content_id === scopedCaptureReference.content_id
                && dataForPassages.capture?.id === scopedCaptureReference.capture_id
                && dataForPassages.capture?.content_sha256 === scopedCaptureReference.capture_sha256
                && data.capture_hash === scopedCaptureReference.capture_sha256
                && SAFE_REF.test(scopedCaptureReference.collection_id)
                && dataForPassages.rights_clearance === false
                && dataForPassages.publication_authority === false) {
              for (const passage of dataForPassages.selectors) {
                if (!SAFE_REF.test(passage.id) || !SAFE_SHA256.test(passage.text_sha256)
                    || !['TEXT_POSITION', 'PAGE_RANGE'].includes(passage.selector_type)
                    || passage.capture_locator?.content_id !== scopedCaptureReference.content_id
                    || passage.capture_locator?.capture_id !== scopedCaptureReference.capture_id
                    || passage.capture_locator?.capture_sha256 !== scopedCaptureReference.capture_sha256
                    || passage.capture_locator?.passage_id !== passage.id) continue;
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = 'Passage ' + passage.id + ' · ' + passage.selector_type;
                button.addEventListener('click', () => {
                  if (!capturePassageLinks.contains(button) || !lineageForm) return;
                  lineageForm.elements.namedItem('collection_id').value = scopedCaptureReference.collection_id;
                  lineageForm.elements.namedItem('content_id').value = scopedCaptureReference.content_id;
                  lineageForm.elements.namedItem('capture_id').value = scopedCaptureReference.capture_id;
                  lineageForm.elements.namedItem('passage_id').value = passage.id;
                  lineageForm.elements.namedItem('limit').value = '20';
                  lineageForm.elements.namedItem('after_statement_id').value = '';
                  for (const panelButton of document.querySelectorAll('[data-panel]')) {
                    panelButton.setAttribute('aria-pressed', panelButton.dataset.panel === 'collections' ? 'true' : 'false');
                  }
                  for (const panel of panels) panel.hidden = panel.id !== 'collections';
                  lineageForm.requestSubmit();
                });
                capturePassageLinks.append(button);
              }
            }
          }
          if (response.ok && form.dataset.endpoint === '/v1/collections/members'
              && Array.isArray(receipt.data?.results)) {
            if (collectionMemberSummary) {
              collectionMemberSummary.textContent = receipt.data.results.length
                + ' Content inclusi in questa pagina della raccolta ' + receipt.data.collection_id;
            }
            for (const member of receipt.data.results) {
              if (typeof member.content_id !== 'string') continue;
              const link = document.createElement('button');
              link.type = 'button';
              link.textContent = member.content_id + ' · ' + member.rights_status + ' · ' + member.processing_status;
              link.addEventListener('click', () => {
                memberDetailForm.elements.namedItem('collection_id').value = receipt.data.collection_id;
                memberDetailForm.elements.namedItem('content_id').value = member.content_id;
                memberDetailForm.elements.namedItem('after_claim_id').value = '';
                memberDetailForm.requestSubmit();
              });
              memberLinks.append(link);
            }
            if (receipt.data.next_after_id && SAFE_REF.test(receipt.data.next_after_id)
                && receipt.data.results.length === data.limit
                && receipt.data.next_after_id === receipt.data.results.at(-1)?.content_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva dei Content inclusi';
              more.addEventListener('click', () => {
                collectionMembersForm.elements.namedItem('after_id').value = receipt.data.next_after_id;
                collectionMembersForm.requestSubmit();
              });
              memberLinks.append(more);
            }
          }
          if (response.ok && form.dataset.endpoint === '/v1/collections/member'
              && Array.isArray(receipt.data?.claims)) {
            if (receipt.data?.private_only === true
                && receipt.data?.publication_authority === false
                && SAFE_REF.test(receipt.data.collection_id)
                && SAFE_REF.test(receipt.data.content_id)
                && receipt.data?.source_exists === true) {
              collectionCaptureForm.elements.namedItem('collection_id').value = receipt.data.collection_id;
              collectionCaptureForm.elements.namedItem('content_id').value = receipt.data.content_id;
              collectionCaptureForm.elements.namedItem('after_id').value = '';
              collectionCaptureForm.requestSubmit();
            } else {
              collectionCaptureSummary.textContent = 'Nessun collegamento persistito valido alla fonte.';
            }
            for (const claim of receipt.data.claims) {
              if (typeof claim.id !== 'string') continue;
              const link = document.createElement('button');
              link.type = 'button';
              link.textContent = claim.id + ' · ' + claim.claim_type;
              link.addEventListener('click', () => {
                provenanceForm.elements.namedItem('collection_id').value = receipt.data.collection_id;
                provenanceForm.elements.namedItem('content_id').value = receipt.data.content_id;
                provenanceForm.elements.namedItem('claim_id').value = claim.id;
                provenanceForm.elements.namedItem('after_id').value = '';
                provenanceForm.requestSubmit();
              });
              claimLinks.append(link);
            }
          }
          if (form === collectionCaptureForm) {
            const captureData = receipt.data;
            if (!response.ok || receipt.contract_version !== 'studio-local-readonly-api-v1'
                || captureData?.contract_version !== 'studio-collection-captures-v1'
                || captureData.private_only !== true || captureData.publication_authority !== false
                || captureData.rights_clearance !== false || captureData.capture_authorized !== false
                || captureData.collection_id !== data.collection_id || captureData.content_id !== data.content_id
                || !SAFE_REF.test(captureData.source_id) || captureData.source_exists !== true
                || !Array.isArray(captureData.captures) || captureData.captures.length > 20) {
              collectionCaptureSummary.textContent = 'Versioni non verificabili: nessun riferimento disponibile.';
              return;
            }
            const captures = captureData.captures;
            const valid = captures.every(item => SAFE_REF.test(item.id)
              && SAFE_SHA256.test(item.content_sha256)
              && typeof item.observed_at === 'string' && !Number.isNaN(Date.parse(item.observed_at)));
            if (!valid) {
              collectionCaptureSummary.textContent = 'Risposta non conforme: nessun riferimento disponibile.';
              return;
            }
            collectionCaptureSummary.textContent = captures.length
              ? 'Content ' + captureData.content_id + ' · fonte ' + captureData.source_id
                + ' · diritti ' + captureData.rights_status
                + ' · ' + captures.length + ' versioni in questa pagina. Nessun permesso di riprodurre.'
              : 'Content ' + captureData.content_id + ' · fonte ' + captureData.source_id
                + ': nessuna cattura persistita. Non esistono selettori di cattura navigabili.';
            for (const capture of captures) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = 'Cattura ' + capture.id + ' · ' + capture.observed_at
                + ' · ' + capture.status + ' · archivio ' + capture.archive_status;
              button.addEventListener('click', () => {
                if (!collectionCaptureLinks.contains(button)) return;
                scopedCaptureReference = {collection_id: captureData.collection_id,
                                          content_id: captureData.content_id,
                                          source_id: captureData.source_id,
                                          capture_id: capture.id,
                                          capture_sha256: capture.content_sha256};
                for (const panelButton of document.querySelectorAll('[data-panel]')) {
                  panelButton.setAttribute('aria-pressed', panelButton.dataset.panel === 'captures' ? 'true' : 'false');
                }
                for (const panel of panels) panel.hidden = panel.id !== 'captures';
                capturePassageForm.elements.namedItem('content_id').value = captureData.content_id;
                capturePassageForm.elements.namedItem('capture_hash').value = capture.content_sha256;
                capturePassageForm.elements.namedItem('after_id').value = '';
                capturePassageForm.requestSubmit();
              });
              collectionCaptureLinks.append(button);
            }
            // Keyset continuation only; no unbounded fetch or client-side full-corpus load.
            if (captureData.has_more === true && SAFE_REF.test(captureData.next_after_id)) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Carica pagina successiva delle catture';
              more.addEventListener('click', () => {
                collectionCaptureForm.elements.namedItem('after_id').value = captureData.next_after_id;
                collectionCaptureForm.requestSubmit();
              });
              collectionCaptureLinks.append(more);
            }
            if (captures.length >= 2) {
              const byTime = [...captures].sort((left, right) =>
                Date.parse(left.observed_at) - Date.parse(right.observed_at));
              const first = byTime[0], last = byTime[byTime.length - 1];
              if (Date.parse(first.observed_at) < Date.parse(last.observed_at)) {
                const compare = document.createElement('button');
                compare.type = 'button';
                compare.textContent = 'Confronta prima e ultima cattura visibili';
                compare.addEventListener('click', () => {
                  for (const panelButton of document.querySelectorAll('[data-panel]')) {
                    panelButton.setAttribute('aria-pressed', panelButton.dataset.panel === 'captures' ? 'true' : 'false');
                  }
                  for (const panel of panels) panel.hidden = panel.id !== 'captures';
                  compareForm.elements.namedItem('content_id').value = captureData.content_id;
                  compareForm.elements.namedItem('earlier_hash').value = first.content_sha256;
                  compareForm.elements.namedItem('later_hash').value = last.content_sha256;
                  compareForm.requestSubmit();
                });
                collectionCaptureLinks.append(compare);
              }
            }
          }
          if (form === passageCandidateForm) {
            const match = receipt.data;
            if (!response.ok || receipt.contract_version !== 'studio-local-readonly-api-v1'
                || match?.contract_version !== 'studio-passage-candidates-v1'
                || match.private_only !== true || match.publication_authority !== false
                || match.review_authority !== false || match.rights_clearance !== false
                || match.collection_id !== data.collection_id
                || match.content_id !== data.content_id || match.passage_id !== data.passage_id
                || !Array.isArray(match.candidates) || match.candidates.length > 20) {
              passageCandidateSummary.textContent = 'Collegamenti non verificabili.';
              return;
            }
            passageCandidateSummary.textContent = match.candidates.length
              ? match.candidates.length + ' Statement Candidate con collegamento persistito. Revisione non verificata.'
              : 'Nessun candidato persistito collegato a questo Passage.';
            for (const candidate of match.candidates) {
              if (!SAFE_REF.test(candidate.statement_candidate_id)
                  || !Array.isArray(candidate.claim_candidates)) continue;
              const button = document.createElement('button');
              button.type = 'button';
              const linkedClaims = candidate.claim_candidates.map(c =>
                SAFE_REF.test(c.id) ? c.id + (SAFE_REF.test(c.promoted_claim_id)
                  ? ' → ' + c.promoted_claim_id : '') : '').filter(Boolean);
              button.textContent = 'Statement ' + candidate.statement_candidate_id
                + ' · ' + candidate.status + ' · Claim candidate/storici: '
                + (linkedClaims.join(', ') || 'nessuno');
              button.addEventListener('click', () => {
                if (match.selector_type !== 'MEDIA_SEGMENT_REF') return;
                mediaForm.elements.namedItem('content_id').value = match.content_id;
                mediaForm.elements.namedItem('statement_candidate_id').value = candidate.statement_candidate_id;
                mediaForm.elements.namedItem('passage_id').value = match.passage_id;
                mediaForm.requestSubmit();
              });
              passageCandidateLinks.append(button);
            }
            if (match.has_more === true && SAFE_REF.test(match.next_after_id)) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva dei candidati';
              more.addEventListener('click', () => {
                passageCandidateForm.elements.namedItem('after_id').value = match.next_after_id;
                passageCandidateForm.requestSubmit();
              });
              passageCandidateLinks.append(more);
            }
          }
        } catch (_) {
          if (generation !== requestGeneration) return;
          activeRequest = null;
          status.textContent = 'Servizio locale non disponibile.';
          results.textContent = 'Nessun risultato.';
        }
      });
    }
  </script>
</body></html>
"""


def render_studio_login_page(nonce: str) -> bytes:
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise ValueError("STUDIO_LOCAL_PAGE_NONCE_INVALID")
    return _PAGE.replace("__NONCE__", nonce).encode("utf-8")


__all__ = ["render_studio_login_page"]
