"""Private Studio quote navigation: no source words in the response."""

EXACT_JUMP_FORM_HTML = """
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
      <h2>Apri citazione nella sorgente originale</h2>
      <p>Per Content incluso e Capture approvata. Il server verifica byte e versione correnti; senza diritti o origine approvati non restituisce collegamenti.</p>
      <form id="source-exact-form">
        <div class="controls">
          <label>ID raccolta<input name="collection_id" maxlength="180" required></label>
          <label>Content ID<input name="content_id" maxlength="180" required></label>
          <label>Capture ID<input name="capture_id" maxlength="180" required></label>
          <label>Passage ID<input name="passage_id" maxlength="180" required></label>
          <label>Citazione esatta (fino a 160 caratteri)<input name="quote_text" maxlength="160" required></label>
          <button type="submit">Verifica citazione</button>
        </div>
      </form>
      <p id="source-exact-status" role="status" aria-live="polite">Incolla la citazione per verificarne la versione.</p>
      <a id="source-exact-open" rel="noopener noreferrer" target="_blank" hidden>Apri sorgente</a>
"""

EXACT_JUMP_BROWSER_JS = r"""
    const exactForm = document.getElementById('source-exact-form');
    const exactStatus = document.getElementById('source-exact-status');
    const exactOpen = document.getElementById('source-exact-open');
    function clearExactSourceJump(scrubForm = false) {
      if (scrubForm) {
        for (const name of ['collection_id','content_id','capture_id','passage_id','quote_text']) {
          const field = exactForm.elements?.namedItem(name);
          if (field) field.value = '';
        }
      }
      exactOpen.hidden = true;
      exactOpen.removeAttribute?.('href');
      exactStatus.textContent = 'Incolla la citazione per verificarne la versione.';
    }
    exactForm.addEventListener('submit', async event => {
      event.preventDefault();
      invalidateRequest();
      clearExactSourceJump();
      if (!/^[0-9a-f]{64,128}$/.test(token.value)) {
        exactStatus.textContent = 'Token locale mancante.';
        return;
      }
      const request = Object.fromEntries(new FormData(exactForm).entries());
      if (!Object.values(request).every(value => typeof value === 'string')
          || !['collection_id','content_id','capture_id','passage_id'].every(
            key => SAFE_REF.test(request[key] || ''))
          || !request.quote_text || request.quote_text.length > 160) {
        exactStatus.textContent = 'Identificativi o citazione non validi.';
        return;
      }
      const generation = requestGeneration;
      const controller = new AbortController();
      activeRequest = controller;
      exactStatus.textContent = 'Rilettura privata di Capture e fonte HTTPS in corso…';
      try {
        const response = await fetch('/v1/source/exact-jump', {
          method: 'POST', credentials: 'omit', redirect: 'error',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token.value},
          body: JSON.stringify(request), signal: controller.signal,
        });
        const receipt = await response.json();
        if (generation !== requestGeneration) return;
        activeRequest = null;
        const jump = receipt?.data;
        if (!response.ok || receipt.contract_version !== 'studio-local-readonly-api-v1'
            || jump?.contract_version !== 'studio-exact-source-jump-v1'
            || jump.private_only !== true || jump.publication_authority !== false
            || jump.rights_clearance !== false || typeof jump.reason !== 'string') {
          exactStatus.textContent = 'Sorgente non verificabile.';
          return;
        }
        if (!['READY_PAGE','BEST_EFFORT_TEXT'].includes(jump.status)) {
          exactStatus.textContent = 'Bloccato: ' + jump.reason;
          return;
        }
        if (typeof jump.url !== 'string' || jump.url.length > 2048) {
          exactStatus.textContent = 'URL non valido.';
          return;
        }
        const safe = new URL(jump.url);
        if (safe.protocol !== 'https:' || safe.username || safe.password || safe.search) {
          exactStatus.textContent = 'URL non consentito.';
          return;
        }
        exactOpen.href = safe.href;
        exactOpen.hidden = false;
        exactOpen.textContent = jump.status === 'READY_PAGE'
          ? 'Apri la pagina PDF verificata' : 'Apri il frammento nel browser (posizione indicativa)';
        exactStatus.textContent = jump.reason + '. La citazione resta privata.';
      } catch (_) {
        if (generation !== requestGeneration) return;
        activeRequest = null;
        exactStatus.textContent = 'Sorgente temporaneamente non verificabile.';
      }
    });
"""

__all__ = ["EXACT_JUMP_BROWSER_JS", "EXACT_JUMP_FORM_HTML"]
