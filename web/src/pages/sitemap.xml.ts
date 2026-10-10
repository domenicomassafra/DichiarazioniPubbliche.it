import type { APIRoute } from "astro";
import { contentSlug, dossierSlug, speakerSlug } from "../lib/format";
import { loadPublicProjection } from "../lib/projection";
import { collectPublicTraces } from "../lib/relations";

export const prerender = true;

const PUBLIC_BASE_URL = "https://dichiarazionipubbliche.it";
const STATIC_ROUTES = ["/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"];

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

export const GET: APIRoute = async () => {
  const projectionPath = process.env.DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH;
  const demoBuild = process.env.DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION === "1" ||
    !projectionPath || projectionPath.endsWith("demo-projection.json");
  const projection = await loadPublicProjection();
  const routes = new Set<string>();

  if (!demoBuild) {
    for (const route of STATIC_ROUTES) routes.add(route);
    for (const dossier of projection.dossiers) {
      routes.add(`/dichiarazioni/${dossierSlug(dossier)}/`);
      routes.add(`/persone/${speakerSlug(dossier)}/`);
    }
    for (const topic of projection.topics ?? []) routes.add(`/temi/${topic.slug}/`);
    if (projection.contents !== undefined) {
      for (const content of projection.contents) routes.add(`/contenuti/${content.slug}/`);
    } else {
      for (const dossier of projection.dossiers) routes.add(`/contenuti/${contentSlug(dossier)}/`);
    }
    for (const trace of collectPublicTraces(projection)) routes.add(`/tracce/${trace.slug}/`);
  }

  const urls = [...routes]
    .sort()
    .map((route) => `  <url><loc>${escapeXml(`${PUBLIC_BASE_URL}${route}`)}</loc></url>`)
    .join("\n");
  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    urls,
    "</urlset>",
    "",
  ].join("\n");

  return new Response(body, {
    headers: {
      "content-type": "application/xml; charset=utf-8",
      "cache-control": "public, max-age=0, must-revalidate",
    },
  });
};
