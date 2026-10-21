"""Ephemeral quote-by-quote review in the existing private Candidate renderer.

Source excerpts are typed by the operator and never sent to the API, stored,
logged, or accepted as independently verified original-source quotations.
"""

from __future__ import annotations


_RELATIONS = frozenset({
    "DUPLICATE_EXTRACTION", "SAME_PROPOSITION", "RELATED", "DIFFERENT", "UNCERTAIN",
})


def quote_review_panel(*, relation: str, usable: bool, same_source: bool) -> str:
    """Attach one bounded, keyboard-native comparison to an existing match row."""
    if relation not in _RELATIONS or type(usable) is not bool or type(same_source) is not bool:
        raise ValueError("DP418_QUOTE_REVIEW_CONTEXT_INVALID")
    return (
        "<section data-private-quote-review data-match-class='" + relation
        + "' data-same-source='" + str(same_source).lower()
        + "' data-usable='" + str(usable).lower() + "'>"
        "<h4>Confronta le due citazioni</h4>"
        "<p>Riporta due estratti brevi dalla fonte originale. I testi inseriti "
        "rimangono in questa pagina privata e non sono attestazioni della fonte.</p>"
        "<label>Citazione A (Candidate, massimo 160 caratteri)"
        "<textarea data-quote-a maxlength='160' rows='3' autocomplete='off' "
        "style='width:100%;max-width:100%;box-sizing:border-box'></textarea></label>"
        "<label>Citazione B (risultato, massimo 160 caratteri)"
        "<textarea data-quote-b maxlength='160' rows='3' autocomplete='off' "
        "style='width:100%;max-width:100%;box-sizing:border-box'></textarea></label>"
        "<p role='status' aria-live='polite' data-quote-result>"
        "In attesa dei due estratti; nessuna decisione registrata.</p>"
        "</section>"
    )


QUOTE_REVIEW_SCRIPT = """<script>
function assessQuoteComparison(left, right, sameSource, relation, usable) {
  // Only display a tentative operator proposal. No database or network action.
  const result = (code, reason) => ({code, reason, approval: false});
  if (usable !== true) {
    return result('FONTE_BLOCCATA', 'Passaggio o diritti non verificabili: confronto sospeso.');
  }
  if (relation === 'UNCERTAIN') {
    return result('CONFRONTO_AMBIGUO', 'Il cluster resta incerto: serve verifica umana.');
  }
  if (typeof left !== 'string' || typeof right !== 'string'
      || left.length > 160 || right.length > 160) {
    return result('TESTO_NON_VALIDO', 'Estratti non validi: limite 160 caratteri.');
  }
  // Preserve negation, numbers, punctuation and case; collapse only whitespace.
  const compact = value => value.normalize('NFC').replace(/\\s+/g, ' ').trim();
  const a = compact(left);
  const b = compact(right);
  if (!a || !b) {
    return result('IN_ATTESA_TESTI', 'Inserire entrambi gli estratti per il confronto.');
  }
  if (a === b && sameSource === true && relation === 'DUPLICATE_EXTRACTION') {
    return result('POSSIBILE_DUPLICATO_PASSAGGIO',
      'Testo identico e stessa versione di fonte/Passage: proposta di doppione da verificare.');
  }
  if (a !== b) {
    return result('DICHIARAZIONI_DISTINTE',
      'I testi non coincidono; mantenere le dichiarazioni separate anche sullo stesso argomento.');
  }
  if (sameSource === true) {
    return result('CONFRONTO_AMBIGUO',
      'Testi uguali nello stesso passaggio ma classificazione persistita discordante: verificare.');
  }
  return result('TESTO_RIPETUTO_FONTI_DIVERSE',
    'Stesso testo, passaggi o versioni diversi: verificare senza unire le estrazioni.');
}
document.querySelectorAll('[data-private-quote-review]').forEach(panel => {
  const left = panel.querySelector('[data-quote-a]');
  const right = panel.querySelector('[data-quote-b]');
  const output = panel.querySelector('[data-quote-result]');
  function update() {
    const proposal = assessQuoteComparison(left.value, right.value,
      panel.dataset.sameSource === 'true', panel.dataset.matchClass,
      panel.dataset.usable === 'true');
    output.textContent = proposal.code + ': ' + proposal.reason
      + ' Nessuna decisione, merge o promozione automatica.';
  }
  left.addEventListener('input', update);
  right.addEventListener('input', update);
  window.addEventListener('pagehide', () => {
    left.value = '';
    right.value = '';
    output.textContent = 'Nessuna decisione registrata.';
  });
  update();
});
</script>"""


__all__ = ["quote_review_panel", "QUOTE_REVIEW_SCRIPT"]
