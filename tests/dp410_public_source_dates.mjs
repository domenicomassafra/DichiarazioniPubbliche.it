import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Check actual public HTML, not source text. The demo projection is an isolated
// local fixture and must remain noindex; no public release or provider is used.
const web = fileURLToPath(new URL("../web/", import.meta.url));
const fixture = JSON.parse(await readFile(path.join(web, "src/data/demo-projection.json"), "utf8"));
const temporary = await mkdtemp(path.join(tmpdir(), "dp410-source-dates-"));
const dist = path.join(temporary, "dist");
const {
  DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: _publicProjection,
  DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: _demoProjection,
  ...baseEnvironment
} = process.env;

try {
  const build = spawnSync("npm", ["run", "build", "--", "--outDir", dist], {
    cwd: web,
    env: { ...baseEnvironment, DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1" },
    encoding: "utf8",
    timeout: 120_000,
  });
  assert.equal(build.status, 0, `isolated public fixture build failed:\n${build.stdout}\n${build.stderr}`);

  for (const dossier of fixture.dossiers) {
    const slug = dossier.finding_id.toLowerCase()
      .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const html = await readFile(path.join(dist, "dichiarazioni", slug, "index.html"), "utf8");
    assert.match(html, /<meta\s+name="robots"\s+content="noindex,nofollow"/, "fixture must stay non-indexable");
    const sourceLinks = [...html.matchAll(/<a\b[^>]*\bclass="source-row"[^>]*>[\s\S]*?<\/a>/g)]
      .map(([match]) => match);
    assert.equal(sourceLinks.length, dossier.evidence.length, `evidence link count changed for ${slug}`);

    for (const evidence of dossier.evidence) {
      const source = sourceLinks.find((link) => link.includes(`href="${evidence.url}"`));
      assert.ok(source, `source link missing for ${slug} / ${evidence.url}`);
      assert.ok(source.includes(evidence.publisher), `source publisher missing for ${slug}`);
      const expectedDate = new Intl.DateTimeFormat("it-IT", {
        day: "2-digit", month: "short", year: "numeric",
      }).format(new Date(evidence.publication_date));
      assert.match(source,
        new RegExp(`<time\\b(?=[^>]*\\bclass="source-date")(?=[^>]*\\bdatetime="${evidence.publication_date}")[^>]*>${expectedDate}<\\/time>`),
        `public source date must preserve its displayed value and machine-readable original for ${slug}`);
    }
  }

  console.log("DP410_SOURCE_DATES_PASS rendered public evidence links expose original machine-readable dates");
} finally {
  await rm(temporary, { recursive: true, force: true });
}
