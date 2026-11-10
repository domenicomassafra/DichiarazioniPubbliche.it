import { useRef } from "react";
import type { PublicSearchRecord, SearchFilters, SearchRecordKind } from "../lib/searchIndex";

type RecordKind = SearchRecordKind | "ALL";
type AssessmentFilter = NonNullable<SearchFilters["assessment"]>;
type SortOrder = NonNullable<SearchFilters["sort"]>;

interface FilterProps {
  kind: RecordKind;
  assessment: AssessmentFilter;
  sort: SortOrder;
  personId: string;
  topicId: string;
  people: PublicSearchRecord[];
  topics: PublicSearchRecord[];
  facetCounts: { people: Record<string, number>; topics: Record<string, number> };
  onKind: (value: RecordKind) => void;
  onAssessment: (value: AssessmentFilter) => void;
  onSort: (value: SortOrder) => void;
  onPerson: (value: string) => void;
  onTopic: (value: string) => void;
  onReset: () => void;
  onClose: () => void;
}

interface SidebarProps extends FilterProps {
  kindCounts: Record<RecordKind, number>;
  activeFilterCount: number;
}

/** A real mobile dialog; focus and Escape are owned by its parent <dialog>. */
export function ExploreFilterSheet({
  kind, assessment, sort, personId, topicId, people, topics, facetCounts,
  onKind, onAssessment, onSort, onPerson, onTopic, onReset, onClose,
}: FilterProps) {
  return (
    <>
      <div className="dp-overlay__header">
        <h2 id="filter-title" className="dp-overlay__title">Filtri di ricerca</h2>
        <button className="quiet-button" type="button" aria-label="Chiudi filtri" onClick={onClose}>×</button>
      </div>
      <div className="dp-overlay__body filter-controls">
        <label>
          Tipo
          <select className="filter-button" value={kind} onChange={(event) => onKind(event.target.value as RecordKind)}>
            <option value="ALL">Tutti i tipi</option>
            <option value="finding">Dichiarazioni</option>
            <option value="statement">Dichiarazioni originali</option>
            <option value="person">Persone</option>
            <option value="topic">Temi</option>
            <option value="content">Contenuti</option>
          </select>
        </label>
        <label>
          Esito
          <select className="filter-button" value={assessment} onChange={(event) => onAssessment(event.target.value as AssessmentFilter)}>
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
            onChange={(event) => onPerson(event.target.value)}
          >
            <option value="ALL">Tutte le persone pubbliche</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.title} · {facetCounts.people[person.id] ?? 0} dichiarazioni
              </option>
            ))}
          </select>
        </label>
        <label>
          Tema
          <select
            className="filter-button"
            aria-label="Filtra dichiarazioni per tema pubblico"
            value={topicId}
            onChange={(event) => onTopic(event.target.value)}
          >
            <option value="ALL">Tutti i temi pubblici</option>
            {topics.map((topic) => (
              <option key={topic.id} value={topic.id}>
                {topic.title} · {facetCounts.topics[topic.id] ?? 0} dichiarazioni
              </option>
            ))}
          </select>
        </label>
        <label>
          Ordine
          <select className="sort-select" value={sort} onChange={(event) => onSort(event.target.value as SortOrder)}>
            <option value="relevance">Più pertinenti</option>
            <option value="recent">Più recenti</option>
            <option value="old">Meno recenti</option>
          </select>
        </label>
      </div>
      <div className="dp-overlay__footer">
        <button className="quiet-button" type="button" onClick={onReset}>Azzera filtri</button>
        <button className="primary-button" type="button" onClick={onClose}>Mostra risultati</button>
      </div>
    </>
  );
}

/** Inline desktop controls share exactly the same verified index and actions. */
export function ExploreSidebar({
  kind, assessment, personId, topicId, people, topics, kindCounts,
  activeFilterCount, onKind, onAssessment, onPerson, onTopic, onReset,
}: SidebarProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  return (
    <aside className="explore-refinement" aria-label="Filtra i risultati">
      <div className="explore-refinement-heading">
        <h2 ref={heading} tabIndex={-1}>Filtra i risultati</h2>
        {activeFilterCount > 0 && (
          <button type="button" onClick={() => {
            onReset();
            heading.current?.focus();
          }}>Azzera</button>
        )}
      </div>
      <fieldset>
        <legend>Tipo di contenuto</legend>
        {([
          ["ALL", "Tutti i risultati"], ["finding", "Dichiarazioni"],
          ["statement", "Originali"], ["person", "Persone"],
          ["topic", "Temi"], ["content", "Contenuti"],
        ] as const).map(([value, label]) => (
          <button key={value} type="button" className="explore-refinement-choice"
            aria-pressed={kind === value} onClick={() => onKind(value)}>
            <span>{label}</span><span>{kindCounts[value]}</span>
          </button>
        ))}
      </fieldset>
      <fieldset>
        <legend>Esito della verifica</legend>
        {([
          ["ALL", "Tutti gli esiti"], ["SUPPORTED", "Supportata"],
          ["FACTUALLY_FALSE", "Conclusione falsa"], ["OUTDATED_DATA", "Dato superato"],
          ["INSUFFICIENT_EVIDENCE", "Prove insufficienti"], ["UNRESOLVED", "Non risolta"],
        ] as const).map(([value, label]) => (
          <button key={value} type="button" className="explore-refinement-choice"
            aria-pressed={assessment === value} onClick={() => onAssessment(value)}>
            <span>{label}</span><span aria-hidden="true">{assessment === value ? "●" : "○"}</span>
          </button>
        ))}
      </fieldset>
      <div className="explore-refinement-selects">
        <label>Persona
          <select value={personId} onChange={(event) => onPerson(event.target.value)}>
            <option value="ALL">Tutte le persone</option>
            {people.map((person) => <option key={person.id} value={person.id}>{person.title}</option>)}
          </select>
        </label>
        <label>Tema
          <select value={topicId} onChange={(event) => onTopic(event.target.value)}>
            <option value="ALL">Tutti i temi</option>
            {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.title}</option>)}
          </select>
        </label>
      </div>
      <p className="explore-refinement-note">I filtri utilizzano soltanto l’indice dei record pubblicati.</p>
    </aside>
  );
}
