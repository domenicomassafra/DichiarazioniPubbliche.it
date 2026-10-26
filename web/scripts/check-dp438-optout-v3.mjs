/** Explicit release opt-out must keep legacy builds available during rollback. */
import assert from "node:assert/strict";
import { loadPublishedPeopleV3 } from "../src/lib/publishedPeopleV3.ts";

const config = {
  DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3: "0",
  DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_ASSETS_PATH: "/nonexistent/dp438-disabled-assets.json",
  DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH: "/nonexistent/dp438-disabled-pins.json",
};
const original = Object.fromEntries(Object.keys(config).map(key => [key, process.env[key]]));
try {
  Object.assign(process.env, config);
  assert.equal(await loadPublishedPeopleV3(), null);
} finally {
  for (const [key, value] of Object.entries(original)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}
console.log("DP438 explicit opt-out with retained pins and asset paths PASS");
