"""Immutable private Studio HTML fragment 6/11."""

PART = r"""              && load.image_approval_authority === false
              && load.text_review_authority === false && load.source_rights_attested === false
              && ['total_members','blocked_members','review_only_members','capture_count',
                  'passage_count','statement_candidate_count','claim_candidate_count']
                  .every(key => count(load[key]))
              && load.total_members <= 500
              && load.blocked_members + load.review_only_members === load.total_members
              && Array.isArray(load.rows) && load.rows.length <= data.limit
              && load.rows.every((item,i) => allowRef(item.content_id)
                && (item.capture_id == null || allowRef(item.capture_id))
                && ['BLOCKED','REVIEW_ONLY'].includes(item.state)
                && allowRef(item.reason)
                && count(item.capture_count) && count(item.passage_count)
                && count(item.statement_candidates) && count(item.claim_candidates)
                && (i === 0 || item.content_id > load.rows[i-1].content_id))
              && Array.isArray(load.blocked_queue)
              && load.blocked_queue.length <= load.rows.length
              && load.blocked_queue.every(item => allowRef(item.content_id)
                && allowRef(item.reason) && allowRef(item.next_action)
                && load.rows.some(row => row.content_id === item.content_id
                  && row.state === 'BLOCKED' && row.reason === item.reason))
              && (load.next_cursor == null ||
                typeof load.next_cursor === 'string' &&
                /^[A-Za-z0-9_-]{20,2048}$/.test(load.next_cursor) &&
                load.rows.length === data.limit);
            if (!valid) {
              workloadSummary.textContent = 'Carico non disponibile o snapshot non verificabile.';
              status.textContent = 'Coda privata non verificabile.';
              return;
            }
            workloadSummary.textContent = load.total_members + ' Content inclusi; '
              + load.blocked_members + ' bloccati e ' + load.review_only_members
              + ' da ispezionare; ' + load.capture_count + ' Capture e '
              + load.passage_count + ' Passage. Nessun permesso di pubblicazione.';
            for (const item of load.rows) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = item.content_id + ' · ' + item.state + ' · ' + item.reason
                + ' · ' + item.passage_count + ' Passage · ' + item.claim_candidates + ' Claim Candidate';
              button.addEventListener('click', () => {
                if (!workloadLinks.contains(button)) return;
                collectionCaptureForm.elements.namedItem('collection_id').value = load.collection_id;
                collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                collectionCaptureForm.elements.namedItem('after_id').value = '';
                collectionCaptureForm.requestSubmit();
              });
              workloadLinks.append(button);
            }
            if (load.next_cursor) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva (stesso snapshot corrente)';
              more.addEventListener('click', () => {
                if (!workloadLinks.contains(more)) return;
                workloadForm.elements.namedItem('after').value = load.next_cursor;
                workloadForm.requestSubmit();
              });
              workloadLinks.append(more);
            }
            status.textContent = 'Carico privato letto; seleziona un Content per l’ispezione.';
            return;
          }
          if (form === collectionForm) {
            results.textContent = 'Solo ID persistiti della pagina Collections.';
            const listing = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && listing?.contract_version === 'studio-operator-queues-v1'
              && listing.private_only === true && listing.publication_authority === false
              && Array.isArray(listing.results) && listing.results.length <= data.limit
              && listing.results.every(item => SAFE_REF.test(item.id)
                && SAFE_REF.test(item.state) && Number.isSafeInteger(item.included_content_count)
                && item.included_content_count >= 0)
              && (listing.next_after_id == null || (SAFE_REF.test(listing.next_after_id)
                && listing.results.length === data.limit
                && listing.next_after_id === listing.results.at(-1)?.id));
            if (!valid) {
              status.textContent = 'Raccolte non verificabili.';
              collectionListSummary.textContent = 'Risposta non conforme: nessuna raccolta visualizzabile.';
              return;
            }
            status.textContent = 'Raccolte persistite caricate.';
            collectionListSummary.textContent = listing.results.length + ' raccolte in questa pagina. Seleziona una raccolta per vedere i Content inclusi.';
            for (const item of listing.results) {
              const button = document.createElement('button');
              button.type = 'button';
              button.textContent = 'Collection ' + item.id + ' · ' + item.state
                + ' · ' + item.included_content_count + ' Content inclusi';
              button.addEventListener('click', () => {
                if (!collectionLinks.contains(button)) return;
                collectionMembersForm.elements.namedItem('collection_id').value = item.id;
                collectionMembersForm.elements.namedItem('after_id').value = '';
                collectionMembersForm.requestSubmit();
              });
              collectionLinks.append(button);
            }
            if (listing.next_after_id) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva delle raccolte';
              more.addEventListener('click', () => {
                collectionForm.elements.namedItem('after_id').value = listing.next_after_id;
                collectionForm.requestSubmit();
              });
              collectionLinks.append(more);
            }
            return;
          }
          if (form === collectionNavigationForm) {
            results.textContent = 'Navigazione privata con soli riferimenti validati.';
            const tree = receipt?.data;
            const valid = response.ok && receipt?.contract_version === 'studio-local-readonly-api-v1'
              && tree?.contract_version === 'studio-collection-navigation-v1'
              && tree.private_only === true && tree.read_only === true
              && tree.publication_authority === false && tree.rights_clearance === false
              && tree.review_authority === false && tree.collection_id === data.collection_id
              && SAFE_REF.test(tree.collection_state)
              && Array.isArray(tree.members) && tree.members.length <= data.limit
              && tree.members.every(item =>
                SAFE_REF.test(item.content_id) && (item.source_id === null || SAFE_REF.test(item.source_id))
                && item.source_exists === Boolean(item.source_id)
                && SAFE_REF.test(item.rights_status) && SAFE_REF.test(item.processing_status)
                && Number.isSafeInteger(item.capture_count) && item.capture_count >= 0
                && item.source_preview_authorized === false && item.review_authority === false
                && Array.isArray(item.blockers) && item.blockers.every(code => SAFE_REF.test(code))
                && (item.latest_capture == null ? item.capture_count === 0
                  : SAFE_REF.test(item.latest_capture.id)
                    && SAFE_SHA256.test(item.latest_capture.content_sha256)
                    && SAFE_REF.test(item.latest_capture.status)
                    && SAFE_REF.test(item.latest_capture.hold_status)
                    && SAFE_REF.test(item.latest_capture.rights_status)
                    && Number.isSafeInteger(item.latest_capture.passage_count)
                    && typeof item.latest_capture.passages_truncated === 'boolean'
                    && Array.isArray(item.latest_capture.passages)
                    && item.latest_capture.passages.length <= 3
                    && item.latest_capture.passage_count >= item.latest_capture.passages.length
                    && item.latest_capture.passages.every(passage =>
                      SAFE_REF.test(passage.id) && SAFE_SHA256.test(passage.text_sha256)
                      && ['TEXT_POSITION','PAGE_RANGE'].includes(passage.selector_type)
                      && Number.isSafeInteger(passage.candidate_count)
                      && passage.candidate_count >= 0
                      && (passage.candidate_count === 0 ? passage.first_candidate_id === null
                        : SAFE_REF.test(passage.first_candidate_id)))))
              && (tree.next_after_content_id == null
                ? tree.has_more === false
                : tree.has_more === true && tree.members.length === data.limit
                  && tree.next_after_content_id === tree.members.at(-1)?.content_id);
            if (!valid) {
              collectionNavigationLinks.replaceChildren();
              collectionNavigationSummary.textContent = 'Snapshot non conforme: nessun riferimento visualizzabile.';
              status.textContent = 'Dati non verificabili.';
              return;
            }
            collectionNavigationSummary.textContent = tree.members.length
              + ' Content inclusi, ' + tree.collection_state
              + '. Nessuna fonte riproducibile né revisione approvata.';
            for (const item of tree.members) {
              const parent = document.createElement('button');
              parent.type = 'button';
              parent.textContent = 'Content ' + item.content_id
                + ' · fonte ' + (item.source_id || 'non collegata')
                + ' · ' + item.capture_count + ' Capture'
                + ' · ' + item.blockers.join(', ');
              parent.addEventListener('click', () => {
                if (!collectionNavigationLinks.contains(parent)) return;
                collectionCaptureForm.elements.namedItem('collection_id').value = tree.collection_id;
                collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                collectionCaptureForm.elements.namedItem('after_id').value = '';
                collectionCaptureForm.requestSubmit();
              });
              collectionNavigationLinks.append(parent);
              const capture = item.latest_capture;
              if (!capture || !item.source_exists) continue;
              for (const passage of capture.passages) {
                const next = document.createElement('button');
                next.type = 'button';
                next.textContent = 'Capture ' + capture.id + ' → Passage ' + passage.id
                  + ' · ' + passage.candidate_count + ' Statement Candidate'
                  + ' · primo ' + (passage.first_candidate_id || 'assente');
                next.addEventListener('click', () => {
                  if (!collectionNavigationLinks.contains(next)) return;
                  scopedCaptureReference = {
                    collection_id: tree.collection_id, content_id: item.content_id,
                    capture_id: capture.id, capture_sha256: capture.content_sha256,
                    source_id: item.source_id,
                  };
                  lineageForm.elements.namedItem('collection_id').value = tree.collection_id;
                  lineageForm.elements.namedItem('content_id').value = item.content_id;
                  lineageForm.elements.namedItem('capture_id').value = capture.id;
                  lineageForm.elements.namedItem('passage_id').value = passage.id;
                  lineageForm.elements.namedItem('limit').value = '20';
                  lineageForm.elements.namedItem('after_statement_id').value = '';
                  lineageForm.requestSubmit();
                });
                collectionNavigationLinks.append(next);
              }
            }
            if (tree.next_after_content_id) {
"""
