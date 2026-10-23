/**
 * Portable scratch root for the public-web QA scripts.
 *
 * The SSR checks build an isolated Astro output into a scratch directory, and
 * Astro moves the prerendered assets there with `fs.rename`. A rename across
 * filesystems fails with `EXDEV: cross-device link not permitted`, so the
 * scratch directory must live on the same filesystem as `web/.astro/`:
 * `os.tmpdir()` is a tmpfs on Linux and breaks the checks there.
 *
 * Therefore the default scratch root is the `web/` package itself, and
 * `DP_SCRATCH_ROOT` overrides it explicitly when another location is wanted.
 */
import { mkdir, mkdtemp } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = fileURLToPath(new URL("../../", import.meta.url));

/** Absolute scratch root: `DP_SCRATCH_ROOT` when set, otherwise the `web/` package. */
export const scratchRoot = process.env.DP_SCRATCH_ROOT
  ? resolve(process.env.DP_SCRATCH_ROOT)
  : webRoot;

/** Create a unique scratch directory on the same filesystem as `web/`. */
export async function makeScratchDir(prefix) {
  await mkdir(scratchRoot, { recursive: true });
  return mkdtemp(join(scratchRoot, prefix));
}
