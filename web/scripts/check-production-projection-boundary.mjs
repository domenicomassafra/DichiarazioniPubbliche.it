import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const directory = await mkdtemp(join(tmpdir(), "dp-projection-boundary-"));
const sourceFixture = fileURLToPath(new URL("../src/data/demo-projection.json", import.meta.url));
const {
  DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: _configuredPath,
  DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: _demoFlag,
  DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY: _studioFlag,
  ...cleanEnv
} = process.env;

function build(projectionPath, outputName, demoMode = false) {
  return spawnSync("npm", ["run", "build", "--", "--outDir", join(directory, outputName)], {
    cwd: root,
    encoding: "utf8",
    env: {
      ...cleanEnv,
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: projectionPath,
      ...(demoMode ? { DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1" } : {}),
    },
  });
}

function output(result) {
  return `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
}

try {
  const copiedFixture = join(directory, "apparently-approved-index.json");
  await copyFile(sourceFixture, copiedFixture);
  const unsafe = build(copiedFixture, "unsafe");
  assert.notEqual(unsafe.status, 0, "a renamed demo projection became a public build");
  assert.match(output(unsafe), /Demo projection records cannot be used in a public build/);

  // A demo is still useful locally, but must never become crawlable just because
  // its filepath does not end with demo-projection.json.
  const demo = build(copiedFixture, "demo", true);
  assert.equal(demo.status, 0, `explicit local demo build failed: ${output(demo)}`);
  assert.match(await readFile(join(directory, "demo/index.html"), "utf8"), /<meta name="robots" content="noindex,nofollow"/);
  assert.equal(await readFile(join(directory, "demo/robots.txt"), "utf8"), "User-agent: *\nDisallow: /\n");
  assert.doesNotMatch(await readFile(join(directory, "demo/sitemap.xml"), "utf8"), /<loc>/);

  const fingerprint = createHash("sha256")
    .update('{"contents":[],"dossiers":[],"topics":[]}', "utf8")
    .digest("hex");
  const emptyProjection = join(directory, "empty-test-projection.json");
  await writeFile(emptyProjection, `${JSON.stringify({
    schema_version: "dichiarazioni-pubbliche-public-v2",
    generated_at: "2026-10-10T18:00:00+00:00",
    dataset_sha256: fingerprint,
    dossier_count: 0,
    dossiers: [],
    topics: [],
    contents: [],
    methodology: { aggregate_person_score: false },
  })}\n`);
  const approvedShape = build(emptyProjection, "empty");
  assert.equal(approvedShape.status, 0, `explicit empty-projection build failed: ${output(approvedShape)}`);
  const homepage = await readFile(join(directory, "empty/index.html"), "utf8");
  assert.match(homepage, /Nessuna dichiarazione ancora pubblicata\./);
  assert.match(homepage, /<meta name="robots" content="index,follow"/);
  const explore = await readFile(join(directory, "empty/esplora/index.html"), "utf8");
  assert.match(explore, /Non ci sono ancora record pubblicati\./);
  assert.doesNotMatch(explore, /astro-island/);
  const index = JSON.parse(await readFile(join(directory, "empty/search-index.v1.json"), "utf8"));
  assert.equal(index.projection_sha256, fingerprint);
  assert.deepEqual(index.records, []);
  const sitemap = await readFile(join(directory, "empty/sitemap.xml"), "utf8");
  const sitemapRoutes = [...sitemap.matchAll(/<loc>https:\/\/dichiarazionipubbliche\.it([^<]*)<\/loc>/g)]
    .map((match) => match[1]).sort();
  assert.deepEqual(sitemapRoutes, ["/", "/correzioni/", "/dati/", "/esplora/", "/metodo/", "/progetto/"]);
  assert.equal(await readFile(join(directory, "empty/robots.txt"), "utf8"),
    "User-agent: *\nAllow: /\nSitemap: https://dichiarazionipubbliche.it/sitemap.xml\n");
  const assets = await readdir(join(directory, "empty/_astro"));
  assert.equal(assets.some((name) => /studio|fixture|demo/i.test(name)), false,
    "private Studio or demo client bundle leaked into the public build");
  for (const route of sitemapRoutes) {
    const filename = route === "/" ? "empty/index.html" : `empty${route}index.html`;
    assert((await readFile(join(directory, filename), "utf8")).includes('<meta name="robots" content="index,follow"'));
  }

  const previewChecker = fileURLToPath(new URL("../../tools/check_informational_preview.py", import.meta.url));
  function audit(fingerprintArg) {
    return spawnSync("python3", [previewChecker, "--bundle-only", "--dist", join(directory, "empty"),
      "--projection", emptyProjection, "--expected-fingerprint", fingerprintArg], {
      cwd: root, encoding: "utf8", env: cleanEnv,
    });
  }
  const audited = audit(fingerprint);
  assert.equal(audited.status, 0, `independent informational-preview audit failed: ${output(audited)}`);
  const wrongFingerprint = audit("a".repeat(64));
  assert.notEqual(wrongFingerprint.status, 0, "independent preview audit accepted a wrong source fingerprint");
  assert.match(output(wrongFingerprint), /PROJECTION_FINGERPRINT_DRIFT/);

  // Browser evidence is an explicit opt-in for a host with Chrome installed.
  // It uses the same isolated bundles checked above, never an old web/dist.
  if (process.env.DP_RUN_BROWSER_QA === "1") {
    for (const [name, expectedRecords] of [["empty", 0], ["demo", 1]]) {
      const browser = spawnSync("node", ["scripts/check-browser-qa.mjs"], {
        cwd: root, encoding: "utf8", maxBuffer: 1024 * 1024,
        env: { ...cleanEnv, DP_BROWSER_DIST: join(directory, name) },
      });
      assert.equal(browser.status, 0, `${name}: isolated keyboard/AX/zoom browser matrix failed: ${output(browser)}`);
      const proof = JSON.parse(browser.stdout.trim());
      assert.equal(proof.status, "PASS", `${name}: browser matrix did not pass`);
      if (expectedRecords === 0) {
        assert.equal(proof.state, "empty-public-projection");
        assert.equal(proof.actual_zoom_200_pages, 6);
      } else {
        assert(proof.search_records > 0, "populated QA lacked searchable demo records");
        assert(new Set(proof.dp422_visual_matrix.map((entry) => entry.family)).size >= 9,
          "populated DP-422 QA omitted a canonical template family");
        assert.equal(proof.browser_zoom_200_exact.devicePixelRatio, 2);
      }
      assert.equal(proof.external_requests, 0, `${name}: browser made external requests`);
      console.log(`isolated ${name} keyboard/AX/zoom matrix PASS`);
    }
  }

  const legacy = join(directory, "legacy-v2-empty.json");
  const legacyProjection = {
    schema_version: "dichiarazioni-pubbliche-public-v2",
    generated_at: "2026-10-10T18:00:00+00:00",
    dataset_sha256: createHash("sha256").update('{"dossiers":[]}', "utf8").digest("hex"),
    dossier_count: 0,
    dossiers: [],
    methodology: { aggregate_person_score: false },
  };
  await writeFile(legacy, JSON.stringify(legacyProjection));
  assert.equal(build(legacy, "legacy").status, 0, "valid legacy v2 projections must remain supported");

  const wrongCount = join(directory, "bad-count.json");
  await writeFile(wrongCount, JSON.stringify({ ...legacyProjection, dossier_count: 1 }));
  const countRejected = build(wrongCount, "bad-count");
  assert.notEqual(countRejected.status, 0, "a mismatched dossier_count was accepted");
  assert.match(output(countRejected), /dossier_count does not match published dossiers/);

  const tampered = join(directory, "tampered-legacy.json");
  await writeFile(tampered, JSON.stringify({ ...legacyProjection, dataset_sha256: "a".repeat(64) }));
  const tamperRejected = build(tampered, "bad-hash");
  assert.notEqual(tamperRejected.status, 0, "tampered legacy v2 fingerprint was accepted");
  assert.match(output(tamperRejected), /Public projection fingerprint does not match/);

  console.log("production-projection-boundary PASS (renamed demo refused, opt-in demo noindex, empty six-route sitemap/index, Studio bundle excluded, independent preflight with wrong-hash rejection, legacy hash and count tamper rejected)");
} finally {
  await rm(directory, { recursive: true, force: true });
}
