import assert from "node:assert/strict";

// Explore's public record-type radio group must remain operable with native
// arrow keys, and the selected value must agree with the visible rows, URL,
// and accessibility tree. This exercises the actual rendered type order.
export async function checkExploreKindRadios({ cdp, key, waitFor, searchIndex, routes }) {
  const axValue = (node, field) => node[field]?.value ?? "";
  const assertRadioAx = async (name, checked) => {
    const nodes = (await cdp.send("Accessibility.getFullAXTree")).nodes;
    const radio = nodes.find((node) => axValue(node, "role") === "radio" && axValue(node, "name") === name);
    assert(radio, `${name}: selected state absent from accessibility tree`);
    const checkedValue = radio.properties?.find((property) => property.name === "checked")?.value?.value;
    assert.equal(String(checkedValue), String(checked), `${name}: assistive-tech checked state differs from DOM selection`);
  };
  const selectNextKind = async (kind, name) => {
    await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
    await waitFor(cdp, `document.querySelector('input[type=radio][value=${kind}]').checked`, `${kind}: keyboard transition failed`);
    const count = searchIndex.records.filter((record) => record.kind === kind).length;
    await waitFor(cdp, `document.querySelectorAll('.explore-row').length === ${count}`, `${kind}: visible results differ from approved index`);
    assert.match(await cdp.evaluate("location.search"), new RegExp(`[?&]tipo=${kind}(?:&|$)`), `${kind}: URL filter mismatch`);
    await assertRadioAx(name, "true");
    return count;
  };
  await assertRadioAx("Tutto", "true");

  await cdp.evaluate("document.querySelector('input[type=radio][value=ALL]').focus()");
  const findingCount = await selectNextKind("finding", "Dichiarazioni");
  assert.equal(await cdp.evaluate("document.activeElement?.value"), "finding", "selected radio did not retain keyboard focus");
  await waitFor(cdp, `document.querySelector('.results-count')?.textContent?.includes('${findingCount} risultat')`, "filtered finding count not updated for screen readers");
  await assertRadioAx("Tutto", "false");

  // The public type grammar includes Originali between Dichiarazioni and Persone.
  // Exercise each native-radio arrow step; skipping an option would mask a
  // keyboard-navigation regression instead of checking the rendered order.
  await selectNextKind("statement", "Originali");

  const personCount = await selectNextKind("person", "Persone");
  assert.equal(await cdp.evaluate("document.querySelector('.results-count[aria-live=polite]')?.textContent.trim()"),
    `${personCount} ${personCount === 1 ? "risultato" : "risultati"}`,
    "filtered Person result count not announced semantically");
  const personLinks = await cdp.evaluate("[...document.querySelectorAll('.explore-row .claim-row-claim')].map(link => link.getAttribute('href'))");
  assert(personLinks.every((route) => route.startsWith("/persone/") && routes.includes(route)),
    "Person results link outside built canonical destinations");
}
