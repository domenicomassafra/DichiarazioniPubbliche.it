"""Immutable private Studio HTML fragment 11/11."""

PART = r"""                for (const panel of panels) panel.hidden = panel.id !== 'captures';
                capturePassageForm.elements.namedItem('content_id').value = captureData.content_id;
                capturePassageForm.elements.namedItem('capture_hash').value = capture.content_sha256;
                capturePassageForm.elements.namedItem('after_id').value = '';
                capturePassageForm.requestSubmit();
              });
              collectionCaptureLinks.append(button);
            }
            // Keyset continuation only; no unbounded fetch or client-side full-corpus load.
            if (captureData.has_more === true && SAFE_REF.test(captureData.next_after_id)) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Carica pagina successiva delle catture';
              more.addEventListener('click', () => {
                collectionCaptureForm.elements.namedItem('after_id').value = captureData.next_after_id;
                collectionCaptureForm.requestSubmit();
              });
              collectionCaptureLinks.append(more);
            }
            if (captures.length >= 2) {
              const byTime = [...captures].sort((left, right) =>
                Date.parse(left.observed_at) - Date.parse(right.observed_at));
              const first = byTime[0], last = byTime[byTime.length - 1];
              if (Date.parse(first.observed_at) < Date.parse(last.observed_at)) {
                const compare = document.createElement('button');
                compare.type = 'button';
                compare.textContent = 'Confronta prima e ultima cattura visibili';
                compare.addEventListener('click', () => {
                  for (const panelButton of document.querySelectorAll('[data-panel]')) {
                    panelButton.setAttribute('aria-pressed', panelButton.dataset.panel === 'captures' ? 'true' : 'false');
                  }
                  for (const panel of panels) panel.hidden = panel.id !== 'captures';
                  compareForm.elements.namedItem('content_id').value = captureData.content_id;
                  compareForm.elements.namedItem('earlier_hash').value = first.content_sha256;
                  compareForm.elements.namedItem('later_hash').value = last.content_sha256;
                  compareForm.requestSubmit();
                });
                collectionCaptureLinks.append(compare);
              }
            }
          }
          if (form === passageCandidateForm) {
            const match = receipt.data;
            if (!response.ok || receipt.contract_version !== 'studio-local-readonly-api-v1'
                || match?.contract_version !== 'studio-passage-candidates-v1'
                || match.private_only !== true || match.publication_authority !== false
                || match.review_authority !== false || match.rights_clearance !== false
                || match.collection_id !== data.collection_id
                || match.content_id !== data.content_id || match.passage_id !== data.passage_id
                || !Array.isArray(match.candidates) || match.candidates.length > 20) {
              passageCandidateSummary.textContent = 'Collegamenti non verificabili.';
              return;
            }
            passageCandidateSummary.textContent = match.candidates.length
              ? match.candidates.length + ' Statement Candidate con collegamento persistito. Revisione non verificata.'
              : 'Nessun candidato persistito collegato a questo Passage.';
            for (const candidate of match.candidates) {
              if (!SAFE_REF.test(candidate.statement_candidate_id)
                  || !Array.isArray(candidate.claim_candidates)) continue;
              const button = document.createElement('button');
              button.type = 'button';
              const linkedClaims = candidate.claim_candidates.map(c =>
                SAFE_REF.test(c.id) ? c.id + (SAFE_REF.test(c.promoted_claim_id)
                  ? ' → ' + c.promoted_claim_id : '') : '').filter(Boolean);
              button.textContent = 'Statement ' + candidate.statement_candidate_id
                + ' · ' + candidate.status + ' · Claim candidate/storici: '
                + (linkedClaims.join(', ') || 'nessuno');
              button.addEventListener('click', () => {
                if (match.selector_type !== 'MEDIA_SEGMENT_REF') return;
                mediaForm.elements.namedItem('content_id').value = match.content_id;
                mediaForm.elements.namedItem('statement_candidate_id').value = candidate.statement_candidate_id;
                mediaForm.elements.namedItem('passage_id').value = match.passage_id;
                mediaForm.requestSubmit();
              });
              passageCandidateLinks.append(button);
            }
            if (match.has_more === true && SAFE_REF.test(match.next_after_id)) {
              const more = document.createElement('button');
              more.type = 'button';
              more.textContent = 'Pagina successiva dei candidati';
              more.addEventListener('click', () => {
                passageCandidateForm.elements.namedItem('after_id').value = match.next_after_id;
                passageCandidateForm.requestSubmit();
              });
              passageCandidateLinks.append(more);
            }
          }
        } catch (_) {
          if (generation !== requestGeneration) return;
          activeRequest = null;
          status.textContent = 'Servizio locale non disponibile.';
          results.textContent = 'Nessun risultato.';
        }
      });
    }
  </script>
</body></html>
"""
