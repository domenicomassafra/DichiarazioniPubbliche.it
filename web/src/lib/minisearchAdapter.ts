/** Local, ephemeral lexical retrieval over already approved public records.
 * Never persists an independent index or caches a possibly withdrawn release.
 * Publication, pin, hash and provenance validation belong to the callers.
 */
import MiniSearch from "minisearch";

type SearchDocument = { id: number; primary: string; secondary: string };
const engines = new WeakMap<object, { revision: string; engine: MiniSearch<SearchDocument> }>();

export function publicTextScores<T>(
  records: readonly T[],
  normalizedQuery: string,
  fields: (record: T) => { primary: readonly string[]; secondary: readonly string[] },
  normalize: (value: string) => string,
  cache: { asset: object; revision: string },
): Map<number, number> {
  if (!normalizedQuery || records.length === 0) return new Map();
  let existing = engines.get(cache.asset);
  if (!existing || existing.revision !== cache.revision) {
    const engine = new MiniSearch<SearchDocument>({
      fields: ["primary", "secondary"],
      idField: "id",
      // The caller has already applied the Italian accent/case normalization.
      tokenize: (value) => value.split(/\s+/u).filter(Boolean),
      processTerm: (term) => term,
    });
    engine.addAll(records.map((record, id) => {
      const terms = fields(record);
      return {
        id,
        primary: terms.primary.map(normalize).join(" "),
        secondary: terms.secondary.map(normalize).join(" "),
      };
    }));
    existing = { revision: cache.revision, engine };
    engines.set(cache.asset, existing);
  }
  const engine = existing.engine;
  const matches = engine.search(normalizedQuery, {
    combineWith: "AND",
    boost: { primary: 8, secondary: 1 },
    prefix: (term) => term.length >= 3,
    fuzzy: (term) => term.length >= 5 ? 0.2 : false,
  });
  return new Map(matches.map(({ id, score }) => [Number(id), score]));
}
