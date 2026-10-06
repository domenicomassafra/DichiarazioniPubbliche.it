import { useEffect, useMemo, useRef, useState } from "react";
import { assessmentLabel, assessmentTone, formatDate } from "../lib/format";
import SegmentedControl from "./design/SegmentedControl";
import {
  SEARCH_QUERY_MAX_CHARS,
  buildExploreSearch,
  parseExploreSearch,
  searchPublicIndex,
  validateSearchIndex,
  type PublicSearchIndex,
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

export default function ExploreClient({ expectedProjectionSha256 }: Props) {
  const [query, setQuery] = useState("");
  const [assessment, setAssessment] = useState<AssessmentFilter>("ALL");
  const [kind, setKind] = useState<SearchRecordKind | "ALL">("ALL");
  const [sort, setSort] = useState<SortOrder>("relevance");
  const [urlReady, setUrlReady] = useState(false);
  const [index, setIndex] = useState<PublicSearchIndex | null>(null);
  const [indexState, setIndexState] = useState<"loading" | "ready" | "unavailable">("loading");
  const filterDialog = useRef<HTMLDialogElement>(null);
  const filterButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function restoreFromUrl() {
      const restored = parseExploreSearch(window.location.search);
      setQuery(restored.query);
      setAssessment(restored.assessment);
      setKind(restored.kind);
      setSort(restored.sort);
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
    const search = buildExploreSearch({ query, assessment, kind, sort });
    const next = `${window.location.pathname}${search ? `?${search}` : ""}`;
    window.history.replaceState(null, "", next);
  }, [assessment, kind, query, sort, urlReady]);

  const response = useMemo(() => {
    if (!index) return null;
    return searchPublicIndex(index, query, { assessment, kind, sort });
  }, [assessment, index, kind, query, sort]);

  const kindCounts = useMemo(() => {
    const counts: Record<SearchRecordKind | "ALL", number> = {
      ALL: 0,
      finding: 0,
      person: 0,
      topic: 0,
      content: 0,
    };
    if (!index) return counts;
    const rows = searchPublicIndex(index, query, { assessment, kind: "ALL", sort }).records;
    counts.ALL = rows.length;
    for (const record of rows) counts[record.kind] += 1;
    return counts;
  }, [assessment, index, query, sort]);

  const activeFilterCount = Number(assessment !== "ALL") + Number(kind !== "ALL") + Number(sort !== "relevance");
  const records = response?.records ?? [];

  function closeFilters() {
    filterDialog.current?.close();
    filterButton.current?.focus();
  }

  function pushFilterState(overrides: {
    assessment?: AssessmentFilter;
    kind?: SearchRecordKind | "ALL";
    sort?: SortOrder;
  }) {
    const nextAssessment = overrides.assessment ?? assessment;
    const nextKind = overrides.kind ?? kind;
    const nextSort = overrides.sort ?? sort;
    const search = buildExploreSearch({
      query,
      assessment: nextAssessment,
      kind: nextKind,
      sort: nextSort,
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
    pushFilterState({ assessment: "ALL", kind: "ALL", sort: "relevance" });
    setAssessment("ALL");
    setKind("ALL");
    setSort("relevance");
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
          id="client-search"
          type="search"
          value={query}
          maxLength={SEARCH_QUERY_MAX_CHARS}
          aria-describedby="search-limit"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Cerca dichiarazioni, persone, temi, contenuti…"
        />
        {query && <button type="button" aria-label="Pulisci ricerca" onClick={() => setQuery("")}>×</button>}
      </div>
      <p id="search-limit" className="dp-visually-hidden">Massimo {SEARCH_QUERY_MAX_CHARS} caratteri. La ricerca resta nel browser.</p>

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
          onClick={() => filterDialog.current?.showModal()}
        >
          Filtri{activeFilterCount ? ` (${activeFilterCount})` : ""}
        </button>
        <span className="results-count" aria-live="polite">
          {indexState === "loading" ? "Caricamento indice…" : `${records.length} ${records.length === 1 ? "risultato" : "risultati"}`}
        </span>
      </div>

      <dialog ref={filterDialog} className="dp-overlay dp-sheet" aria-labelledby="filter-title" onClose={() => filterButton.current?.focus()}>
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
          <div className="claim-list explore-list">
            {records.map((record, position) => (
              <article className="claim-row explore-row" key={`${record.kind}:${record.id}`}>
                <div className="explore-rank" aria-hidden="true">{String(position + 1).padStart(2, "0")}</div>
                <div className="claim-row-date">{record.published_at ? formatDate(record.published_at) : kindLabels[record.kind]}</div>
                <div className="claim-row-main">
                  <div className="eyebrow">{kindLabels[record.kind]}</div>
                  <a className="claim-row-claim" href={record.route}>{record.title}</a>
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
              <h2 className="dp-state__title">Nessun record pubblico corrisponde.</h2>
              <p className="dp-state__body">Modifica la ricerca o azzera i filtri. Non viene avviata una nuova analisi live.</p>
              <button className="quiet-button" type="button" onClick={() => { setQuery(""); setAssessment("ALL"); setKind("ALL"); setSort("relevance"); }}>Azzera ricerca e filtri</button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
