/** DP-412: Public Topic v3 design token and source-level accessibility contract.
 * The existing DP-406 Astro fixture covers rendering; this deliberately does
 * not claim a live screen-reader or browser AX pass (AC-412.5 remains open).
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const [component, tokens] = await Promise.all([
  readFile(new URL("src/components/PublicTopicV3.astro", root), "utf8"),
  readFile(new URL("src/styles/tokens.css", root), "utf8"),
]);
const css = component.match(/<style is:inline>([\s\S]*?)<\/style>/)?.[1];
assert.ok(css, "PublicTopicV3 must provide its local layout stylesheet");
assert.match(tokens, /--rule-hairline:\s*#[0-9a-fA-F]{6}\s*;/,
  "the approved informational separator token must be defined");
for (const selector of ["topic-v3-row", "topic-v3-aside"]) {
  const rule = css.match(new RegExp(`(?:^|\\n)\\s*\\.${selector}\\s*\\{([^}]+)\\}`))?.[1];
  assert.ok(rule, `${selector} missing`);
  assert.match(rule, /border-top:\s*1px solid var\(--rule-hairline\)\s*;/,
    `${selector}: content divider must use the canonical hairline token`);
}
assert.doesNotMatch(css, /#[\da-fA-F]{3,8}\b|var\(--color-border/,
  "Topic styling must not invent a hex fallback or undefined border token");

// Source-level semantic invariants: preserve explicit names, headings, native
// label associations, textual filter count and operable native controls.
assert.match(component, /<section aria-labelledby="topic-v3-statements"[^>]*>/);
assert.match(component, /<h2 id="topic-v3-statements"[^>]*>Opinioni pubblicate sul Tema<\/h2>/);
assert.match(component, /<aside aria-label="Indice delle fonti e delle persone"[^>]*>/);
assert.match(component, /<form[^>]+aria-label="Filtri delle opinioni pubbliche"[^>]*>/);
assert.match(component, /<label>Fonte\s*<select name="source"/);
assert.match(component, /<label>Dal <input name="from" type="date"/);
assert.match(component, /<label>Al <input name="to" type="date"/);
assert.match(component, /<button type="reset">Azzera filtri<\/button>/);
assert.match(component, /<span role="status" aria-live="polite" aria-atomic="true" data-topic-v3-count>/);
assert.match(component, /<details><summary>Identità e limiti del Tema<\/summary>/);

console.log("DP-412 PublicTopicV3 design token + source-level AX semantics PASS");
