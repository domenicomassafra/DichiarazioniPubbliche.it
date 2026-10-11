#!/usr/bin/env node
// DP-405: exercise the actual Astro component in an isolated, non-deployable
// static build. This is deliberately NOT an approval or route-publication test.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFile, cp, mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
// Keep the ephemeral project under the real project so Astro resolves its
// package and virtual module loader from the same node_modules ancestor.
const scratch = await mkdtemp(join(root, ".dp405-person-empty-"));
const routeFile = join(scratch, "src/pages/approved-zero.astro");
const astroBin = join(root, "node_modules/astro/bin/astro.mjs");
const sample = {
  person_id: "person:synthetic-approved-zero",
  slug: "persona-sintetica",
  route: "/persone/persona-sintetica/",
  display_name: "Persona Sintetica",
  disambiguator: "Identità dimostrativa",
  status: "PUBLISHED",
  roles: [],
  statements: [],
};

async function build(person, { expectedFailure = false, omitApproval = false, routeSource } = {}) {
  const props = omitApproval ? "{}" : JSON.stringify({ approvedEmptyPerson: person });
  await writeFile(routeFile, routeSource ?? `---
import PersonRecord from "../components/PersonRecord.astro";
const props = ${props};
---
<PersonRecord {...props} />
`);
  const result = spawnSync(process.execPath, [astroBin, "build", "--root", scratch], {
    cwd: scratch,
    env: {
      ...process.env,
      DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH: "",
      DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION: "1",
    },
    encoding: "utf8",
    timeout: 60000,
    maxBuffer: 2 * 1024 * 1024,
  });
  const logs = `${result.stdout}\n${result.stderr}`;
  if (result.error) throw result.error;
  if (expectedFailure) {
    assert.notEqual(result.status, 0, "Unsafe/missing Person unexpectedly produced a public HTML artifact");
    assert.match(logs, /Invalid or nonempty approved Person input|No approved public Person input/);
    return null;
  }
  assert.equal(result.status, 0, `Approved synthetic empty Person failed to render:\n${logs.slice(-2000)}`);
  return readFile(join(scratch, "dist/approved-zero/index.html"), "utf8");
}

try {
  await cp(join(root, "src"), join(scratch, "src"), { recursive: true });
  await rm(join(scratch, "src/pages"), { recursive: true });
  await mkdir(join(scratch, "src/pages"));
  await copyFile(join(root, "astro.config.mjs"), join(scratch, "astro.config.mjs"));
  await copyFile(join(root, "tsconfig.json"), join(scratch, "tsconfig.json"));

  const html = await build(sample);
  assert.match(html, /<h1[^>]*>Persona Sintetica<\/h1>/);
  assert.match(html, /<h2[^>]*id="person-empty-title"[^>]*>Nessuna dichiarazione pubblicata per questa persona<\/h2>/);
  assert.match(html, /aria-labelledby="person-empty-title"/);
  assert.match(html, /href="\/esplora\/"/);
  assert.match(html, /href="\/metodo\/"/);
  assert.match(html, /<link rel="canonical" href="\/persone\/persona-sintetica\/"/);
  assert.doesNotMatch(html, /data-record-count|data-record-row|data-record-filters|data-record-filter-toggle/);
  assert.doesNotMatch(html, /0 dichiarazioni pubbliche|Nessuna dichiarazione pubblica corrisponde ai filtri/);
  assert.doesNotMatch(html, /omitted_count|private_count|reliability_score|person_score/);

  const populated = await build(null, { routeSource: `---
import PersonRecord from "../components/PersonRecord.astro";
import demo from "../data/demo-projection.json";
---
<PersonRecord dossiers={demo.dossiers.slice(0, 1)} />
` });
  assert.match(populated, /Dichiarazioni nel tempo/);
  assert.match(populated, /data-record-row/);
  assert.match(populated, /data-record-count/);
  assert.match(populated, /data-record-filters/);

  const withRole = await build({
    ...sample,
    roles: [{
      role_id: "role:synthetic",
      label: "Delegata",
      organization: "Ente dimostrativo",
      valid_from: "2024-01-01",
      valid_to: null,
      source_url: "https://example.test/registro",
    }],
  });
  assert.match(withRole, /Fonte dell'incarico/);
  assert.match(withRole, /href="https:\/\/example.test\/registro"/);
  assert.match(withRole, /fine non indicata/);
  assert.doesNotMatch(withRole, /in corso/);

  await build(sample, { expectedFailure: true, omitApproval: true });
  await build({ ...sample, status: "HELD" }, { expectedFailure: true });
  await build({
    ...sample,
    statements: [{ statement_id: "statement:not-allowed-in-empty" }],
  }, { expectedFailure: true });
  for (const source_url of [
    "javascript:alert(1)", "data:text/html,unsafe", "http://example.test/source",
    "https://user:pass@example.test/source", "not-a-url",
  ]) {
    await build({
      ...sample,
      roles: [{ role_id: "role:bad", label: "Titolo", organization: null,
        valid_from: "2024-01-01", valid_to: null, source_url }],
    }, { expectedFailure: true });
  }
  console.log("DP-405 Person component: PASS (approved zero, legacy populated, safe links, 8 fail-closed cases)");
} finally {
  await rm(scratch, { recursive: true, force: true });
}
