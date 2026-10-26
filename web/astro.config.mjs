import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import { readdir, readFile, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

async function removeUnreferencedPrivateChunks(dir) {
  const output = fileURLToPath(dir);
  const publicAssets = join(output, "_astro");
  const names = await readdir(publicAssets);
  const privateNames = names.filter((name) => /^Studio(?:WorkspaceClient|ReadOnlyWorkspace)\.[\w-]+\.js$/.test(name));
  if (!privateNames.length) return;

  async function inspect(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const full = join(directory, entry.name);
      if (entry.isDirectory()) {
        await inspect(full);
      } else if (!privateNames.includes(entry.name) && /\.(?:html|js|css)$/.test(entry.name)) {
        const text = await readFile(full, "utf8");
        for (const privateName of privateNames) {
          if (text.includes(privateName)) {
            throw new Error(`PUBLIC_BUILD_REFERENCES_PRIVATE_STUDIO_ASSET:${privateName}:${full}`);
          }
        }
      }
    }
  }
  await inspect(output);
  for (const name of privateNames) await unlink(join(publicAssets, name));
}

function excludePrivateStudioFromPublicBuild() {
  let building = false;
  return {
    name: "exclude-private-studio-from-public-build",
    hooks: {
      "astro:config:setup": ({ command }) => {
        building = command === "build";
      },
      "astro:routes:resolved": ({ routes }) => {
        if (!building || process.env.DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY === "1") return;
        // Static public builds never serve Studio. Astro still emits its unused
        // hydration chunks, which are separately removed after generation.
        for (let index = routes.length - 1; index >= 0; index--) {
          if (routes[index].entrypoint.includes("/studio/") ||
              (process.env.DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3 !== "1" &&
                routes[index].entrypoint.includes("public-people.v3.json"))) {
            routes.splice(index, 1);
          }
        }
      },
      "astro:build:done": async ({ dir }) => {
        if (building && process.env.DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY !== "1") {
          // Astro may emit hydration chunks for a dynamic route even when that
          // route has no prerendered pages. Keep them out of public artifacts.
          await removeUnreferencedPrivateChunks(dir);
        }
        // Keep the release mode detectable after an interrupted JSON removal.
        // Clean v2 builds omit this marker; an incomplete v3 cutover fails closed.
        if (building && process.env.DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY !== "1" &&
            process.env.DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3 === "1") {
          await writeFile(join(fileURLToPath(dir), "person-v3.mode"),
            "dichiarazioni-pubbliche-person-v3\n");
        }
        // Route removal can leave an emitted static endpoint on some Astro
        // versions. An opted-out build must never ship the v3 JSON artifact.
        if (building && process.env.DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3 !== "1") {
          try { await unlink(join(fileURLToPath(dir), "public-people.v3.json")); }
          catch (error) { if (error.code !== "ENOENT") throw error; }
        }
      },
    },
  };
}

export default defineConfig({
  output: "static",
  integrations: [react(), excludePrivateStudioFromPublicBuild()],
  build: {
    format: "directory"
  }
});
