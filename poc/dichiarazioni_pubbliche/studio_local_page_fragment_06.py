"""Immutable private Studio HTML fragment 7/11."""

PART = r"""              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva dei Content inclusi';
              more.addEventListener('click', () => {
                collectionNavigationForm.elements.namedItem('after_content_id').value = tree.next_after_content_id;
                collectionNavigationForm.requestSubmit();
              });
              collectionNavigationLinks.append(more);
            }
            collectionNavigationHeading.focus();
            return;
          }
          if (form === decisionForm) {
            results.textContent = 'Solo stato e hash della ricevuta privata verificata.';
            const decision = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && decision?.contract_version === 'studio-candidate-decision-receipt-v1'
              && decision.private_only === true && decision.historical_only === true
              && decision.review_authority === false && decision.promotion_authority === false
              && decision.publication_authority === false && decision.rights_clearance === false
              && ['HOLD','REJECT','REVIEW_CREATE','REVIEW_LINK'].includes(decision.decision)
              && ['HISTORICAL_SOURCE_CURRENT','HISTORICAL_SOURCE_WITHDRAWN'].includes(decision.status)
              && Number.isSafeInteger(decision.revision) && decision.revision > 0
              && SAFE_SHA256.test(decision.receipt_sha256)
              && ['candidate_id','run_id','capture_id','passage_id','request_key'].every(
                name => decision[name] === data[name] && SAFE_REF.test(decision[name]));
            if (!valid) {
              decisionSummary.textContent = 'Ricevuta assente, non configurata o non verificabile.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            decisionSummary.textContent = 'Decisione ' + decision.decision
              + ' · revisione ' + decision.revision
              + ' · ricevuta SHA-256 ' + (decision.receipt_sha256 || 'non prodotta')
              + ' · ' + decision.status
              + '. Storico soltanto: nessuna promozione o pubblicazione autorizzata.';
            return;
          }
          if (form === candidateWriteForm) {
            results.textContent = 'Solo stato sanitizzato dell’intenzione privata firmata.';
            const decision = receipt?.data;
            const code = decision?.result_code;
            const confirmed = ['CREATED','REPLAY'].includes(code);
            const valid = receipt?.contract_version === 'studio-private-candidate-decision-api-v1'
              && decision?.contract_version === 'studio-private-candidate-decision-write-v1'
              && decision.private_only === true && decision.mutation_kind === 'REVIEW_INTENT_ONLY'
              && decision.candidate_id === data.candidate_id && decision.run_id === data.run_id
              && decision.capture_id === data.capture_id && decision.passage_id === data.passage_id
              && decision.decision === data.decision
              && decision.promoted === false && decision.promotion_authority === false
              && decision.publication_authority === false && decision.source_rights_approved === false
              && Number.isSafeInteger(decision.revision) && decision.revision >= 0
              && (confirmed ? SAFE_SHA256.test(decision.receipt_sha256)
                : decision.receipt_sha256 == null || SAFE_SHA256.test(decision.receipt_sha256))
              && ['CREATED','REPLAY','HELD_SOURCE','REVISION_CONFLICT','IDEMPOTENCY_CONFLICT'].includes(code)
              && response.ok === confirmed;
            if (!valid) {
              candidateWriteSummary.textContent = 'Intenzione non attestata. Nessun salvataggio confermato.';
              status.textContent = 'Writer non disponibile o firma/sorgente non verificabile.';
              return;
            }
            candidateWriteSummary.textContent = code + ' · revisione ' + decision.revision
              + ' · ricevuta SHA-256 ' + decision.receipt_sha256
              + '. Storico privato soltanto: nessun Claim creato o pubblicazione autorizzata.';
            if (confirmed) {
              decisionForm.elements.namedItem('candidate_id').value = data.candidate_id;
              decisionForm.elements.namedItem('run_id').value = data.run_id;
              decisionForm.elements.namedItem('capture_id').value = data.capture_id;
              decisionForm.elements.namedItem('passage_id').value = data.passage_id;
              decisionForm.elements.namedItem('request_key').value = data.request_key;
              status.textContent = 'Intenzione persistita: rileggi lo storico e i diritti correnti.';
            }
            return;
          }
          if (form === lineageForm) {
            // Never dump unvalidated data into the shared results panel.
            results.textContent = 'Solo riferimenti validati nel dettaglio della raccolta.';
            const match = receipt?.data;
            const scope = scopedCaptureReference;
            const validScope = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && match?.contract_version === 'studio-operator-queues-v1'
              && match.private_only === true && match.rights_clearance === false
              && match.review_authority_evaluated === false && match.publication_authority === false
              && match.collection_id === data.collection_id && match.content_id === data.content_id
              && match.capture_id === data.capture_id && match.passage?.id === data.passage_id
              && scope?.collection_id === data.collection_id && scope?.content_id === data.content_id
              && scope?.capture_id === data.capture_id
              && match.capture_sha256 === scope?.capture_sha256
              && SAFE_SHA256.test(match.capture_sha256) && SAFE_SHA256.test(match.passage?.text_sha256)
              && SAFE_REF.test(match.source_id) && match.source_id === scope.source_id
              && match.source_exists === true && SAFE_REF.test(match.rights_status)
              && SAFE_REF.test(match.processing_status) && SAFE_REF.test(match.collection_state)
              && ['TEXT_POSITION', 'PAGE_RANGE'].includes(match.passage?.selector_type)
              && Array.isArray(match.blockers) && match.blockers.every(code => SAFE_REF.test(code))
              && Array.isArray(match.candidates) && match.candidates.length <= data.limit;
            const validCandidates = validScope && match.candidates.every(candidate =>
              SAFE_REF.test(candidate.id) && SAFE_REF.test(candidate.status)
              && SAFE_SHA256.test(candidate.statement_text_hash)
              && candidate.review_authority_evaluated === false
              && Number.isInteger(candidate.claim_candidate_count)
              && candidate.claim_candidate_count >= 0
              && typeof candidate.claim_candidates_truncated === 'boolean'
              && Array.isArray(candidate.claim_candidates) && candidate.claim_candidates.length <= 5
              && candidate.claim_candidate_count >= candidate.claim_candidates.length
              && candidate.claim_candidates_truncated ===
                (candidate.claim_candidate_count > candidate.claim_candidates.length)
              && candidate.claim_candidates.every(claim =>
                SAFE_REF.test(claim.id) && SAFE_REF.test(claim.status)
                && claim.promotion_authority_evaluated === false
                && (claim.status === 'PROMOTED'
                  ? SAFE_REF.test(claim.recorded_promoted_claim_id)
                    && SAFE_REF.test(claim.promotion_receipt_id)
                  : !claim.recorded_promoted_claim_id && !claim.promotion_receipt_id)));
            const validCursor = validScope && (match.next_after_statement_id == null
              || (match.candidates.length === data.limit
                  && SAFE_REF.test(match.next_after_statement_id)
                  && match.next_after_statement_id === match.candidates.at(-1)?.id
                  && (!data.after_statement_id || match.next_after_statement_id > data.after_statement_id)));
            if (!validCandidates || !validCursor) {
              status.textContent = 'Dati non verificabili.';
              lineageSummary.textContent = 'Collegamento non verificabile o risposta non conforme.';
              return;
            }
            status.textContent = 'Collegamenti persistiti recuperati, senza approvazione.';
            const passage = match.passage;
            const position = passage.selector_type === 'TEXT_POSITION'
              ? 'caratteri ' + passage.start_char + '–' + passage.end_char
              : 'pagine ' + passage.page_start + '–' + passage.page_end;
            const validPosition = passage.selector_type === 'TEXT_POSITION'
              ? Number.isInteger(passage.start_char) && passage.start_char >= 0
                && Number.isInteger(passage.end_char) && passage.end_char > passage.start_char
              : Number.isInteger(passage.page_start) && passage.page_start >= 1
                && Number.isInteger(passage.page_end) && passage.page_end >= passage.page_start;
            if (!validPosition) {
              lineageSummary.textContent = 'Selettore scritto non conforme.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            lineageSummary.textContent = 'Collection ' + match.collection_id + ' · Content ' + match.content_id
              + ' · fonte ' + match.source_id + ' · Capture ' + match.capture_id
              + ' · Passage ' + passage.id + ' (' + position + ') · diritti '
              + match.rights_status + ' · blocchi: ' + match.blockers.join(', ')
              + ' · pagina di ' + match.candidates.length
              + ' Statement. Revisione e pubblicazione non autorizzate.';
            for (const candidate of match.candidates) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = 'Statement ' + candidate.id + ' · ' + candidate.status
                + ' · Claim Candidate ' + (candidate.claim_candidates.map(claim =>
                  claim.id + ' (' + claim.status + ')'
                  + (claim.status === 'PROMOTED' ? ' → Claim ' + claim.recorded_promoted_claim_id : '')
                ).join(', ') || 'nessuno')
                + (candidate.claim_candidates_truncated ? ' · altri Claim Candidate non caricati' : '');
              button.addEventListener('click', () => {
                if (!lineageLinks.contains(button)) return;
                candidateDetail.textContent = 'Statement ' + candidate.id
                  + ' · hash ' + candidate.statement_text_hash
                  + ' · ' + candidate.claim_candidate_count + ' Claim Candidate persistiti'
                  + ' · ricevute promozione: ' + (candidate.claim_candidates
                    .filter(claim => claim.status === 'PROMOTED')
                    .map(claim => claim.promotion_receipt_id).join(', ') || 'nessuna')
                  + '. Stato registrato; nessuna autorità di revisione o pubblicazione.';
                lineageInspector.hidden = false;
                candidateHeading.focus();
              });
              lineageLinks.append(button);
              for (const claim of candidate.claim_candidates) {
                if (claim.status !== 'CANDIDATE') continue;
                const prepare = document.createElement('button');
                prepare.type = 'button';
                prepare.textContent = 'Prepara intenzione privata per Claim Candidate ' + claim.id;
                prepare.addEventListener('click', () => {
                  if (!lineageLinks.contains(prepare)) return;
                  // A persisted provenance path can *populate scope IDs* only:
                  // no MatchRun fingerprint, CAS revision or reviewer signature
                  // is derived from this historical read-only inspection.
                  for (const field of candidateWriteForm.querySelectorAll('input,select,textarea')) {
                    if (field.name === 'decision') field.value = 'HOLD';
                    else if (field.name === 'expected_revision') field.value = '0';
                    else field.value = '';
                  }
"""
