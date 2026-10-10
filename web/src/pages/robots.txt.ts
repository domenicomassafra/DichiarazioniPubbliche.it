import type { APIRoute } from "astro";

export const prerender = true;

const PUBLIC_BASE_URL = "https://dichiarazionipubbliche.it";

export const GET: APIRoute = async () => {
  const projectionPath = process.env.DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH;
  const demoBuild = process.env.DICHIARAZIONI_PUBBLICHE_ALLOW_DEMO_PROJECTION === "1" ||
    !projectionPath || projectionPath.endsWith("demo-projection.json");
  const body = demoBuild
    ? "User-agent: *\nDisallow: /\n"
    : `User-agent: *\nAllow: /\nSitemap: ${PUBLIC_BASE_URL}/sitemap.xml\n`;

  return new Response(body, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=0, must-revalidate",
    },
  });
};
