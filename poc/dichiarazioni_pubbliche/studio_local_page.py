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
    p{max-width:55rem}
    .quiet{color:#354256;font-size:.93rem}
    .rules{border-block:1px solid #7d8580;padding:1rem 0;margin:1rem 0}
    .controls{display:flex;flex-wrap:wrap;gap:1rem;align-items:end}
    label{display:grid;gap:.2rem;min-width:14rem;max-width:100%;font-weight:600;font-size:.9rem}
    input,select,button{font:inherit;padding:.65rem;border:1px solid #4d5861;border-radius:0;min-height:2.5rem;background:white;color:inherit}
    input,select{width:100%}button{cursor:pointer}
    button[aria-pressed=true],button[type=submit]{background:#182130;color:white}
    :focus-visible{outline:3px solid #0f46b0;outline-offset:2px}
    [hidden]{display:none!important}
    .pane{margin-top:1rem;padding:1rem;border:1px solid #9ca3a0}
    .notice{font-weight:600}
    #member-links{display:grid;gap:.4rem;margin:1rem 0}
    #member-links button{text-align:left;overflow-wrap:anywhere}
    #claim-links{display:grid;gap:.4rem;margin:1rem 0}
    #claim-links button{text-align:left;overflow-wrap:anywhere}
    #corpus-links{display:grid;gap:.4rem;margin:1rem 0}
    #corpus-links button{text-align:left;overflow-wrap:anywhere}
    #corpus-inspector{border:1px solid #68747c;padding:1rem;margin-top:1rem}
    #corpus-inspector dl{display:grid;grid-template-columns:minmax(8rem,12rem) minmax(0,1fr);gap:.45rem}
    #corpus-inspector dd{margin:0;overflow-wrap:anywhere}
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
      <h2>Contenuti inclusi</h2><p>Seleziona una raccolta per leggere solo i riferimenti persistiti. Il dettaglio indica i collegamenti verificati e gli elementi ancora assenti.</p>
      <form data-endpoint="/v1/collections/members">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Content ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Elenca contenuti</button></div>
      </form>
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
      <h2>Catalogo Discovery per raccolta</h2>
      <p>Provenienza, stato della raccolta, diritti e motivi di blocco dal database. Nessuna azione di revisione, cattura o pubblicazione è abilitata da questa pagina.</p>
      <form data-endpoint="/v1/discovery/inbox">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Discovery Hit ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Consulta Inbox persistita</button></div>
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
    </section>
    <section class="pane" id="matches" hidden>
      <h2>Candidati e corrispondenze</h2><p>Classificazioni suggerite da un match run persistito; attualità e autorità di revisione non verificate.</p>
      <form data-endpoint="/v1/candidate/matches">
        <div class="controls"><label>ID match run<input name="run_id" maxlength="180" required></label>
        <label>ID candidato<input name="claim_candidate_id" maxlength="180" required></label>
        <button type="submit">Ispeziona match</button></div>
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
    const memberLinks = document.getElementById('member-links');
    const claimLinks = document.getElementById('claim-links');
    const captureLinks = document.getElementById('capture-links');
    const capturePassageLinks = document.getElementById('capture-passage-links');
    const passageCandidateLinks = document.getElementById('passage-candidate-links');
    const passageCandidateSummary = document.getElementById('passage-candidate-summary');
    const collectionCaptureLinks = document.getElementById('collection-capture-links');
    const collectionCaptureSummary = document.getElementById('collection-capture-summary');
    const collectionCaptureForm = document.querySelector('form[data-endpoint="/v1/collections/captures"]');
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
      claimLinks.replaceChildren();
      captureLinks.replaceChildren();
      capturePassageLinks.replaceChildren();
      passageCandidateLinks.replaceChildren();
      passageCandidateSummary.textContent = 'Nessun Passage selezionato.';
      scopedCaptureReference = null;
      collectionCaptureLinks.replaceChildren();
      collectionCaptureSummary.textContent = 'Nessun Content selezionato per le catture.';
      mediaLocator.textContent = 'Nessun segmento selezionato.';
    }
    document.getElementById('clear').addEventListener('click', () => {
      token.value = '';
      invalidateRequest();
      hidePrivateLocators();
      results.textContent = 'Token cancellato dalla pagina.';
      status.textContent = 'Accesso disconnesso.';
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
          else if (key === 'from_date') data.from_at = value + 'T00:00:00Z';
          else if (key === 'to_date') data.to_at = value + 'T23:59:59Z';
          else if (key === 'check_worthy') data.check_worthy = value === 'true';
          else data[key] = key === 'limit' || key === 'after_revision' ? Number(value) : value;
        }
        status.textContent = 'Richiesta locale in corso…';
        results.textContent = 'Nessun risultato ancora disponibile.';
        if (form === corpusForm) clearCorpusResults(false);
        if (form.dataset.endpoint === '/v1/collections/members') {
          memberLinks.replaceChildren();
          claimLinks.replaceChildren();
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
        if (form.dataset.endpoint === '/v1/capture/compare') {
          captureLinks.replaceChildren();
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
                && SAFE_REF.test(scopedCaptureReference.collection_id)
                && dataForPassages.rights_clearance === false
                && dataForPassages.publication_authority === false) {
              for (const passage of dataForPassages.selectors) {
                if (!SAFE_REF.test(passage.id)) continue;
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = 'Passage ' + passage.id + ' · ' + passage.selector_type;
                button.addEventListener('click', () => {
                  if (!capturePassageLinks.contains(button)) return;
                  passageCandidateForm.elements.namedItem('collection_id').value = scopedCaptureReference.collection_id;
                  passageCandidateForm.elements.namedItem('content_id').value = scopedCaptureReference.content_id;
                  passageCandidateForm.elements.namedItem('passage_id').value = passage.id;
                  passageCandidateForm.elements.namedItem('after_id').value = '';
                  passageCandidateForm.requestSubmit();
                });
                capturePassageLinks.append(button);
              }
            }
          }
          if (response.ok && form.dataset.endpoint === '/v1/collections/members'
              && Array.isArray(receipt.data?.results)) {
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
                                          source_id: captureData.source_id};
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
