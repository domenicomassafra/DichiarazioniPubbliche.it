"""Immutable private Studio HTML fragment 4/11."""

PART = r"""    const collectionCaptureLinks = document.getElementById('collection-capture-links');
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
    const candidateQueueForm = document.querySelector('form[data-endpoint="/v1/discovery/candidate-queue"]');
    const candidateQueueLinks = document.getElementById('candidate-queue-links');
    const candidateQueueSummary = document.getElementById('candidate-queue-summary');
    const coverageQueueForm = document.querySelector('form[data-endpoint="/v1/discovery/coverage-queue"]');
    const coverageQueueLinks = document.getElementById('coverage-queue-links');
    const coverageQueueSummary = document.getElementById('coverage-queue-summary');
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
    __CAPTURE_DIFF_BROWSER_HELPERS__
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
      captureSelectorDiffDetails?.replaceChildren();
      if (captureCopyStatus) captureCopyStatus.textContent = 'I riferimenti di audit sono privati e non autorizzano riproduzione.';
      capturePassageLinks.replaceChildren();
      passageCandidateLinks.replaceChildren();
"""
