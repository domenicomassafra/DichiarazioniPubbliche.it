import { useEffect, useMemo, useRef, useState } from "react";
import { assessmentLabel, assessmentTone, formatDate } from "../lib/format";
import SegmentedControl from "./design/SegmentedControl";
import {
  SEARCH_QUERY_MAX_CHARS,
  buildExploreSearch,
  normalizeSearchText,
  parseExploreSearch,
  searchPublicIndex,
  validateSearchIndex,
  type ExploreUrlState,
  type PublicSearchIndex,
  type SearchFilters,
  type SearchRecordKind,
} from "../lib/searchIndex";
import type { PublicDossier } from "../lib/types";

interface Props {
  expectedProjectionSha256: string;
}

type AssessmentFilter = PublicDossier["finding"]["assessment"] | "ALL";
type SortOrder = "relevance" | "recent" | "old";

const kindLabels: Record<SearchRecordKind, string> = {
  finding: "Dichiarazione",
  content: "Contenuto",
  person: "Persona",
  topic: "Tema",
};

/** URL state keeps user-entered bytes; only the actual search normalizes input. */
export function buildExploreUrlKeepingQuery(state: ExploreUrlState): string {
  const params = new URLSearchParams(buildExploreSearch(state));
  if (state.query.length > 0) params.set("q", state.query);
  return params.toString();
}

function nearbyPublicWord(typed: string, candidate: string, limit: number): boolean {
  if (Math.abs(typed.length - candidate.length) > limit ||
      typed[0] !== candidate[0] || typed === candidate) return false;
  let previous = Array.from({ length: candidate.length + 1 }, (_, index) => index);
  for (let row = 1; row <= typed.length; row += 1) {
    const current = [row];
    let lowest = row;
    for (let column = 1; column <= candidate.length; column += 1) {
      const distance = Math.min(
        previous[column] + 1,
        current[column - 1] + 1,
        previous[column - 1] + (typed[row - 1] === candidate[column - 1] ? 0 : 1),
      );
      current.push(distance);
      lowest = Math.min(lowest, distance);
    }
    if (lowest > limit) return false;
    previous = current;
  }
  return previous[candidate.length] <= limit;
}

/**
 * Suggestions are optional queries from the verified public search vocabulary.
 * They do not change the query, score people, or extend DP-409's matching rules.
 */
export function getExploreSuggestions(
  index: PublicSearchIndex,
  rawQuery: string,
  filters: SearchFilters,
): string[] {
  if (!rawQuery.trim() || [...rawQuery].length > SEARCH_QUERY_MAX_CHARS ||
      searchPublicIndex(index, rawQuery, filters).records.length > 0) return [];

  const words = new Set<string>();
  // Reserve a bounded share for each public type so a large Content catalog
  // cannot crowd out Declaration, Person or Topic suggestions.
  const collected: Record<SearchRecordKind, number> = {
    finding: 0, content: 0, person: 0, topic: 0,
  };
  const kind = filters.kind ?? "ALL";
  const assessment = filters.assessment ?? "ALL";
  const personId = filters.personId ?? "ALL";
  const topicId = filters.topicId ?? "ALL";
  for (const record of index.records) {
    // Apply the exact public membership filters used by searchPublicIndex
    // BEFORE collecting fuzzy vocabulary or spending its candidate budget.
    // Unrelated public records cannot crowd out an eligible suggestion.
    if ((kind !== "ALL" && record.kind !== kind) ||
        (assessment !== "ALL" && record.assessment !== assessment) ||
        (personId !== "ALL" &&
          (record.kind !== "finding" || record.person_id !== personId)) ||
        (topicId !== "ALL" &&
          (record.kind !== "finding" || !record.topic_ids?.includes(topicId)))) {
      continue;
    }
    if (collected[record.kind] >= 125) continue;
    collected[record.kind] += 1;
    for (const term of [...record.primary_terms.slice(0, 5), ...record.secondary_terms.slice(0, 5)]) {
      if (typeof term !== "string") continue;
      for (const word of normalizeSearchText(term.slice(0, 160)).split(" ")) {
        if (word.length >= 4 && word.length <= 24) words.add(word);
        if (words.size >= 1600) break;
      }
      if (words.size >= 1600) break;
    }
    if (words.size >= 1600) break;
  }

  // Preserve the original punctuation, case and whitespace in unedited tokens.
  const typedWords = [...rawQuery.matchAll(/[\p{L}\p{N}]+/gu)]
    .filter((match) => {
      const normalized = normalizeSearchText(match[0]);
      return normalized.length >= 4 && normalized.length <= 24 &&
        !normalized.includes(" ");
    }).slice(0, 3);
  const candidates = new Set<string>();
  const vocabulary = [...words].sort((left, right) => left.localeCompare(right, "it"));
  let candidateChecks = 24;
  for (const typed of typedWords) {
    const normalized = normalizeSearchText(typed[0]);
    const limit = normalized.length >= 6 ? 2 : 1;
    for (const word of vocabulary) {
      if (!nearbyPublicWord(normalized, word, limit)) continue;
      candidateChecks -= 1;
      const proposal = rawQuery.slice(0, typed.index) + word +
        rawQuery.slice(typed.index! + typed[0].length);
      if ([...proposal].length <= SEARCH_QUERY_MAX_CHARS &&
          searchPublicIndex(index, proposal, filters).records.length > 0) {
        candidates.add(proposal);
      }
      if (candidates.size >= 4 || candidateChecks <= 0) break;
    }
    if (candidates.size >= 4 || candidateChecks <= 0) break;
  }
  return [...candidates].sort((left, right) => left.localeCompare(right, "it")).slice(0, 4);
}

export default function ExploreClient({ expectedProjectionSha256 }: Props) {
  const [query, setQuery] = useState("");
  const [assessment, setAssessment] = useState<AssessmentFilter>("ALL");
  const [kind, setKind] = useState<SearchRecordKind | "ALL">("ALL");
  const [sort, setSort] = useState<SortOrder>("relevance");
  const [personId, setPersonId] = useState<string>("ALL");
  const [topicId, setTopicId] = useState<string>("ALL");
  const [urlReady, setUrlReady] = useState(false);
  const [index, setIndex] = useState<PublicSearchIndex | null>(null);
  const [indexState, setIndexState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);
  const filterDialog = useRef<HTMLDialogElement>(null);
  const filterButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function restoreFromUrl() {
      const restored = parseExploreSearch(window.location.search);
      setQuery(restored.query);
      setAssessment(restored.assessment);
      setKind(restored.kind);
      setSort(restored.sort);
      setPersonId(restored.personId ?? "ALL");
      setTopicId(restored.topicId ?? "ALL");
    }
    restoreFromUrl();
    window.addEventListener("popstate", restoreFromUrl);
    setUrlReady(true);
    return () => window.removeEventListener("popstate", restoreFromUrl);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/search-index.v1.json", {
          headers: { accept: "application/json" },
        });
        if (!response.ok) throw new Error("SEARCH_INDEX_UNAVAILABLE");
        const verified = await validateSearchIndex(
          await response.json(),
          expectedProjectionSha256,
        );
        if (!cancelled) {
          setIndex(verified);
          setIndexState("ready");
        }
      } catch {
        if (!cancelled) setIndexState("unavailable");
      }
    })();
    return () => { cancelled = true; };
  }, [expectedProjectionSha256]);

  useEffect(() => {
    if (!urlReady) return;
    const search = buildExploreUrlKeepingQuery({ query, assessment, kind, sort, personId, topicId });
    const next = `${window.location.pathname}${search ? `?${search}` : ""}`;
    window.history.replaceState(null, "", next);
  }, [assessment, kind, query, sort, personId, topicId, urlReady]);

  const response = useMemo(() => {
    if (!index) return null;
    return searchPublicIndex(index, query, { assessment, kind, sort, personId, topicId });
  }, [assessment, index, kind, query, sort, personId, topicId]);

  const suggestions = useMemo(
    () => index && response?.status === "OK" && response.records.length === 0
      ? getExploreSuggestions(index, query, { assessment, kind, personId, topicId })
      : [],
    [assessment, index, kind, personId, query, response, topicId],
  );

  // Facet choices are exclusively from this verified public projection.
  const people = useMemo(
    () => index?.records.filter((record) => record.kind === "person") ?? [],
    [index],
  );
  const topics = useMemo(
    () => index?.records.filter((record) => record.kind === "topic") ?? [],
    [index],
  );

  const kindCounts = useMemo(() => {
    const counts: Record<SearchRecordKind | "ALL", number> = {
      ALL: 0,
      finding: 0,
      person: 0,
      topic: 0,
      content: 0,
    };
    if (!index) return counts;
    const rows = searchPublicIndex(index, query, { assessment, kind: "ALL", sort, personId, topicId }).records;
    counts.ALL = rows.length;
    for (const record of rows) counts[record.kind] += 1;
    return counts;
  }, [assessment, index, query, sort, personId, topicId]);

  const activeFilterCount = Number(assessment !== "ALL") + Number(kind !== "ALL") +
    Number(sort !== "relevance") + Number(personId !== "ALL") + Number(topicId !== "ALL");
  const records = response?.records ?? [];

  function closeFilters() {
    filterDialog.current?.close();
    filterButton.current?.focus();
  }

  function openFilters() {
    filterDialog.current?.showModal();
    setFiltersOpen(true);
  }

  function pushFilterState(overrides: {
    assessment?: AssessmentFilter;
    kind?: SearchRecordKind | "ALL";
    sort?: SortOrder;
    personId?: string;
    topicId?: string;
  }) {
    const nextAssessment = overrides.assessment ?? assessment;
    const nextKind = overrides.kind ?? kind;
    const nextSort = overrides.sort ?? sort;
    const nextPersonId = overrides.personId ?? personId;
    const nextTopicId = overrides.topicId ?? topicId;
    const search = buildExploreUrlKeepingQuery({
      query,
      assessment: nextAssessment,
      kind: nextKind,
      sort: nextSort,
      personId: nextPersonId,
      topicId: nextTopicId,
    });
    window.history.pushState(null, "", `${window.location.pathname}${search ? `?${search}` : ""}`);
  }

  function changeKind(next: SearchRecordKind | "ALL") {
    pushFilterState({ kind: next });
    setKind(next);
  }

  function changeAssessment(next: AssessmentFilter) {
    pushFilterState({ assessment: next });
    setAssessment(next);
  }

  function changeSort(next: SortOrder) {
    pushFilterState({ sort: next });
    setSort(next);
  }

  function resetFilters() {
    pushFilterState({ assessment: "ALL", kind: "ALL", sort: "relevance", personId: "ALL", topicId: "ALL" });
    setAssessment("ALL");
    setKind("ALL");
    setSort("relevance");
    setPersonId("ALL");
    setTopicId("ALL");
  }

  if (indexState === "unavailable") {
    return (
      <section className="explore-client dp-state" data-state="unavailable" aria-live="polite">
        <h2 className="dp-state__title">Indice di ricerca non disponibile.</h2>
        <p className="dp-state__body">Lo snapshot pubblico e il suo indice non coincidono oppure l'asset non è raggiungibile. Il sito non usa dati demo o un indice precedente come ripiego.</p>
      </section>
    );
  }

  return (
    <section className="explore-client" aria-label="Risultati di ricerca">
      <label className="dp-visually-hidden" htmlFor="client-search">Cerca nel record pubblico</label>
      <div className="search-field" style={{ margin: "0 0 22px" }}>
        <span className="search-icon" aria-hidden="true">⌕</span>
        <input
          ref={searchInput}
          id="client-search"
          type="search"
          value={query}
          maxLength={SEARCH_QUERY_MAX_CHARS}
          aria-describedby="search-limit"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Cerca dichiarazioni, persone, temi, contenuti…"
        />
        {query && <button type="button" aria-label="Pulisci ricerca" onClick={() => {
          setQuery("");
          searchInput.current?.focus();
        }}>×</button>}
      </div>
      <p id="search-limit" className="dp-visually-hidden">Massimo {SEARCH_QUERY_MAX_CHARS} caratteri. La ricerca resta nel browser.</p>

      {suggestions.length > 0 && (
        <div className="dp-state" data-state="suggestions" role="region" aria-label="Suggerimenti di ricerca" aria-live="polite">
          <p className="dp-state__body" style={{ overflowWrap: "anywhere" }}>
            Nessun risultato per «{query}». Puoi scegliere una ricerca simile presente
            nel catalogo pubblico. La tua ricerca rimane invariata finché non scegli.
          </p>
          <ul style={{ display: "flex", flexWrap: "wrap", gap: "8px", listStyle: "none", padding: 0 }}>
            {suggestions.map((suggestion) => (
              <li key={suggestion}>
                <button
                  className="quiet-button"
                  type="button"
                  data-search-suggestion={true}
                  style={{ overflowWrap: "anywhere", whiteSpace: "normal" }}
                  onClick={() => {
                    setQuery(suggestion);
                    searchInput.current?.focus();
                  }}
                >
                  Cerca «{suggestion.trim()}»
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {response?.status === "QUERY_TOO_LONG" && (
        <div className="dp-state" data-state="error" role="alert">
          <h2 className="dp-state__title">Ricerca troppo lunga.</h2>
          <p className="dp-state__body">Usa al massimo {SEARCH_QUERY_MAX_CHARS} caratteri. Nessuna ricerca è stata eseguita.</p>
        </div>
      )}

      <SegmentedControl
        label="Tipo di record"
        name="tipo-record"
        value={kind}
        onChange={(value) => changeKind(value as SearchRecordKind | "ALL")}
        options={[
          { value: "ALL", label: "Tutto", count: kindCounts.ALL },
          { value: "finding", label: "Dichiarazioni", count: kindCounts.finding },
          { value: "person", label: "Persone", count: kindCounts.person },
          { value: "topic", label: "Temi", count: kindCounts.topic },
          { value: "content", label: "Contenuti", count: kindCounts.content },
        ]}
      />

      <div className="filter-row">
        <button
          ref={filterButton}
          className="filter-button"
          type="button"
          aria-haspopup="dialog"
          aria-controls="explore-filter-dialog"
          aria-expanded={filtersOpen}
          onClick={openFilters}
        >
          Filtri{activeFilterCount ? ` (${activeFilterCount})` : ""}
        </button>
        <span className="results-count" role="status" aria-live="polite" aria-atomic="true">
          {indexState === "loading"
            ? "Caricamento indice…"
            : response?.status === "QUERY_TOO_LONG"
              ? "Ricerca non eseguita"
              : `${records.length} ${records.length === 1 ? "risultato" : "risultati"}`}
        </span>
      </div>

      <dialog
        id="explore-filter-dialog"
        ref={filterDialog}
        className="dp-overlay dp-sheet"
        aria-labelledby="filter-title"
        onClose={() => {
          // A queued close event can arrive after the sheet was reopened.
          // Reflect the dialog's actual state rather than hiding a live sheet
          // from assistive technology by reverting aria-expanded to false.
          const isOpen = filterDialog.current?.open ?? false;
          setFiltersOpen(isOpen);
          if (!isOpen) filterButton.current?.focus();
        }}
      >
        <div className="dp-overlay__header">
          <h2 id="filter-title" className="dp-overlay__title">Filtri di ricerca</h2>
          <button className="quiet-button" type="button" aria-label="Chiudi filtri" onClick={closeFilters}>×</button>
        </div>
        <div className="dp-overlay__body filter-controls">
          <label>
            Tipo
            <select className="filter-button" value={kind} onChange={(event) => changeKind(event.target.value as SearchRecordKind | "ALL")}>
              <option value="ALL">Tutti i tipi</option>
              <option value="finding">Dichiarazioni</option>
              <option value="person">Persone</option>
              <option value="topic">Temi</option>
              <option value="content">Contenuti</option>
            </select>
          </label>
          <label>
            Esito
            <select className="filter-button" value={assessment} onChange={(event) => changeAssessment(event.target.value as AssessmentFilter)}>
              <option value="ALL">Tutti gli esiti</option>
              <option value="SUPPORTED">Supportata</option>
              <option value="FACTUALLY_FALSE">Conclusione fattualmente falsa</option>
              <option value="OUTDATED_DATA">Dato superato</option>
              <option value="INSUFFICIENT_EVIDENCE">Prove insufficienti</option>
              <option value="UNRESOLVED">Non risolta</option>
            </select>
          </label>
          <label>
            Persona
            <select
              className="filter-button"
              aria-label="Filtra dichiarazioni per persona pubblica"
              value={personId}
              onChange={(event) => {
                const next = event.target.value;
                pushFilterState({ personId: next });
                setPersonId(next);
              }}
            >
              <option value="ALL">Tutte le persone pubbliche</option>
              {people.map((person) => <option key={person.id} value={person.id}>{person.title}</option>)}
            </select>
          </label>
          <label>
            Tema
            <select
              className="filter-button"
              aria-label="Filtra dichiarazioni per tema pubblico"
              value={topicId}
              onChange={(event) => {
                const next = event.target.value;
                pushFilterState({ topicId: next });
                setTopicId(next);
              }}
            >
              <option value="ALL">Tutti i temi pubblici</option>
              {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.title}</option>)}
            </select>
          </label>
          <label>
            Ordine
            <select className="sort-select" value={sort} onChange={(event) => changeSort(event.target.value as SortOrder)}>
              <option value="relevance">Più pertinenti</option>
              <option value="recent">Più recenti</option>
              <option value="old">Meno recenti</option>
            </select>
          </label>
        </div>
        <div className="dp-overlay__footer">
          <button className="quiet-button" type="button" onClick={resetFilters}>Azzera filtri</button>
          <button className="primary-button" type="button" onClick={closeFilters}>Mostra risultati</button>
        </div>
      </dialog>

      {indexState === "ready" && response?.status === "OK" && (
        <>
          {records.length > 0 && (
            <p className="claim-row-meta">
              La data mostrata indica la pubblicazione del risultato o della fonte, quando
              disponibile: non è la data della dichiarazione. La data di aggiunta
              all’archivio non è disponibile in questo indice.
            </p>
          )}
          <div className="claim-list explore-list">
            {records.map((record, position) => (
              <article className="claim-row explore-row" key={`${record.kind}:${record.id}`}>
                <div className="explore-rank" aria-hidden="true">{String(position + 1).padStart(2, "0")}</div>
                <div className="claim-row-date">{record.published_at ? formatDate(record.published_at) : kindLabels[record.kind]}</div>
                <div className="claim-row-main">
                  <div className="eyebrow">{kindLabels[record.kind]}</div>
                  <a className="claim-row-claim" href={record.route}>{record.title}</a>
                  {record.kind === "finding" && record.wording_type === "PARAPHRASE" && (
                    <div className="claim-row-meta">
                      Formulazione normalizzata · non è una citazione testuale
                    </div>
                  )}
                  {record.subtitle && <div className="claim-row-meta"><span>{record.subtitle}</span></div>}
                  {(record.has_corrections || record.has_rights_of_reply) && (
                    <div className="claim-row-meta">
                      <a href={`${record.route}#storia`}>
                        {record.has_corrections && record.has_rights_of_reply
                          ? "Correzioni e repliche nel record"
                          : record.has_corrections ? "Correzioni nel record" : "Repliche nel record"}
                      </a>
                    </div>
                  )}
                </div>
                {record.assessment && (
                  <div className="claim-row-status">
                    <span className={`assessment assessment-${assessmentTone(record.assessment)} assessment-compact`}>
                      <span className="assessment-mark" aria-hidden="true" />
                      <span>{assessmentLabel(record.assessment)}</span>
                    </span>
                  </div>
                )}
                <span className="claim-row-arrow" aria-hidden="true">→</span>
              </article>
            ))}
          </div>
          {records.length === 0 && (
            <div className="dp-state" data-state="empty" aria-live="polite">
              <h2 className="dp-state__title">
                {index?.records.length === 0 ? "L'archivio pubblico è ancora vuoto." : "Nessun record pubblico corrisponde."}
              </h2>
              <p className="dp-state__body">
                {index?.records.length === 0
                  ? "Non ci sono ancora dichiarazioni o risorse autorizzate nello snapshot pubblico. Nessun risultato privato viene mostrato."
                  : "Modifica la ricerca o azzera i filtri. La combinazione Persona × Tema considera soltanto dichiarazioni pubblicate, senza avviare analisi live."}
              </p>
              <button className="quiet-button" type="button" onClick={() => { setQuery(""); resetFilters(); }}>Azzera ricerca e filtri</button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
