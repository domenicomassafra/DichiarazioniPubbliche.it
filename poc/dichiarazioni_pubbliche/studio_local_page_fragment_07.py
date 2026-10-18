"""Immutable private Studio HTML fragment 8/11."""

PART = r"""                  candidateWriteForm.elements.namedItem('candidate_id').value = claim.id;
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
              && typeof queue.snapshot_sha256 === 'string'
              && /^[0-9a-f]{64}$/.test(queue.snapshot_sha256)
              && (!data.expected_snapshot_sha256 || data.expected_snapshot_sha256 === queue.snapshot_sha256)
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
                captureQueueForm.elements.namedItem('expected_snapshot_sha256').value = queue.snapshot_sha256;
                captureQueueForm.requestSubmit();
              });
              captureQueueLinks.append(more);
            }
            return;
          }
          if (form === candidateQueueForm) {
            results.textContent = 'Solo ID e codici verificati dalla coda privata Candidate.';
            const queue = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && queue?.contract_version === 'studio-statement-candidate-queue-pg-v1'
              && queue.private_only === true && queue.read_only === true
              && queue.publication_authority === false && queue.triage_action_authorized === false
              && queue.collection_id === data.collection_id
              && ['ACTIVE','PAUSED','ARCHIVED'].includes(queue.collection_status)
              && /^[0-9a-f]{64}$/.test(queue.snapshot_sha256)
              && (!data.expected_snapshot_sha256 || data.expected_snapshot_sha256 === queue.snapshot_sha256)
              && Array.isArray(queue.rows) && queue.rows.length <= data.limit
              && queue.rows.every(item => item.collection_id === data.collection_id
                && SAFE_REF.test(item.candidate_id) && SAFE_REF.test(item.content_id)
                && (item.capture_id === null || SAFE_REF.test(item.capture_id))
                && (item.passage_id === null || SAFE_REF.test(item.passage_id))
                && ['CANDIDATE','HELD','APPROVED'].includes(item.candidate_status)
                && ['BLOCKED','NEEDS_REVIEW'].includes(item.state)
                && Array.isArray(item.blockers) && item.blockers.length >= 2
                && item.blockers.every(code => SAFE_REF.test(code))
                && SAFE_REF.test(item.retry_condition))
              && (queue.next_after_candidate_id == null || (
                SAFE_REF.test(queue.next_after_candidate_id)
                && queue.rows.length === data.limit
                && queue.next_after_candidate_id === queue.rows.at(-1)?.candidate_id));
            if (!valid) {
              candidateQueueSummary.textContent = 'Coda Candidate non verificabile o snapshot non corrente.';
              status.textContent = 'Dati Candidate non verificabili.';
              return;
            }
            candidateQueueSummary.textContent = queue.rows.length + ' Statement Candidate persistiti'
              + ' · raccolta ' + queue.collection_id + '. Diritti e review non attestati.';
            for (const item of queue.rows) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = item.candidate_id + ' · ' + item.state
                + ' · blocchi: ' + item.blockers.join(', ');
              button.addEventListener('click', () => {
                if (!candidateQueueLinks.contains(button)) return;
                if (item.capture_id && item.passage_id) {
                  lineageForm.elements.namedItem('collection_id').value = queue.collection_id;
                  lineageForm.elements.namedItem('content_id').value = item.content_id;
                  lineageForm.elements.namedItem('capture_id').value = item.capture_id;
                  lineageForm.elements.namedItem('passage_id').value = item.passage_id;
                  lineageForm.elements.namedItem('after_statement_id').value = '';
                } else {
                  collectionCaptureForm.elements.namedItem('collection_id').value = queue.collection_id;
                  collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                  collectionCaptureForm.elements.namedItem('after_id').value = '';
                }
                for (const panel of panels) panel.hidden = panel.id !== 'collections';
                for (const panelButton of document.querySelectorAll('[data-panel]')) {
                  panelButton.setAttribute('aria-pressed', panelButton.dataset.panel === 'collections' ? 'true' : 'false');
                }
                if (item.capture_id && item.passage_id) lineageForm.requestSubmit();
                else collectionCaptureForm.requestSubmit();
              });
              candidateQueueLinks.append(button);
            }
            if (queue.next_after_candidate_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva della coda Candidate';
              more.addEventListener('click', () => {
                if (!candidateQueueLinks.contains(more)) return;
                candidateQueueForm.elements.namedItem('after_candidate_id').value = queue.next_after_candidate_id;
                candidateQueueForm.elements.namedItem('expected_snapshot_sha256').value = queue.snapshot_sha256;
                candidateQueueForm.requestSubmit();
              });
              candidateQueueLinks.append(more);
            }
            return;
          }
          if (form === coverageQueueForm) {
            results.textContent = 'Solo metadati convalidati di Coverage Need persistite.';
            const queue = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && queue?.contract_version === 'studio-coverage-need-queue-pg-v1'
              && queue.private_only === true && queue.read_only === true
              && queue.publication_authority === false && queue.triage_action_authorized === false
              && queue.rights_clearance === false && queue.collection_id === data.collection_id
              && ['ACTIVE','PAUSED','ARCHIVED'].includes(queue.collection_status)
              && typeof queue.snapshot_sha256 === 'string'
              && /^[0-9a-f]{64}$/.test(queue.snapshot_sha256)
              && (!data.expected_snapshot_sha256 || data.expected_snapshot_sha256 === queue.snapshot_sha256)
              && Array.isArray(queue.rows) && queue.rows.length <= data.limit
              && queue.rows.every(item => item.collection_id === data.collection_id
                && SAFE_REF.test(item.need_id) && SAFE_REF.test(item.need_type)
                && SAFE_REF.test(item.requirement_kind)
                && ['OPEN','SEARCHING','BLOCKED'].includes(item.status)
                && ['BLOCKED','NEEDS_REVIEW'].includes(item.state)
                && Number.isInteger(item.attempt_count) && Number.isInteger(item.max_attempts)
                && item.attempt_count >= 0 && item.attempt_count <= item.max_attempts
                && item.max_attempts >= 1 && item.max_attempts <= 10
                && (item.event_id == null || SAFE_REF.test(item.event_id))
                && (item.atomic_claim_id == null || SAFE_REF.test(item.atomic_claim_id))
                && (item.claim_candidate_id == null || SAFE_REF.test(item.claim_candidate_id))
                && (item.source_intelligence_assessment_id == null || SAFE_REF.test(item.source_intelligence_assessment_id))
                && Array.isArray(item.blockers) && item.blockers.length > 0
                && item.blockers.every(code => SAFE_REF.test(code))
                && SAFE_REF.test(item.retry_condition))
              && (queue.next_after_need_id == null || (
"""
