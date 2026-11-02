import assert from "node:assert/strict";

// Inspect the actual DOM at each public layout width, not just component markup.
export async function assertAtlasReadingPath(cdp, family, variant) {
  if (family === "home") return;
  const selector = family === "method" || family === "utility"
    ? ".atlas-utility-path a" : ".atlas-route li";
  const count = await cdp.evaluate("document.querySelectorAll('" + selector + "').length");
  assert.equal(count, 3, family + " " + variant + ": Atlante reading path missing");

  if (family === "statement") {
    const sourceFirst = await cdp.evaluate("(() => { const source = document.querySelector('.dp-provenance-disclosure'); const finding = document.querySelector('.dp-finding-summary'); return source && finding ? Boolean(source.compareDocumentPosition(finding) & Node.DOCUMENT_POSITION_FOLLOWING) : null; })()");
    if (sourceFirst !== null) {
      assert(sourceFirst, "Atlante statement must present provenance before summary");
    }
  }
}
