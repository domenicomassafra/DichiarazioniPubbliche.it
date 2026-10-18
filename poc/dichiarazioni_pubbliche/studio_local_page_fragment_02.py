"""Immutable private Studio HTML fragment 3/11."""

PART = r"""      <p>Decisioni private persistite, non autorizzazioni: ogni risultato resta soggetto a identità del revisore e diritti sulle fonti da verificare. L'archivio è disponibile soltanto dopo la migrazione SQL.</p>
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
      <div id="capture-selector-diff-details" role="group" aria-label="Coordinate e riferimenti delle differenze tra catture"></div>
      <p id="capture-copy-status" role="status" aria-live="polite">I riferimenti di audit sono privati e non autorizzano riproduzione.</p>
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
    const captureSelectorDiffDetails = document.getElementById('capture-selector-diff-details');
    const captureCopyStatus = document.getElementById('capture-copy-status');
    const capturePassageLinks = document.getElementById('capture-passage-links');
    const passageCandidateLinks = document.getElementById('passage-candidate-links');
    const passageCandidateSummary = document.getElementById('passage-candidate-summary');
"""
