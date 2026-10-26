import type { APIRoute } from "astro";
import { canonicalJson } from "../lib/searchIndex.ts";
import { loadPublishedPeopleV3 } from "../lib/publishedPeopleV3.ts";

export const prerender = true;

export const GET: APIRoute = async () => {
  const release = await loadPublishedPeopleV3();
  if (!release) return new Response("Not found", { status: 404 });
  const {schema_version, dataset_sha256, people} = release.collection;
  return new Response(canonicalJson({schema_version,dataset_sha256,people}) + "\n", {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
};
