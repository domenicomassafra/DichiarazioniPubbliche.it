"""Immutable private Studio HTML fragment 1/11."""

PART = r"""<!doctype html>
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
    #collection-lineage-links,#capture-queue-links,#collection-navigation-links,#inbox-annotation-links{display:grid;gap:.4rem;margin:1rem 0}
    #collection-lineage-links button,#capture-queue-links button,#collection-navigation-links button,#inbox-annotation-links button{text-align:left;overflow-wrap:anywhere}
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
"""
