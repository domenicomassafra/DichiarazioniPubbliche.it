"""Immutable private Studio HTML fragment 10/11."""

PART = r"""              && binding.private_only === true && binding.publication_authority === false
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
          results.textContent = form === compareForm
            ? 'Confronto Capture privato: coordinate e hash validati nel pannello Catture.'
            : JSON.stringify(receipt, null, 2);
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
            showCaptureComparison(receipt, data, generation);
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
"""
