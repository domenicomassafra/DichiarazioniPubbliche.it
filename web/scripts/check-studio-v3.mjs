import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import { studioFixtures } from "../src/data/studio.ts";
import {
  assertOriginalSourceResolution,
  assertSourceBoundStatus,
  assertStudioViewModel,
  isStudioUnavailable,
  resolveStudioViewModel,
} from "../src/lib/studioViewModel.ts";

const root = process.cwd();
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const expectedWorkspaces = ["corpus", "inbox", "collections", "verify"];
assert.deepEqual(Object.keys(studioFixtures), expectedWorkspaces, "Studio must expose exactly four operator jobs");

for (const workspace of expectedWorkspaces) {
  const fixture = studioFixtures[workspace];
  assert.equal(fixture.fixture_only, true, `${workspace}: demo data must be tagged fixture_only`);
  assert.equal(fixture.workspace, workspace, `${workspace}: workspace tag drift`);
  assert.ok(fixture.dominant_task.trim(), `${workspace}: dominant task missing`);
  assertStudioViewModel(fixture);

  const production = resolveStudioViewModel(fixture, { allow_fixture: false });
  assert.equal(isStudioUnavailable(production), true, `${workspace}: production path exposed fixture without opt-in`);
  assert.equal(JSON.stringify(production).includes("fixture:"), false, `${workspace}: fixture payload leaked into blocked production view-model`);
  for (const status of production.statuses) assertSourceBoundStatus(status);

  const optedIn = resolveStudioViewModel(fixture, { allow_fixture: true });
  assert.equal(optedIn, fixture, `${workspace}: explicit fixture opt-in did not resolve fixture`);
}

const sabotage = structuredClone(studioFixtures.inbox);
delete sabotage.statuses[0].source_ref;
assert.throws(
  () => assertStudioViewModel(sabotage),
  /SOURCE_REF_REQUIRED/,
  "status without source_ref must fail closed",
);

const blockerSabotage = structuredClone(studioFixtures.collections);
blockerSabotage.collections[1].status.blocker_code = null;
assert.throws(
  () => assertStudioViewModel(blockerSabotage),
  /BLOCKED_STATUS_REQUIRES_BLOCKER_CODE/,
  "blocked status without blocker_code must fail closed",
);

const originalSource = studioFixtures.verify.claims.find((claim) => claim.original_source_resolution)?.original_source_resolution;
assert.ok(originalSource, "Verify fixture must exercise a DP-225 original-source receipt");
assertOriginalSourceResolution(originalSource);
assert.equal(originalSource.path_content_ids.at(-1), originalSource.root_content_id, "original-source receipt root/path drift");

const originalSourceSabotage = structuredClone(studioFixtures.verify);
originalSourceSabotage.claims[0].original_source_resolution.root_content_id = "content:fixture:wrong-root";
assert.throws(
  () => assertStudioViewModel(originalSourceSabotage),
  /ORIGINAL_SOURCE_ROOT_PATH_MISMATCH/,
  "Studio must fail closed on a DP-225 root/path mismatch",
);

const header = read("src/components/SiteHeader.astro");
for (const workspace of expectedWorkspaces) {
  const route = `/studio/${workspace}/`;
  assert.ok(header.includes(route), `Studio navigation missing ${route}`);
}
for (const retired of ["/studio/sessioni/", "Nuova verifica", "Sessioni"]) {
  assert.equal(header.includes(retired), false, `ambiguous retired Studio navigation remains: ${retired}`);
}

const routeFile = path.join(root, "src", "pages", "studio", "[workspace]", "index.astro");
assert.ok(fs.existsSync(routeFile), "missing gated Studio workspace route");
const routeSource = fs.readFileSync(routeFile, "utf8");
assert.equal((routeSource.match(/<h1\b/g) ?? []).length, 0, "Studio route must not add a second dominant h1");
assert.ok(routeSource.includes("StudioWorkspaceFrame"), "Studio route must use shared workspace frame");
assert.ok(routeSource.includes("if (!allowFixture) return []"), "public builds must omit private Studio routes by default");

const verify = read("src/components/StudioWorkspaceClient.tsx");
const frame = read("src/components/StudioWorkspaceFrame.astro");
assert.equal((frame.match(/<h1\b/g) ?? []).length, 1, "shared Studio frame must own the single dominant h1");
assert.equal((verify.match(/className="workspace-pane"/g) ?? []).length, 3, "Verify must remain exactly three-pane");
assert.ok(verify.includes('data-verify-three-pane="true"'), "Verify three-pane contract marker missing");
assert.ok(verify.includes('data-action-domain="analysis"'), "Verify analysis action boundary missing");
assert.ok(verify.includes('data-action-domain="review"'), "Verify review action boundary missing");
assert.ok(verify.includes('data-original-source-resolution="true"'), "Verify original-source inspection marker missing");
assert.ok(verify.includes("data-root-content-id"), "Verify original-source root binding missing");

const statusRenderers = [
  read("src/components/StudioStatus.astro"),
  verify,
];
for (const renderer of statusRenderers) {
  for (const attribute of ["data-source-kind", "data-source-ref", "data-query-state", "data-blocker-code"]) {
    assert.ok(renderer.includes(attribute), `visible Studio status renderer missing ${attribute}`);
  }
}

const studioSources = [
  "src/data/studio.ts",
  "src/lib/studioViewModel.ts",
  "src/components/StudioWorkspaceClient.tsx",
  "src/components/StudioWorkspaceFrame.astro",
  "src/components/StudioStatus.astro",
  "src/components/SiteHeader.astro",
  "prototypes/verify-studio/sessioni.astro",
  "prototypes/verify-studio/workspace/[id].astro",
  "src/pages/studio/[workspace]/index.astro",
].map(read).join("\n");

for (const [label, pattern] of [
  ["fake AI wording", /\bAI\b|intelligenza artificiale|generat[oa] dall['’]IA|AI activity|AI insight/i],
  ["fake activity wording", /attivit[àa] recente|live activity|thinking\.\.\.|sta pensando/i],
  ["publication control", /\bpubblica(?:re|zione)?\b|\bpublish\b|auto-publish/i],
]) {
  assert.equal(pattern.test(studioSources), false, `Studio source contains forbidden ${label}`);
}

const fixtureVerify = studioFixtures.verify;
assert.ok(fixtureVerify.actions.every((action) => action.enabled === false), "fixture mutation actions must stay disabled");
assert.deepEqual(
  [...new Set(fixtureVerify.actions.map((action) => action.domain))].sort(),
  ["analysis", "review"],
  "Verify action domains must remain analysis/review only",
);

const distStudio = path.join(root, "dist", "studio");
if (!process.env.DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY) {
  assert.equal(fs.existsSync(distStudio), false, "public build must not emit private Studio routes");
} else {
  assert.ok(fs.existsSync(distStudio), "explicit Studio fixture build must emit Studio routes");
  for (const workspace of expectedWorkspaces) {
    const htmlPath = path.join(distStudio, workspace, "index.html");
    assert.ok(fs.existsSync(htmlPath), `built Studio route missing: ${workspace}`);
    const html = fs.readFileSync(htmlPath, "utf8");
    assert.ok(html.includes("fixture_only"), `${workspace}: explicit fixture build missing fixture_only tag`);
    const statusTags = [...html.matchAll(/<[^>]+data-studio-status[^>]*>/g)].map((match) => match[0]);
    assert.ok(statusTags.length > 0, `${workspace}: fixture build rendered no sourced status`);
    for (const tag of statusTags) {
      for (const attribute of ["data-source-kind", "data-source-ref", "data-query-state", "data-blocker-code"]) {
        assert.ok(tag.includes(`${attribute}=`), `${workspace}: rendered status missing ${attribute}`);
      }
    }
    assert.equal(/>\s*Pubblica(?:re)?\s*</i.test(html), false, `${workspace}: publication control rendered`);
  }
}

console.log("studio-v3 checks PASS: four unambiguous jobs, source-bound statuses, fixture gate, three-pane Verify, no publication action");
