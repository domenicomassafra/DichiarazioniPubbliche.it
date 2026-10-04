import { useEffect, useMemo, useState } from "react";
import { assessmentLabel, assessmentTone, dossierSlug, formatDate } from "../lib/format";
import type { PublicDossier } from "../lib/types";

interface Props { dossiers: PublicDossier[] }

export default function ExploreClient({ dossiers }: Props) {
  const [query, setQuery] = useState("");
  const [assessment, setAssessment] = useState("ALL");
  const [sort, setSort] = useState("recent");
  const [urlReady, setUrlReady] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQuery(params.get("q") ?? "");
    const nextAssessment = params.get("esito");
    if (nextAssessment) setAssessment(nextAssessment);
    const nextSort = params.get("ordine");
    if (nextSort === "old" || nextSort === "recent") setSort(nextSort);
    setUrlReady(true);
  }, []);

  useEffect(() => {
    if (!urlReady) return;
    const params = new URLSearchParams(window.location.search);
    const normalizedQuery = query.trim();
    if (normalizedQuery) params.set("q", normalizedQuery);
    else params.delete("q");
    if (assessment !== "ALL") params.set("esito", assessment);
    else params.delete("esito");
    if (sort !== "recent") params.set("ordine", sort);
    else params.delete("ordine");
    const search = params.toString();
    const next = `${window.location.pathname}${search ? `?${search}` : ""}`;
    window.history.replaceState(null, "", next);
  }, [assessment, query, sort, urlReady]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("it");
    const next = dossiers.filter((item) => {
      const haystack = [item.claim, item.speaker.name, item.source.title, item.claim_type]
        .join(" ")
        .toLocaleLowerCase("it");
      return (!needle || haystack.includes(needle)) &&
        (assessment === "ALL" || item.finding.assessment === assessment);
    });
    next.sort((a, b) => {
      const da = new Date(a.finding.published_at ?? a.source.published_at ?? 0).getTime();
      const db = new Date(b.finding.published_at ?? b.source.published_at ?? 0).getTime();
      return sort === "old" ? da - db : db - da;
    });
    return next;
  }, [assessment, dossiers, query, sort]);

  return (
    <section className="explore-client" aria-label="Risultati di ricerca">
      <label className="dp-visually-hidden" htmlFor="client-search">Cerca nel record pubblico</label>
      <div className="search-field" style={{ margin: "0 0 22px" }}>
        <span className="search-icon" aria-hidden="true">⌕</span>
        <input id="client-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca dichiarazioni, persone, temi, video…" />
        {query && <button type="button" aria-label="Pulisci ricerca" onClick={() => setQuery("")}>×</button>}
      </div>

      <div className="filter-row">
        <div className="filter-controls">
          <label>
            <span className="dp-visually-hidden">Filtra per esito</span>
            <select className="filter-button" value={assessment} onChange={(event) => setAssessment(event.target.value)}>
              <option value="ALL">Tutti gli esiti</option>
              <option value="SUPPORTED">Supportata</option>
              <option value="FACTUALLY_FALSE">Conclusione fattualmente falsa</option>
              <option value="OUTDATED_DATA">Dato superato</option>
              <option value="INSUFFICIENT_EVIDENCE">Prove insufficienti</option>
              <option value="UNRESOLVED">Non risolta</option>
            </select>
          </label>
          <label>
            <span className="dp-visually-hidden">Ordina risultati</span>
            <select className="sort-select" value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="recent">Più recenti</option>
              <option value="old">Meno recenti</option>
            </select>
          </label>
        </div>
        <span className="results-count">{filtered.length} {filtered.length === 1 ? "risultato" : "risultati"}</span>
      </div>

      <div className="claim-list explore-list">
        {filtered.map((dossier) => (
          <article className="claim-row explore-row" key={dossier.finding_id}>
            <div className="explore-rank" aria-hidden="true">{String(filtered.indexOf(dossier) + 1).padStart(2, "0")}</div>
            <div className="claim-row-date">{formatDate(dossier.finding.published_at)}</div>
            <div className="claim-row-main">
              <div className="eyebrow">{dossier.claim_type.replaceAll("_", " ")}</div>
              <a className="claim-row-claim" href={`/fact-check/${dossierSlug(dossier)}/`}>{dossier.claim}</a>
              <div className="claim-row-meta">
                <span>{dossier.speaker.name}</span><span aria-hidden="true">·</span><span>{dossier.source.title}</span>
              </div>
            </div>
            <div className="claim-row-status">
              <span className={`assessment assessment-${assessmentTone(dossier.finding.assessment)} assessment-compact`}>
                <span className="assessment-mark" aria-hidden="true" />
                <span>{assessmentLabel(dossier.finding.assessment)}</span>
              </span>
            </div>
            <span className="claim-row-arrow" aria-hidden="true">→</span>
          </article>
        ))}
      </div>
      {filtered.length === 0 && <p className="no-results">Nessun record pubblico corrisponde ai filtri correnti.</p>}
    </section>
  );
}
