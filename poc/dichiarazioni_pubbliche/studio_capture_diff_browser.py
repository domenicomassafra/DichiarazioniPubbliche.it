"""Private, DOM-only helpers for the bounded Capture Passage comparison."""

CAPTURE_DIFF_BROWSER_JS = r"""
    function validCaptureComparisonScope(receipt, request) {
      const scope = receipt?.data;
      return receipt?.contract_version === 'studio-local-readonly-api-v1'
        && scope?.contract_version === 'studio-capture-inspection-v1'
        && scope.private_only === true && scope.rights_clearance === false
        && scope.publication_authority === false
        && SAFE_REF.test(request.content_id) && scope.content_id === request.content_id
        && SAFE_REF.test(scope.earlier?.id) && SAFE_REF.test(scope.later?.id)
        && scope.earlier.id !== scope.later.id
        && SAFE_SHA256.test(request.earlier_hash) && SAFE_SHA256.test(request.later_hash)
        && request.earlier_hash !== request.later_hash
        && scope.earlier.content_sha256 === request.earlier_hash
        && scope.later.content_sha256 === request.later_hash;
    }
    function validAuditLocator(locator, contentId, capture, passageId) {
      return locator && !Array.isArray(locator) && typeof locator === 'object'
        && Object.keys(locator).length === 4
        && locator.content_id === contentId && locator.capture_id === capture.id
        && locator.capture_sha256 === capture.content_sha256
        && locator.passage_id === passageId;
    }
    function validCaptureDiffRow(row, contentId, earlier, later) {
      if (!row || typeof row !== 'object' || Array.isArray(row)
          || !['UNCHANGED','CHANGED','REMOVED','ADDED'].includes(row.change)) return false;
      const written = row.selector_type === 'TEXT_POSITION';
      if (!written && row.selector_type !== 'PAGE_RANGE') return false;
      const first = written ? row.start_char : row.page_start;
      const last = written ? row.end_char : row.page_end;
      if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last)
          || first < (written ? 0 : 1) || last < first + (written ? 1 : 0)
          || (written ? row.page_start !== null || row.page_end !== null
            : row.start_char !== null || row.end_char !== null)) return false;
      const before = row.earlier_passage_id !== null;
      const after = row.later_passage_id !== null;
      if (!before && !after) return false;
      if (before && (!SAFE_REF.test(row.earlier_passage_id)
          || !SAFE_SHA256.test(row.earlier_text_sha256)
          || !validAuditLocator(row.earlier_locator, contentId, earlier,
                                row.earlier_passage_id))) return false;
      if (after && (!SAFE_REF.test(row.later_passage_id)
          || !SAFE_SHA256.test(row.later_text_sha256)
          || !validAuditLocator(row.later_locator, contentId, later,
                                row.later_passage_id))) return false;
      if (!before && (row.earlier_text_sha256 !== null || row.earlier_locator !== null)) return false;
      if (!after && (row.later_text_sha256 !== null || row.later_locator !== null)) return false;
      return row.change === (before && after
        ? row.earlier_text_sha256 === row.later_text_sha256 ? 'UNCHANGED' : 'CHANGED'
        : before ? 'REMOVED' : 'ADDED');
    }
    function renderCaptureDiffDetails(receipt, request, container, copyStatus, stillCurrent) {
      const scope = receipt?.data;
      const comparison = scope?.selector_comparison;
      if (!validCaptureComparisonScope(receipt, request)
          || comparison?.status !== 'COMPLETE' || comparison.complete !== true
          || comparison.max_per_version !== 20
          || !Array.isArray(comparison.changes) || comparison.changes.length > 40) return false;
      const counts = {UNCHANGED: 0, CHANGED: 0, ADDED: 0, REMOVED: 0};
      const anchors = new Set();
      for (const row of comparison.changes) {
        if (!validCaptureDiffRow(row, scope.content_id, scope.earlier, scope.later)) return false;
        const anchor = JSON.stringify([
          row.selector_type, row.start_char, row.end_char, row.page_start, row.page_end,
        ]);
        if (anchors.has(anchor)) return false;
        anchors.add(anchor);
        counts[row.change]++;
      }
      if (!comparison.counts || Object.keys(counts).some(
        kind => comparison.counts[kind] !== counts[kind])
          || counts.UNCHANGED + counts.CHANGED + counts.REMOVED > 20
          || counts.UNCHANGED + counts.CHANGED + counts.ADDED > 20) return false;
      // Nothing from a malformed response is appended, even if its first rows look safe.
      for (const row of comparison.changes) {
        const item = document.createElement('p');
        const position = row.selector_type === 'TEXT_POSITION'
          ? 'caratteri ' + row.start_char + '–' + row.end_char
          : 'pagine ' + row.page_start + '–' + row.page_end;
        item.textContent = row.change + ' · ' + position
          + ' · precedente: ' + (row.earlier_passage_id || 'assente')
          + (row.earlier_text_sha256 ? ' (hash ' + row.earlier_text_sha256 + ')' : '')
          + ' · successiva: ' + (row.later_passage_id || 'assente')
          + (row.later_text_sha256 ? ' (hash ' + row.later_text_sha256 + ')' : '');
        for (const [label, locator] of [
          ['precedente', row.earlier_locator], ['successiva', row.later_locator],
        ]) {
          if (!locator) continue;
          const audit = {
            content_id: locator.content_id, capture_id: locator.capture_id,
            capture_sha256: locator.capture_sha256, passage_id: locator.passage_id,
          };
          const copy = document.createElement('button');
          copy.type = 'button';
          copy.textContent = 'Copia riferimento ' + label + ' di ' + locator.passage_id;
          copy.addEventListener('click', async () => {
            if (!stillCurrent() || !container.contains(item)) return;
            try {
              if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText)
                throw new Error('clipboard unavailable');
              await navigator.clipboard.writeText(JSON.stringify(audit));
              if (stillCurrent() && container.contains(item))
                copyStatus.textContent = 'Riferimento privato copiato: ' + locator.passage_id;
            } catch (_) {
              if (stillCurrent() && container.contains(item))
                copyStatus.textContent = 'Copia automatica non disponibile: seleziona il codice di audit mostrato.';
            }
          });
          const code = document.createElement('code');
          code.textContent = JSON.stringify(audit);
          item.append(copy, code);
        }
        container.append(item);
      }
      return true;
    }
    function showCaptureComparison(receipt, data, generation) {
      const comparison = receipt?.data?.selector_comparison;
      const validScope = validCaptureComparisonScope(receipt, data);
      const validDetails = validScope && captureSelectorDiffDetails && captureCopyStatus && renderCaptureDiffDetails(
        receipt, data, captureSelectorDiffDetails, captureCopyStatus,
        () => generation === requestGeneration && /^[0-9a-f]{64,128}$/.test(token.value));
      const counts = comparison?.counts;
      const validCounts = counts && ['UNCHANGED', 'CHANGED', 'ADDED', 'REMOVED'].every(
        key => Number.isSafeInteger(counts[key]) && counts[key] >= 0 && counts[key] <= 20)
        && counts.UNCHANGED + counts.CHANGED + counts.REMOVED <= 20
        && counts.UNCHANGED + counts.CHANGED + counts.ADDED <= 20;
      const legacyCounts = comparison?.changes === undefined && comparison?.max_per_version === 20;
      if (validScope && comparison?.complete === true && comparison.status === 'COMPLETE'
          && validCounts && (validDetails || legacyCounts)) {
        captureSelectorDiffSummary.textContent = 'Selettori delle catture: '
            + comparison.counts.UNCHANGED + ' invariati, '
            + comparison.counts.CHANGED + ' modificati, '
            + comparison.counts.ADDED + ' aggiunti, '
            + comparison.counts.REMOVED + ' rimossi. '
            + (validDetails ? 'Riferimenti privati per versione.'
              : 'Solo conteggi; riferimenti di audit non disponibili.')
            + ' Nessun permesso di riproduzione.';
      } else if (validScope && comparison?.status === 'TRUNCATED'
          && comparison.complete === false && comparison.max_per_version === 20
          && Array.isArray(comparison.changes) && comparison.changes.length === 0) {
        captureSelectorDiffSummary.textContent = 'Confronto non completo: oltre 20 selettori in almeno una versione. '
          + 'Aprire i selettori paginati per ispezionarli. Nessuna differenza totale deducibile.';
      } else {
        captureSelectorDiffSummary.textContent = 'Differenze non verificabili: riferimenti di audit non disponibili.';
      }
      for (const position of validDetails ? ['earlier', 'later'] : []) {
        const capture = receipt.data?.[position];
        if (!SAFE_REF.test(capture?.id) || !SAFE_SHA256.test(capture?.content_sha256)
            || !SAFE_REF.test(receipt.data?.content_id)) continue;
        const link = document.createElement('button');
        link.type = 'button';
        link.textContent = (position === 'earlier' ? 'Precedente' : 'Successiva')
          + ' · selettori di ' + capture.id;
        link.addEventListener('click', () => {
          if (generation !== requestGeneration || !captureLinks.contains(link)) return;
          capturePassageForm.elements.namedItem('content_id').value = receipt.data.content_id;
          capturePassageForm.elements.namedItem('capture_hash').value = capture.content_sha256;
          capturePassageForm.elements.namedItem('after_id').value = '';
          capturePassageForm.requestSubmit();
        });
        captureLinks.append(link);
      }
    }
"""

__all__ = ["CAPTURE_DIFF_BROWSER_JS"]
