import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Build the approved, deliberately empty public projection in isolation. This
// checks the real rendered route, not an authored HTML fragment or a demo index.
const web = fileURLToPath(new URL("../web/", import.meta.url));
const temp = await mkdtemp(path.join(tmpdir(), "dp429-explore-a11y-"));
const projectionPath = path.join(temp, "approved-empty.json");
const dist = path.join(temp, "dist");
const fingerprint = createHash("sha256")
  .update('{"contents":[],"dossiers":[],"topics":[]}', "utf8")
  .digest("hex");

function run(command, args, env) {
  const result = spawnSync(command, args, {
    cwd: web,
    encoding: "utf8",
    env,
    timeout: 120_000,
  });
  assert.equal(result.status, 0,
    `${command} ${args.join(" ")} failed:\n${result.stdout ?? ""}\n${result.stderr ?? ""}`);
  return result.stdout ?? "";
}

try {
  await writeFile(projectionPath, JSON.stringify({
    schema_version: "dichiarazioni-pubbliche-public-v2",
    generated_at: "2026-10-11T00:00:00+00:00",
    dataset_sha256: fingerprint,
    dossier_count: 0,
    dossiers: [],
    topics: [],
    contents: [],
    methodology: { aggregate_person_score: false },
  }));
  const {
    DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: _demo,
    DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: _projection,
    ...safeEnv
  } = process.env;
  const env = { ...safeEnv, DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: projectionPath };

  run("npm", ["run", "build", "--", "--outDir", dist], env);
  const html = await readFile(path.join(dist, "esplora", "index.html"), "utf8");
  const state = html.match(/<section\b[^>]*\bclass="[^"]*\blaunch-empty-state\b[^"]*"[^>]*>[\s\S]*?<\/section>/)?.[0];
  assert.ok(state, "The approved-empty Explore route must render its own public state");
  assert.match(state, /aria-labelledby="archivio-vuoto"/);
  assert.match(state, /<h2\b[^>]*id="archivio-vuoto"[^>]*>Non ci sono ancora record pubblicati\.<\/h2>/);
  assert.match(state, /<p\b[^>]*class="results-count"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"[^>]*>0 risultati pubblicati<\/p>/,
    "The empty archive must expose a visible, atomic live result count");
  assert.match(html, /archivio pubblico è in preparazione: le ricerche saranno disponibili/,
    "The empty page must not promise an unavailable search interaction");
  assert.match(state, /<nav\b[^>]*aria-label="Informazioni sul progetto"/);
  assert.match(state, /href="\/metodo\/"[\s\S]*href="\/progetto\/"[\s\S]*href="\/correzioni\/"/,
    "Keyboard links must retain their existing reading order");
  assert.doesNotMatch(html, /<astro-island\b|<input\b[^>]*id="client-search"|class="[^"]*claim-row/,
    "The approved-empty route must not hydrate private or phantom search results");

  const index = JSON.parse(await readFile(path.join(dist, "search-index.v1.json"), "utf8"));
  assert.equal(index.projection_sha256, fingerprint);
  assert.deepEqual(index.records, [], "Test must not turn on demo/publication results");

  if (process.env.DP429_BROWSER === "1") {
    const browserOutput = run("node", ["scripts/check-browser-qa.mjs"], {
      ...env, DP_BROWSER_DIST: dist,
    });
    assert.match(browserOutput, /"keyboard_navigation": "PASS"/);
    assert.match(browserOutput, /"reduced_motion": "PASS"/);
    assert.match(browserOutput, /"actual_zoom_200_pages": [1-9]/);
  }
  console.log("DP-429 Explore approved-empty DOM, accessible count and projection boundary PASS");
} finally {
  await rm(temp, { recursive: true, force: true });
}
