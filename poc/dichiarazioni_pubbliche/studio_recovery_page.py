"""Add a private DP-241 read-only panel to the existing Studio HTML shell.

The shared form submit code already validates the operator token and renders
the JSON response as text. This panel adds no client-side network lookup.
"""

_BUTTON = b'<button type="button" aria-pressed="false" data-panel="recovery">Recovery</button>'
_PANEL = """
<section class="pane" id="recovery" hidden>
  <h2>Fonte originale · indagine DP-241</h2>
  <p>Esito osservato, metodi, versioni e selettori, budget, domanda irrisolta e prossima azione. I risultati richiedono una revisione: nessuna autorità editoriale o di pubblicazione.</p>
  <form data-endpoint="/v1/recovery/observed">
    <div class="controls">
      <label>Case ID<input name="case_id" maxlength="80" required autocomplete="off" placeholder="dp241-nasa-apollo11-smallstep"></label>
      <button type="submit">Leggi indagine persistita</button>
    </div>
  </form>
  <p class="quiet">Accesso con token operatore al journal privato configurato. Questa pagina non avvia ricerche.</p>
</section>
""".encode("utf-8")


def with_recovery_panel(page: bytes) -> bytes:
    """Insert exactly one panel; fail closed if the expected Studio shell moves."""
    if (not isinstance(page, bytes) or page.count(b"</nav>") != 1
            or page.count(b"<section class=\"pane\" aria-labelledby=\"esito\">") != 1):
        raise ValueError("DP241_STUDIO_PAGE_SCOPE_CHANGED")
    return (page.replace(b"</nav>", _BUTTON + b"</nav>", 1)
            .replace(b'<section class="pane" aria-labelledby="esito">',
                     _PANEL + b'<section class="pane" aria-labelledby="esito">', 1))
