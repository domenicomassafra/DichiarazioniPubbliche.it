import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { validateOriginalStatement } from "../src/lib/statementV3.ts";

// Cross-language, synthetic-only proof. No actual source or runtime is used.
const root = fileURLToPath(new URL("../../", import.meta.url));
const script = [
  "import json,sys",
  "sys.path.insert(0,'poc');sys.path.insert(0,'tests')",
  "from test_dp435_public_statement_seam import IsolatedStatementSource,STAMP",
  "from dichiarazioni_pubbliche.public_projection import build_public_projection",
  "source=IsolatedStatementSource()",
  "bundle=build_public_projection(source,generated_at=STAMP,include_public_statements=True)",
  "assert len(bundle['statements'])==1",
  "print(json.dumps({'schema_version':bundle['schema_version'],'statement':bundle['statements'][0]},ensure_ascii=False))",
].join(";");
const result = spawnSync("python3", ["-c", script], {
  cwd: root,
  encoding: "utf8",
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
});
assert.equal(result.status, 0, "synthetic source projection failed: " + result.stderr);
const payload = JSON.parse(result.stdout);
assert.equal(payload.schema_version, "dichiarazioni-pubbliche-public-v3-statement-opt-in");
const statement = await validateOriginalStatement(payload.statement);
assert.equal(statement.finding_id, null);
assert.equal(statement.original_text, "costa 10 euro, non 20.");
assert.equal(statement.locator.end_char - statement.locator.start_char, [...statement.original_text].length);
const tampered = structuredClone(statement);
tampered.original_text = "costa 20 euro, non 10.";
await assert.rejects(() => validateOriginalStatement(tampered), /TAMPERED/);
console.log("backend to Astro v3 Statement parity PASS (synthetic opt-in only)");
