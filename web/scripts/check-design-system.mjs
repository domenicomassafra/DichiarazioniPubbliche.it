import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const src = path.join(root, "src");
const tokensPath = path.join(src, "styles", "tokens.css");
const layoutPath = path.join(src, "layouts", "BaseLayout.astro");
const failures = [];

const read = (file) => fs.readFileSync(file, "utf8");
const tokens = read(tokensPath);
const layout = read(layoutPath);

const paper = tokens.match(/--paper-0:\s*(#[0-9a-fA-F]{6})\s*;/)?.[1]?.toLowerCase();
const theme = layout.match(/<meta\s+name="theme-color"\s+content="(#[0-9a-fA-F]{6})"\s*\/>/)?.[1]?.toLowerCase();
if (!paper || !theme || paper !== theme) {
  failures.push(`theme-color drift: paper-0=${paper ?? "missing"} meta=${theme ?? "missing"}`);
}

const sourceFiles = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
    } else if (/\.(?:css|astro|tsx|ts)$/.test(entry.name)) {
      sourceFiles.push(full);
    }
  }
}
walk(src);

for (const file of sourceFiles) {
  const body = read(file);
  if (/(?:linear|radial|conic)-gradient\s*\(/i.test(body)) {
    failures.push(`gradient forbidden: ${path.relative(root, file)}`);
  }
  if (/backdrop-filter\s*:/i.test(body)) {
    failures.push(`backdrop-filter forbidden: ${path.relative(root, file)}`);
  }

  const hexes = [...body.matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((match) => match[0].toLowerCase());
  if (file === tokensPath) continue;
  if (file === layoutPath) {
    const unexpected = hexes.filter((value) => value !== paper);
    if (unexpected.length || hexes.length !== 1) {
      failures.push(`unexpected color literal in BaseLayout: ${hexes.join(", ") || "none"}`);
    }
  } else if (hexes.length) {
    failures.push(`color literal outside tokens.css: ${path.relative(root, file)} => ${hexes.join(", ")}`);
  }
}

for (const match of tokens.matchAll(/--radius[^:]*:\s*([^;]+);/g)) {
  for (const px of match[1].matchAll(/(\d+(?:\.\d+)?)px/g)) {
    if (Number(px[1]) >= 10) failures.push(`double-digit radius forbidden: ${match[0]}`);
  }
}

const licenses = [
  "licenses/IBM-Plex-Sans-OFL-1.1.txt",
  "licenses/IBM-Plex-Mono-OFL-1.1.txt",
  "licenses/Newsreader-OFL-1.1.txt"
];
for (const relative of licenses) {
  const file = path.join(root, relative);
  if (!fs.existsSync(file)) {
    failures.push(`font license missing: ${relative}`);
    continue;
  }
  if (!/SIL Open Font License, Version 1\.1/i.test(read(file))) {
    failures.push(`unexpected font license text: ${relative}`);
  }
}

if (failures.length) {
  for (const failure of failures) console.error(`DESIGN CHECK FAIL: ${failure}`);
  process.exit(1);
}

console.log(`DESIGN CHECK PASS: theme ${paper}, no forbidden visual effects/literals, font licenses present`);
