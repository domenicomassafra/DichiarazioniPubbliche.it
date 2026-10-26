import type { APIRoute } from "astro";
import { loadPublicProjection } from "../lib/projection";
import { loadPublishedPeopleV3 } from "../lib/publishedPeopleV3";
import {
  buildSearchIndexMaterial,
  canonicalJson,
  finalizeSearchIndex,
} from "../lib/searchIndex";

export const prerender = true;

export const GET: APIRoute = async () => {
  const projection = await loadPublicProjection();
  const released = await loadPublishedPeopleV3();
  const index = await finalizeSearchIndex(buildSearchIndexMaterial(projection, released?.people));
  return new Response(`${canonicalJson(index)}\n`, {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=0, must-revalidate",
    },
  });
};
