"""Private Studio media player HTML and browser script at one replacement seam.

The existing login page owns authentication, workspace and request generation;
these fragments add only the media player to that single private DOM.
"""
MEDIA_PLAYBACK_HTML = """      <form data-endpoint="/v1/media/capture-context">
        <div class="controls"><label>Content ID<input name="content_id" maxlength="180" required></label>
        <label>Statement Candidate ID<input name="statement_candidate_id" maxlength="180" required></label>
        <label>Passage ID<input name="passage_id" maxlength="180" required></label>
        <label>Capture ID<input name="capture_id" maxlength="180" required></label>
        <label>Capture SHA-256<input name="capture_sha256" minlength="64" maxlength="64" required></label>
        <button type="submit">Confronta timeline e conservazione</button></div>
      </form>
      <p id="media-capture-context-summary" role="status" aria-live="polite">Nessun contesto cattura verificato.</p>
      <h2>Ricevuta persistita Capture → Segment (metadati soltanto)</h2>
      <p>L'attestazione locale conserva Capture SHA, segmento e revisioni di revoca. È una dichiarazione di provenienza da verificare indipendentemente: non concede diritti o riproduzione e non espone il media.</p>
      <form data-endpoint="/v1/media/binding" aria-describedby="media-binding-summary">
        <div class="controls"><label>Binding ID<input name="binding_id" maxlength="180" required></label>
        <button type="submit">Rileggi stato corrente e revoche</button></div>
      </form>
      <p id="media-binding-summary" role="status" aria-live="polite">Nessun binding verificato.</p>
      <button type="button" id="media-play-button">Apri il media autenticato e raggiungi il segmento</button>
      <audio id="media-verified-audio" controls hidden preload="none" aria-label="Media autentico, segmento verificato"></audio>
      <p id="media-play-status" role="status" aria-live="polite">Riproduzione disponibile solo dopo verifica dei diritti correnti.</p>
      <p class="muted">Solo revisione privata: non autorizza la pubblicazione del candidato.</p>
"""

MEDIA_PLAYBACK_SETUP = """    const mediaPlayButton = document.getElementById('media-play-button');
    const mediaAudio = document.getElementById('media-verified-audio');
    const mediaPlayStatus = document.getElementById('media-play-status');
    let mediaObjectUrl = null;
    let mediaLoadTimeout = null;
    function clearMediaPlayback() {
      if (mediaLoadTimeout !== null) clearTimeout(mediaLoadTimeout);
      mediaLoadTimeout = null;
      // The old metadata-only Studio DOM fixtures contain no media element.
      if (!mediaAudio || typeof mediaAudio.pause !== 'function'
          || typeof mediaAudio.load !== 'function') return;
      mediaAudio.pause();
      mediaAudio.removeAttribute('src');
      mediaAudio.load();
      mediaAudio.hidden = true;
      delete mediaAudio.dataset.segmentEnd;
      if (mediaObjectUrl) URL.revokeObjectURL(mediaObjectUrl);
      mediaObjectUrl = null;
      mediaPlayStatus.textContent = 'Nessun media riproducibile per la sessione corrente.';
    }
"""

MEDIA_PLAYBACK_HANDLER = """    mediaAudio?.addEventListener?.('timeupdate', () => {
      const end = Number(mediaAudio.dataset.segmentEnd);
      if (Number.isFinite(end) && end > 0 && mediaAudio.currentTime >= end) {
        mediaAudio.pause();
        if (mediaAudio.currentTime > end + 0.08) mediaAudio.currentTime = end;
      }
    });
    mediaAudio?.addEventListener?.('error', () => {
      if (mediaAudio.hasAttribute('src')) {
        clearMediaPlayback();
        mediaPlayStatus.textContent = 'Audio non decodificabile: nessun seek verificato.';
      }
    });
    mediaPlayButton?.addEventListener?.('click', async () => {
      invalidateRequest();
      const bindingId = mediaBindingForm.elements.namedItem('binding_id').value.trim();
      if (!SAFE_REF.test(bindingId) || !/^[0-9a-f]{64,128}$/.test(token.value)) {
        mediaPlayStatus.textContent = 'Binding o autenticazione assenti.';
        return;
      }
      const generation = requestGeneration;
      const controller = new AbortController();
      activeRequest = controller;
      mediaPlayStatus.textContent = 'Rilettura di byte, provenienza e diritti in corso…';
      try {
        const response = await fetch('/v1/media/playback', {
          method: 'POST', credentials: 'omit', redirect: 'error',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token.value},
          signal: controller.signal, body: JSON.stringify({binding_id: bindingId}),
        });
        if (!response.ok) throw new Error('hold');
        const start = Number(response.headers.get('X-Seek-Start-Ms'));
        const end = Number(response.headers.get('X-Seek-End-Ms'));
        const size = Number(response.headers.get('Content-Length'));
        const contentType = response.headers.get('Content-Type');
        if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end)
            || start < 0 || end <= start || end - start > 30000
            || !Number.isSafeInteger(size) || size < 1 || size > 64 * 1024 * 1024
            || !['audio/ogg','audio/wav','audio/x-wav','audio/mp4'].includes(contentType)) throw new Error('invalid');
        const bytes = await response.arrayBuffer();
        if (generation !== requestGeneration) return;
        activeRequest = null;
        if (bytes.byteLength !== size) throw new Error('invalid');
        mediaObjectUrl = URL.createObjectURL(new Blob([bytes], {type: contentType}));
        mediaAudio.dataset.segmentEnd = String(end / 1000);
        mediaAudio.addEventListener('loadedmetadata', function verifiedMetadata() {
          mediaAudio.removeEventListener('loadedmetadata', verifiedMetadata);
          if (mediaLoadTimeout !== null) clearTimeout(mediaLoadTimeout);
          mediaLoadTimeout = null;
          if (generation !== requestGeneration) return;
          if (!Number.isFinite(mediaAudio.duration)
              || end / 1000 > mediaAudio.duration + 0.1) {
            clearMediaPlayback();
            return;
          }
          mediaAudio.currentTime = start / 1000;
        });
        mediaAudio.addEventListener('seeked', function verifiedSeek() {
          mediaAudio.removeEventListener('seeked', verifiedSeek);
          if (generation !== requestGeneration) return;
          const actual = mediaAudio.currentTime;
          if (Math.abs(actual - start / 1000) > 0.1) {
            clearMediaPlayback();
            return;
          }
          mediaAudio.hidden = false;
          mediaPlayStatus.textContent = 'Seek reale: ' + actual.toFixed(3)
            + ' s · intervallo ' + (start / 1000).toFixed(3)
            + '–' + (end / 1000).toFixed(3) + ' s.';
        });
        mediaAudio.src = mediaObjectUrl;
        mediaAudio.load();
        mediaLoadTimeout = setTimeout(() => {
          if (generation !== requestGeneration || mediaAudio.readyState >= 1) return;
          clearMediaPlayback();
          mediaPlayStatus.textContent = 'Decoder audio non disponibile: nessun seek verificato.';
        }, 8000);
      } catch (_error) {
        if (generation !== requestGeneration) return;
        activeRequest = null;
        clearMediaPlayback();
        mediaPlayStatus.textContent = 'Riproduzione negata: provenienza, byte o diritti non verificabili.';
      }
    });
"""
