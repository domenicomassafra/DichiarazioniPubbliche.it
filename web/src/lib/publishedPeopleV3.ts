/** DP-438 public build adapter for a separately issued, current Person release.
 * Assets alone never authorize publication. The release authority must supply
 * the independent pins and an explicit publication decision.
 */
import { readFile, stat } from "node:fs/promises";
import { readPinnedPrivatePublicPersonV3, type PrivatePublicPersonPins } from "./privatePublicPersonEmptyV3.ts";
import { readApprovedPersonV3, type ApprovedPersonV3, type ApprovedPersonV3Collection } from "./publicPersonV3.ts";

export interface PublishedPeopleV3Pins extends PrivatePublicPersonPins {
  publicationAuthorized: boolean;
}

export interface PublishedPeopleV3Release {
  collection: ApprovedPersonV3Collection;
  people: ApprovedPersonV3[];
  pins: PublishedPeopleV3Pins;
}

export async function validatePublishedPeopleV3(
  assets: { people: unknown; join: unknown; index: unknown; source: unknown; sitemapPersonRoutes: unknown },
  pins: PublishedPeopleV3Pins,
): Promise<PublishedPeopleV3Release> {
  if (pins?.publicationAuthorized !== true) {
    throw new Error("DP438_PUBLICATION_NOT_AUTHORIZED");
  }
  // The existing pinned private reader verifies source rights, immutable
  // quotation, Person membership, index, sitemap and current release expiry.
  await readPinnedPrivatePublicPersonV3(assets, pins, "dp438:unmatched");
  const collection = structuredClone(assets.people) as ApprovedPersonV3Collection;
  await readApprovedPersonV3(collection, {
    allowPersonV3: true,
    expectedCollectionSha256: pins.personSha256,
    identifier: "dp438:unmatched",
  });
  return { collection, people: collection.people, pins: structuredClone(pins) };
}

const ENABLE = "DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3";
const ASSETS = "DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_ASSETS_PATH";
const PINS = "DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH";

async function stableJson(path: string): Promise<unknown> {
  const before = await stat(path);
  if (!before.isFile() || before.size > 16 * 1024 * 1024) throw new Error("DP438_RELEASE_FILE_INVALID");
  const value: unknown = JSON.parse(await readFile(path, "utf8"));
  const after = await stat(path);
  if (before.mtimeMs !== after.mtimeMs || before.size !== after.size || before.ino !== after.ino) {
    throw new Error("DP438_RELEASE_CHANGED_DURING_BUILD");
  }
  return value;
}

export async function loadPublishedPeopleV3(): Promise<PublishedPeopleV3Release | null> {
  const enabled = process.env[ENABLE];
  const assetsPath = process.env[ASSETS];
  const pinsPath = process.env[PINS];
  if (!enabled && !assetsPath && !pinsPath) return null;
  if (enabled !== "1" || !assetsPath || !pinsPath || assetsPath === pinsPath) {
    throw new Error("DP438_PUBLIC_RELEASE_CONFIG_INCOMPLETE");
  }
  // Pins belong to the independent current publication authority, not to the
  // candidate assets. Reject partial configuration and changed input files.
  const [assets, pins] = await Promise.all([stableJson(assetsPath), stableJson(pinsPath)]);
  return validatePublishedPeopleV3(
    assets as Parameters<typeof validatePublishedPeopleV3>[0],
    pins as PublishedPeopleV3Pins,
  );
}
