import { collectPublicTraces } from "./relations";
import { loadPublicProjection } from "./projection";

export async function getTraceStaticPaths() {
  const projection = await loadPublicProjection();
  return collectPublicTraces(projection).map((trace) => ({
    params: { id: trace.slug },
    props: { trace }
  }));
}
