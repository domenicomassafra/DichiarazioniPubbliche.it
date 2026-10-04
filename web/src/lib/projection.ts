import fs from "node:fs/promises";
import path from "node:path";
import demoProjection from "../data/demo-projection.json";
import type { PublicProjection } from "./types";

const EXPECTED_SCHEMA = "dichiarazioni-pubbliche-public-v2";

function assertProjection(value: unknown): asserts value is PublicProjection {
  if (!value || typeof value !== "object") {
    throw new Error("Public projection must be a JSON object.");
  }

  const candidate = value as Partial<PublicProjection>;
  if (candidate.schema_version !== EXPECTED_SCHEMA) {
    throw new Error(
      `Unsupported public projection schema: ${String(candidate.schema_version)}`
    );
  }
  if (!Array.isArray(candidate.dossiers)) {
    throw new Error("Public projection dossiers must be an array.");
  }
  if (candidate.methodology?.aggregate_person_score !== false) {
    throw new Error("Public projection must explicitly disable aggregate person scores.");
  }
}

export async function loadPublicProjection(): Promise<PublicProjection> {
  const configuredPath = process.env.DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH;
  if (!configuredPath) {
    if (process.env.DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION === "1") {
      assertProjection(demoProjection);
      return demoProjection as PublicProjection;
    }
    throw new Error(
      "DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH is required. " +
      "Set DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION=1 only for explicit local demo builds."
    );
  }

  const resolved = path.resolve(configuredPath);
  const raw = await fs.readFile(resolved, "utf8");
  const parsed: unknown = JSON.parse(raw);
  assertProjection(parsed);
  return parsed;
}

export const projectionSchemaVersion = EXPECTED_SCHEMA;
