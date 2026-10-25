"""Nonce-bound Collection→Capture→written Passage navigation fragment."""

COLLECTION_CAPTURE_LINKS_JS = r"""
              const capture = item.latest_capture;
              if (!capture || !item.source_exists) continue;
              const captureLink = document.createElement('button');
              captureLink.type = 'button';
              captureLink.textContent = 'Capture ' + capture.id
                + ' · SHA-256 ' + capture.content_sha256
                + ' · ' + capture.passage_count + ' Passage'
                + (capture.passage_count === 0
                  ? ' · Passage assenti: Candidate non disponibili (HOLD)'
                  : ' · apri versioni e selettori persistiti');
              captureLink.addEventListener('click', () => {
                if (!collectionNavigationLinks.contains(captureLink)) return;
                collectionCaptureForm.elements.namedItem('collection_id').value = tree.collection_id;
                collectionCaptureForm.elements.namedItem('content_id').value = item.content_id;
                collectionCaptureForm.elements.namedItem('after_id').value = '';
                collectionCaptureForm.requestSubmit();
              });
              collectionNavigationLinks.append(captureLink);
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
                  for (const key of ['collection_id','content_id','capture_id','passage_id']) {
                    document.getElementById('source-exact-form').elements.namedItem(key).value =
                      key === 'collection_id' ? tree.collection_id :
                      key === 'content_id' ? item.content_id :
                      key === 'capture_id' ? capture.id : passage.id;
                  }
                  clearExactSourceJump();
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
"""
