// DP-407: real Astro Content routes, isolated fictional public projection.
// No real sources, providers, network calls or modifications to web/dist.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { makeScratchDir } from "./lib/scratch.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repository = path.dirname(webRoot);
const base = JSON.parse(await readFile(path.join(webRoot, "src/data/dp407-content-projection.json"), "utf8"));
const testDir = await makeScratchDir("dp407-currentness-");
const stagedWeb = path.join(testDir, "web");
const projectionPath = path.join(testDir, "projection.json");

const canonicalJson = (value) => value === null || typeof value !== "object"
  ? JSON.stringify(value)
  : Array.isArray(value) ? `[${value.map(canonicalJson).join(",")}]`
    : `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;

const withPublicContents = () => {
  const projection = structuredClone(base);
  const groups = new Map();
  for (const dossier of projection.dossiers) {
    const group = groups.get(dossier.source.content_id) ?? [];
    group.push(dossier);
    groups.set(dossier.source.content_id, group);
  }
  projection.contents = [...groups.entries()].map(([contentId, dossiers]) => ({
    content_id: contentId,
    slug: contentId.replaceAll(":", "-"),
    title: dossiers[0].source.title,
    url: dossiers[0].source.url,
    published_at: dossiers[0].source.published_at ?? null,
    content_kind: dossiers[0].source.text_provenance?.length ? "WRITTEN" : "VIDEO",
    duration_ms: dossiers[0].source.text_provenance?.length ? null : 390000,
    public_media_url: null,
    media_policy_version: null,
    publication_version: "public-content-v1",
    review_event_ids: ["review:fictional:content-v1"],
    finding_ids: dossiers.map((item) => item.finding_id),
  }));
  return projection;
};

const recomputeFingerprint = (bundle) => {
  const material = { dossiers: bundle.dossiers, contents: bundle.contents };
  if (bundle.topics !== undefined) material.topics = bundle.topics;
  bundle.dataset_sha256 = createHash("sha256").update(canonicalJson(material)).digest("hex");
};

const runBuild = async (bundle) => {
  recomputeFingerprint(bundle);
  await writeFile(projectionPath, JSON.stringify(bundle), "utf8");
  const schema = spawnSync("python3", ["-c",
    "import json,sys; from dichiarazioni_pubbliche.public_schema import validate_public_bundle; validate_public_bundle(json.load(open(sys.argv[1])))",
    projectionPath], { cwd: repository, encoding: "utf8", env: { ...process.env, PYTHONPATH: path.join(repository, "poc") } });
  assert.equal(schema.status, 0, `Fixture must pass the genuine Python public schema: ${schema.stderr}`);
  const build = spawnSync("npm", ["run", "build"], {
    cwd: stagedWeb,
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
    env: {
      ...process.env,
      DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1",
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: projectionPath,
    },
  });
  assert.equal(build.status, 0, `Astro failed on schema-valid Content data: ${build.stderr}\n${build.stdout.slice(-4000)}`);
  const html = (slug) => readFile(path.join(stagedWeb, "dist", "contenuti", slug, "index.html"), "utf8");
  return { timed: await html("content-demo-maintenance"), written: await html("content-demo-study") };
};

try {
  await cp(path.join(webRoot, "src"), path.join(stagedWeb, "src"), { recursive: true });
  for (const name of ["public", "astro.config.mjs", "tsconfig.json", "package.json"]) {
    try { await cp(path.join(webRoot, name), path.join(stagedWeb, name), { recursive: true }); }
    catch (error) { if (error.code !== "ENOENT") throw error; }
  }
  await symlink(path.join(webRoot, "node_modules"), path.join(stagedWeb, "node_modules"), "dir");

  const approved = withPublicContents();
  // A reviewed timed source can legitimately carry its own fragment and query.
  // The Content moment link must replace the fragment with the media-time
  // locator, not append a second '#' that no browser can interpret as #t.
  const withFragment = "https://example.test/demo/maintenance?edition=1#intro";
  for (const dossier of approved.dossiers.filter((item) => item.source.content_id === "content:demo:maintenance")) {
    dossier.source.url = withFragment;
  }
  approved.contents.find((item) => item.content_id === "content:demo:maintenance").url = withFragment;
  const initial = await runBuild(approved);
  const timed = approved.dossiers.find((item) => item.finding_id.endsWith("moment-06"));
  const written = approved.dossiers.find((item) => item.finding_id === "finding:demo:study");
  assert(timed && written && written.source.text_provenance?.length, "DP-407 timed/written fixtures unavailable");
  assert(initial.timed.includes(timed.claim), "approved timed Source/Content/Statement moment must appear");
  assert(initial.written.includes(written.claim), "approved written selector must appear");
  assert(initial.timed.includes("#t=150"), "approved timed locator must be tied to the source segment");
  assert(initial.timed.includes("https://example.test/demo/maintenance?edition=1#t=150"),
    "Content timed locator must preserve the reviewed query and replace any existing source fragment");
  assert(!initial.timed.includes("#intro#t="),
    "Content cannot append an uninterpretable second fragment to a reviewed source URL");
  assert(initial.written.includes("Passaggio 420–612"), "approved written locator must retain checked text offsets");

  const stale = withPublicContents();
  const taintedUrl = "https://example.test/internal/unapproved-source-revision?access=PRIVATE_URL_LEAK_SENTINEL";
  const staleTimed = stale.dossiers.find((item) => item.finding_id === timed.finding_id);
  const staleWritten = stale.dossiers.find((item) => item.finding_id === written.finding_id);
  staleTimed.source.url = taintedUrl;
  staleWritten.source.url = taintedUrl;
  const maintenance = stale.contents.find((item) => item.content_id === "content:demo:maintenance");
  const removedId = "finding:demo:maintenance-moment-07";
  const removed = stale.dossiers.find((item) => item.finding_id === removedId);
  maintenance.finding_ids = maintenance.finding_ids.filter((item) => item !== removedId);
  const withdrawn = stale.dossiers.find((item) => item.finding_id === "finding:demo:maintenance-moment-08");
  const withdrawnRationale = "WITHDRAWN_RATIONALE_MUST_NOT_RENDER_AS_CURRENT";
  withdrawn.finding.publication_status = "RETRACTED";
  withdrawn.finding.rationale = withdrawnRationale;
  const injectedMarkup = '<img data-dp407-probe src="data:,bad" onerror="document.documentElement.dataset.dp407Probe=\'executed\'">';
  maintenance.title += ` ${injectedMarkup}`;
  // Same stable content_id/finding_id, different Source release: the public
  // bundle schema accepts this, so the mounted Content UI must re-pin locally.
  const after = await runBuild(stale);
  assert(!after.timed.includes(staleTimed.claim), "stale timed Statement was projected onto a different Content source version");
  assert(!after.timed.includes(`data-content-select="${staleTimed.finding_id}"`), "stale timed marker must not be selectable");
  assert(after.timed.includes("#t=120"), "other current Source/Content moments must remain navigable");
  assert(!after.written.includes(staleWritten.claim), "stale written Statement was projected onto a different Content source version");
  assert(after.written.includes("Nessuna verifica pubblicata"), "written Content must retain a safe empty fallback");
  assert(!after.timed.includes(removed.claim), "revoked Content membership must not retain its earlier Statement moment");
  assert(after.timed.includes(withdrawn.claim) && after.timed.includes("Valutazione ritirata"), "publicly retracted moment remains visible with its actual state");
  assert(!after.timed.includes(withdrawnRationale), "withdrawn rationale must never appear as a current finding");
  for (const html of [after.timed, after.written]) {
    assert(!html.includes("PRIVATE_URL_LEAK_SENTINEL"), "stale source URL leaked into public HTML");
    assert(!html.includes("transcript_candidates") && !html.includes("provider_receipt"), "private processing body leaked");
  }
  assert(after.timed.includes(timed.source.title), "Content still renders its approved source context");
  assert(after.timed.includes("&lt;img"), "Astro SSR must HTML-escape even a synthetic public title with markup");
  const chrome = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const pageFile = path.join(stagedWeb, "dist/contenuti/content-demo-maintenance/index.html");
  const browser = spawnSync(chrome, ["--headless=new", "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-gpu", `--user-data-dir=${path.join(testDir, "chrome-profile")}`,
    "--dump-dom", pathToFileURL(pageFile).href], { encoding: "utf8", timeout: 30000, maxBuffer: 8 * 1024 * 1024 });
  assert.equal(browser.status, 0, `real Chrome DOM check unavailable: ${browser.error ?? browser.stderr.slice(-1500)}`);
  assert(browser.stdout.includes("&lt;img"), "the serialized browser DOM lost the escaped public title text");
  assert(!browser.stdout.includes("<img data-dp407-probe"), "the source title was parsed as a live HTML element");
  assert(!browser.stdout.includes('data-dp407-probe="executed"'), "an injected event handler executed in the browser");
  console.log("PASS DP-407: schema-valid Source/Content release mismatch omitted from real timed/written Astro HTML; membership withdrawal/retraction; escaped real Chrome DOM; current locators preserved, stale URL absent");
} finally {
  await rm(testDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 });
}
