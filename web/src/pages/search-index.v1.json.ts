import type { APIRoute } from "astro";
import { loadPublicProjection } from "../lib/projection";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
} from "../lib/searchIndex";

export const prerender = true;

export const GET: APIRoute = async () => {
  const projection = await loadPublicProjection();
  const index = await finalizeSearchIndex(buildSearchIndexMaterial(projection));
  return new Response(`${canonicalJson(index)}\n`, {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=0, must-revalidate",
    },
  });
};
