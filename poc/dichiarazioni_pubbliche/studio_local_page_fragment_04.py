"""Immutable private Studio HTML fragment 5/11."""

PART = r"""      passageCandidateSummary.textContent = 'Nessun Passage selezionato.';
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
      candidateQueueLinks?.replaceChildren();
      if (candidateQueueSummary) candidateQueueSummary.textContent = 'Nessuna coda Candidate letta.';
      coverageQueueLinks?.replaceChildren();
      if (coverageQueueSummary) coverageQueueSummary.textContent = 'Nessuna Coverage Need letta.';
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
      for (const form of [lineageForm, captureQueueForm, candidateQueueForm, coverageQueueForm]) {
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
          if (!data.after_capture_id) {
            delete data.expected_snapshot_sha256;
            captureQueueForm.elements.namedItem('expected_snapshot_sha256').value = '';
          }
          captureQueueLinks.replaceChildren();
          captureQueueSummary.textContent = 'Lettura della coda in corso…';
        }
        if (form === candidateQueueForm) {
          if (!data.after_candidate_id) {
            delete data.expected_snapshot_sha256;
            candidateQueueForm.elements.namedItem('expected_snapshot_sha256').value = '';
          }
          candidateQueueLinks.replaceChildren();
          candidateQueueSummary.textContent = 'Lettura Candidate e provenienza in corso…';
        }
        if (form === coverageQueueForm) {
          if (!data.after_need_id) {
            delete data.expected_snapshot_sha256;
            coverageQueueForm.elements.namedItem('expected_snapshot_sha256').value = '';
          }
          coverageQueueLinks.replaceChildren();
          coverageQueueSummary.textContent = 'Lettura Coverage Needs in corso…';
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
          captureSelectorDiffDetails?.replaceChildren();
          if (captureCopyStatus) captureCopyStatus.textContent = 'Nessun riferimento copiato.';
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
"""
