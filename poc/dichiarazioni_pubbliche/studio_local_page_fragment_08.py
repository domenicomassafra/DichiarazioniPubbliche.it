"""Immutable private Studio HTML fragment 9/11."""

PART = r"""                SAFE_REF.test(queue.next_after_need_id)
                && queue.rows.length === data.limit
                && queue.next_after_need_id === queue.rows.at(-1)?.need_id));
            if (!valid) {
              coverageQueueSummary.textContent = 'Coverage Needs non verificabili o snapshot non corrente.';
              status.textContent = 'Coverage Needs non verificabili.';
              return;
            }
            coverageQueueSummary.textContent = queue.rows.length + ' Coverage Needs persistite'
              + ' · raccolta ' + queue.collection_id + '. Nessun intervento autorizzato.';
            for (const item of queue.rows) {
              const line = document.createElement('p');
              line.textContent = item.need_id + ' · ' + item.need_type + ' · ' + item.status
                + ' · tentativi ' + item.attempt_count + '/' + item.max_attempts
                + ' · evento ' + (item.event_id || 'non attestato')
                + ' · blocchi: ' + item.blockers.join(', ')
                + ' · retry: ' + item.retry_condition;
              coverageQueueLinks.append(line);
            }
            if (queue.next_after_need_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva delle Coverage Needs';
              more.addEventListener('click', () => {
                if (!coverageQueueLinks.contains(more)) return;
                coverageQueueForm.elements.namedItem('after_need_id').value = queue.next_after_need_id;
                coverageQueueForm.elements.namedItem('expected_snapshot_sha256').value = queue.snapshot_sha256;
                coverageQueueForm.requestSubmit();
              });
              coverageQueueLinks.append(more);
            }
            return;
          }
          if (form === inboxForm) {
            results.textContent = 'Solo riferimenti Discovery validati nell’Inbox.';
            const inbox = receipt?.data;
            const queueTypes = new Set(['NEW_CONTENT', 'EXISTING_CONTENT', 'DUPLICATE_WITHIN_RUN',
              'HOST_LIMIT', 'RESULT_LIMIT', 'OUTSIDE_DATE_WINDOW', 'REJECTED_POLICY',
              'AMBIGUOUS_CONTENT_IDENTITY']);
            const queueLabels = {
              NEW_CONTENT: 'Nuova fonte', EXISTING_CONTENT: 'Contenuto già presente',
              DUPLICATE_WITHIN_RUN: 'Doppione nella scoperta',
              HOST_LIMIT: 'Limite sorgente', RESULT_LIMIT: 'Limite risultati',
              OUTSIDE_DATE_WINDOW: 'Fuori intervallo date',
              REJECTED_POLICY: 'Escluso dalla policy',
              AMBIGUOUS_CONTENT_IDENTITY: 'Identità non risolta'
            };
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && inbox?.contract_version === 'studio-discovery-inbox-v2'
              && inbox.collection_id === data.collection_id
              && inbox.private_only === true && inbox.read_only === true
              && inbox.action_authorized === false && inbox.publication_authority === false
              && Array.isArray(inbox.rows) && inbox.rows.length <= data.limit
              && inbox.rows.every(row =>
                row.collection_id === data.collection_id && SAFE_REF.test(row.hit_id)
                && queueTypes.has(row.queue)
                && (row.content_id === null || SAFE_REF.test(row.content_id))
                && (row.reason_code === null || SAFE_REF.test(row.reason_code))
                && row.provenance_path?.hit_id === row.hit_id
                && row.provenance_path?.collection_id === data.collection_id
                && ['run_id', 'query_id', 'manifest_id'].every(
                  key => SAFE_REF.test(row.provenance_path[key]))
                && row.private_only === true && row.read_only === true
                && row.action_authorized === false && row.publication_authority === false
                && (row.annotation_revision === null ||
                  Number.isSafeInteger(row.annotation_revision) && row.annotation_revision >= 0)
                && Array.isArray(row.blockers) && row.blockers.every(code => SAFE_REF.test(code))
                && Array.isArray(row.unblock_conditions)
                && row.unblock_conditions.length === row.blockers.length
                && row.unblock_conditions.every((item, i) =>
                  item.blocker === row.blockers[i] && SAFE_REF.test(item.unblock_condition)))
              && (inbox.next_after_id === null || SAFE_REF.test(inbox.next_after_id));
            if (!valid) {
              inboxAnnotationSummary.textContent = 'Inbox non verificabile, nessun Hit navigabile.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            const count = type => inbox.rows.filter(row => row.queue === type).length;
            const needsAttention = inbox.rows.filter(row =>
              row.blockers.length > 0 || row.queue === 'AMBIGUOUS_CONTENT_IDENTITY').length;
            inboxAnnotationSummary.textContent = 'Pagina corrente: ' + inbox.rows.length
              + ' risultati · nuove ' + count('NEW_CONTENT')
              + ' · esistenti ' + count('EXISTING_CONTENT')
              + ' · doppioni ' + count('DUPLICATE_WITHIN_RUN')
              + ' · da analizzare ' + needsAttention
              + '. Seleziona una voce per consultare lo storico.';
            for (const row of inbox.rows) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = queueLabels[row.queue] + ' · Hit ' + row.hit_id
                + (row.content_id ? ' · Content ' + row.content_id : '')
                + (row.reason_code ? ' · motivo ' + row.reason_code : '')
                + ' · revisione '
                + (row.annotation_revision === null ? 'lineage non verificata' : row.annotation_revision)
                + ' · da verificare: ' + (row.unblock_conditions.map(item =>
                  item.blocker + ' → ' + item.unblock_condition).join('; ') || 'nessun blocco segnalato');
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
            if (inbox.next_after_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva della Discovery Inbox';
              more.addEventListener('click', () => {
                if (!inboxAnnotationLinks.contains(more)) return;
                inboxForm.elements.namedItem('after_id').value = inbox.next_after_id;
                inboxForm.requestSubmit();
              });
              inboxAnnotationLinks.append(more);
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
"""
