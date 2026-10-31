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
  await assertRadioAx("Tutto", "true");

  await cdp.evaluate("document.querySelector('input[type=radio][value=ALL]').focus()");
  await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(cdp, "document.querySelector('input[type=radio][value=finding]').checked", "arrow-key radio transition failed");
  assert.equal(await cdp.evaluate("document.activeElement?.value"), "finding", "selected radio did not retain keyboard focus");
  assert.match(await cdp.evaluate("location.search"), /tipo=finding/, "keyboard filter transition did not serialize URL state");
  const findingCount = searchIndex.records.filter((record) => record.kind === "finding").length;
  await waitFor(cdp, `document.querySelector('.results-count')?.textContent?.includes('${findingCount} risultat')`, "filtered finding count not updated for screen readers");
  assert.equal(await cdp.evaluate("document.querySelectorAll('.explore-row').length"), findingCount,
    "filtered findings did not match visible result list");
  await assertRadioAx("Dichiarazioni", "true");
  await assertRadioAx("Tutto", "false");

  // The public type grammar includes Originali between Dichiarazioni and Persone.
  // Exercise each native-radio arrow step; skipping an option would mask a
  // keyboard-navigation regression instead of checking the rendered order.
  await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(cdp, "document.querySelector('input[type=radio][value=statement]').checked", "keyboard statement-kind transition failed");
  const statementCount = searchIndex.records.filter((record) => record.kind === "statement").length;
  assert.equal(await cdp.evaluate("document.querySelectorAll('.explore-row').length"), statementCount,
    "Statement radio filter does not match approved public Statement records");
  assert.match(await cdp.evaluate("location.search"), /tipo=statement/, "Statement filter did not serialize shareable URL");
  await assertRadioAx("Originali", "true");

  await key(cdp, "ArrowRight", { code: "ArrowRight", keyCode: 39 });
  await waitFor(cdp, "document.querySelector('input[type=radio][value=person]').checked", "keyboard next-kind transition failed");
  const personCount = searchIndex.records.filter((record) => record.kind === "person").length;
  assert.equal(await cdp.evaluate("document.querySelectorAll('.explore-row').length"), personCount,
    "People radio filter does not match approved public Person records");
  assert.equal(await cdp.evaluate("document.querySelector('.results-count[aria-live=polite]')?.textContent.trim()"),
    `${personCount} ${personCount === 1 ? "risultato" : "risultati"}`,
    "filtered Person result count not announced semantically");
  assert.match(await cdp.evaluate("location.search"), /tipo=person/, "Person filter did not serialize shareable URL");
  await assertRadioAx("Persone", "true");
  const personLinks = await cdp.evaluate("[...document.querySelectorAll('.explore-row .claim-row-claim')].map(link => link.getAttribute('href'))");
  assert(personLinks.every((route) => route.startsWith("/persone/") && routes.includes(route)),
    "Person results link outside built canonical destinations");
}
