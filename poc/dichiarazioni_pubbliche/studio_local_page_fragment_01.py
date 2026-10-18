"""Immutable private Studio HTML fragment 2/11."""

PART = r"""      <p id="collection-capture-summary" role="status" aria-live="polite">Nessun Content selezionato per le catture.</p>
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
        <input type="hidden" name="expected_snapshot_sha256" value="">
        <button type="submit">Mostra eccezioni delle catture</button></div>
      </form>
      <p id="capture-queue-summary" role="status" aria-live="polite">Nessuna coda letta.</p>
      <div id="capture-queue-links" role="group" aria-label="Catture bloccate o cambiate"></div>
      <h2>Coda Statement Candidate da ispezionare</h2>
      <p>Collegamenti persistiti alla Capture e al Passage, con blocchi di diritti e provenienza.
      Ogni voce rimane privata e non autorizza review, promozione o pubblicazione.</p>
      <form data-endpoint="/v1/discovery/candidate-queue" aria-describedby="candidate-queue-summary">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Candidate ID<input name="after_candidate_id" maxlength="180"></label>
        <input type="hidden" name="expected_snapshot_sha256" value="">
        <button type="submit">Mostra Statement Candidate persistiti</button></div>
      </form>
      <p id="candidate-queue-summary" role="status" aria-live="polite">Nessuna coda Candidate letta.</p>
      <div id="candidate-queue-links" role="group" aria-label="Statement Candidate da ispezionare"></div>
      <h2>Coda Coverage Needs persistite</h2>
      <p>Esigenze di prova aperte, in ricerca o bloccate: codici di motivo, tentativi e riferimenti,
      mai domande riservate, testi delle fonti o autorizzazioni implicite.</p>
      <form data-endpoint="/v1/discovery/coverage-queue">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Coverage Need ID<input name="after_need_id" maxlength="180"></label>
        <input type="hidden" name="expected_snapshot_sha256" value="">
        <button type="submit">Mostra Coverage Needs persistite</button></div>
      </form>
      <p id="coverage-queue-summary" role="status" aria-live="polite">Nessuna Coverage Need letta.</p>
      <div id="coverage-queue-links" role="group" aria-label="Coverage Needs da verificare"></div>
      <h2>Catalogo Discovery per raccolta</h2>
      <p>Provenienza, stato della raccolta, diritti e motivi di blocco dal database. Nessuna azione di revisione, cattura o pubblicazione è abilitata da questa pagina.</p>
      <form data-endpoint="/v1/discovery/inbox">
        <div class="controls"><label>ID raccolta<input name="collection_id" maxlength="180" value="research:garlasco" required></label>
        <label>Limite (1–30)<input name="limit" type="number" min="1" max="30" value="20" required></label>
        <label>Dopo Discovery Hit ID<input name="after_id" maxlength="180"></label>
        <button type="submit">Consulta Inbox persistita</button></div>
      </form>
      <p id="inbox-annotation-summary" role="status" aria-live="polite">Nessun Hit caricato.</p>
      <p class="quiet">Conteggi riferiti alla pagina corrente, non all’intera raccolta. Ogni Hit resta privato fino alla verifica dei diritti e della provenienza.</p>
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
"""
