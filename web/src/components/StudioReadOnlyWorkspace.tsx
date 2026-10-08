import { useId, useMemo, useState } from "react";
import {
  explainSourceBoundStatus,
  filterCollections,
  filterCorpusResults,
  filterInboxRows,
} from "../lib/studioReadOnlyWorkflows";
import type {
  StudioCorpusViewModel,
  StudioInboxViewModel,
  StudioCollectionsViewModel,
  StudioSourceBoundStatus,
} from "../lib/studioViewModel";

type Model = StudioCorpusViewModel | StudioInboxViewModel | StudioCollectionsViewModel;

function StatusText({ status }: { status: StudioSourceBoundStatus }) {
  return (
    <div className="studio-v3-inspector-status" data-query-state={status.query_state}>
      <strong>{status.label}</strong>
      <p>{explainSourceBoundStatus(status)}</p>
      <dl><dt>Fonte dello stato</dt><dd><code>{status.source_ref}</code></dd></dl>
    </div>
  );
}

function CorpusWorkspace({ model }: { model: StudioCorpusViewModel }) {
  const queryLabel = useId();
  const kindLabel = useId();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [selectedId, setSelectedId] = useState(model.results[0]?.id ?? "");
  const visible = useMemo(() => filterCorpusResults(model.results, query, kind), [model.results, query, kind]);
  const selected = visible.find((row) => row.id === selectedId) ?? visible[0];
  const kinds = Array.from(new Set(model.results.map((row) => row.kind))).sort();

  return (
    <>
      <section className="studio-v3-primary" aria-labelledby={queryLabel}>
        <div className="studio-v3-primary-copy">
          <h2 id={queryLabel}>Ricerca nel campione Studio</h2>
          <p>Filtro lessicale locale sui soli record della fixture. Non interroga il database privato.</p>
        </div>
        <div className="studio-v3-controls">
          <label htmlFor={`${queryLabel}-input`}>Testo da cercare
            <input id={`${queryLabel}-input`} type="search" maxLength={128} value={query}
              onChange={(event) => setQuery(event.target.value)} placeholder="Termine o provenienza" />
          </label>
          <label htmlFor={kindLabel}>Tipo record
            <select id={kindLabel} value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="all">Tutti i tipi</option>
              {kinds.map((value) => <option value={value} key={value}>{value}</option>)}
            </select>
          </label>
        </div>
      </section>
      <div className="studio-v3-browser-grid">
        <section className="studio-v3-list" aria-label="Risultati filtrati del corpus">
          <h2 className="studio-v3-list-header" aria-live="polite">{visible.length} risultati nella fixture</h2>
          {visible.length === 0 && <p className="studio-v3-empty">Nessun record corrisponde ai filtri. Non equivale a un corpus vuoto.</p>}
          {visible.map((row) => (
            <button type="button" key={row.id} className="studio-v3-select-row"
              aria-pressed={selected?.id === row.id} onClick={() => setSelectedId(row.id)}>
              <span className="eyebrow">{row.kind}</span>
              <strong>{row.title}</strong>
              <small>{row.source_ref}</small>
            </button>
          ))}
        </section>
        <section className="studio-v3-inspector" aria-label="Provenienza del risultato selezionato" aria-live="polite">
          <h2>Provenienza e passaggio</h2>
          {selected ? (
            <>
              <p><strong>{selected.title}</strong></p>
              <p>{selected.excerpt}</p>
              <dl>
                <dt>Identificatore record</dt><dd><code>{selected.id}</code></dd>
                <dt>Riferimento alla fonte</dt><dd><code>{selected.source_ref}</code></dd>
                <dt>Tipo</dt><dd>{selected.kind}</dd>
              </dl>
              <p className="studio-v3-boundary">Ispezione di fixture, non approvazione. Nessun corpo sorgente o documento privato è disponibile nel browser.</p>
            </>
          ) : <p>Nessun risultato selezionabile.</p>}
        </section>
      </div>
    </>
  );
}

function InboxWorkspace({ model }: { model: StudioInboxViewModel }) {
  const [state, setState] = useState<"all" | "ready" | "blocked">("all");
  const [selectedId, setSelectedId] = useState(model.rows[0]?.id ?? "");
  const visible = filterInboxRows(model.rows, state);
  const selected = visible.find((row) => row.id === selectedId) ?? visible[0];
  const filterId = useId();
  return (
    <>
      <section className="studio-v3-primary" aria-labelledby={filterId}>
        <h2 id={filterId}>Triage e impedimenti</h2>
        <p>Anteprima di consultazione. Le azioni che cambiano lo stato richiedono il runtime privato e non sono disponibili qui.</p>
        <div className="studio-v3-controls">
          <label>Stato della coda
            <select value={state} onChange={(event) => setState(event.target.value as typeof state)}>
              <option value="all">Tutti</option><option value="ready">Da ispezionare</option><option value="blocked">Bloccati</option>
            </select>
          </label>
        </div>
      </section>
      <div className="studio-v3-browser-grid">
        <section className="studio-v3-list" aria-label="Coda da ispezionare">
          <h2 className="studio-v3-list-header" aria-live="polite">{visible.length} elementi nella fixture</h2>
          {visible.map((row) => (
            <button key={row.id} type="button" className="studio-v3-select-row"
              aria-pressed={selected?.id === row.id} onClick={() => setSelectedId(row.id)}>
              <strong>{row.title}</strong>
              <small>{row.status.label}</small>
            </button>
          ))}
          {visible.length === 0 && <p className="studio-v3-empty">Nessun elemento nello stato selezionato.</p>}
        </section>
        <section className="studio-v3-inspector" aria-label="Origine e impedimenti" aria-live="polite">
          <h2>Provenienza del candidato</h2>
          {selected ? (
            <>
              <p><strong>{selected.title}</strong></p>
              <dl><dt>ID coda</dt><dd><code>{selected.id}</code></dd>
                <dt>Fonte discovery</dt><dd><code>{selected.provenance_ref}</code></dd></dl>
              <StatusText status={selected.status} />
              <p className="studio-v3-boundary">Nessuna approvazione, merge, estrazione o promozione da questa vista.</p>
            </>
          ) : <p>Selezionare un elemento della coda.</p>}
        </section>
      </div>
    </>
  );
}

function CollectionsWorkspace({ model }: { model: StudioCollectionsViewModel }) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(model.collections[0]?.id ?? "");
  const visible = filterCollections(model.collections, query);
  const selected = visible.find((row) => row.id === selectedId) ?? visible[0];
  const searchId = useId();
  return (
    <>
      <section className="studio-v3-primary" aria-labelledby={searchId}>
        <h2 id={searchId}>Raccolte e ambito di ricerca</h2>
        <p>Apri una scheda della fixture; fonti, cronologia e candidati persistiti richiedono la connessione privata.</p>
        <div className="studio-v3-controls">
          <label>Filtra raccolte
            <input type="search" maxLength={128} value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
        </div>
      </section>
      <div className="studio-v3-browser-grid">
        <section className="studio-v3-list" aria-label="Raccolte selezionabili">
          <h2 className="studio-v3-list-header" aria-live="polite">{visible.length} raccolte nella fixture</h2>
          {visible.map((row) => (
            <button key={row.id} type="button" className="studio-v3-select-row"
              aria-pressed={selected?.id === row.id} onClick={() => setSelectedId(row.id)}>
              <strong>{row.title}</strong><small>{row.scope}</small>
            </button>
          ))}
          {visible.length === 0 && <p className="studio-v3-empty">Nessuna raccolta corrisponde al filtro.</p>}
        </section>
        <section className="studio-v3-inspector" aria-label="Dettaglio raccolta" aria-live="polite">
          <h2>Ambito e stato</h2>
          {selected ? (
            <>
              <p><strong>{selected.title}</strong></p><p>{selected.scope}</p>
              <dl><dt>ID raccolta</dt><dd><code>{selected.id}</code></dd></dl>
              <StatusText status={selected.status} />
              <p className="studio-v3-boundary">I collegamenti a fonti, passaggi e claim non sono ancora disponibili nel campione: nessun risultato inventato.</p>
            </>
          ) : <p>Selezionare una raccolta.</p>}
        </section>
      </div>
    </>
  );
}

export default function StudioReadOnlyWorkspace({ model }: { model: Model }) {
  if (!model.fixture_only) {
    return <p className="studio-v3-unavailable">STUDIO_PRIVATE_SOURCE_REQUIRED: collegamento privato non configurato.</p>;
  }
  if (model.workspace === "corpus") return <CorpusWorkspace model={model} />;
  if (model.workspace === "inbox") return <InboxWorkspace model={model} />;
  return <CollectionsWorkspace model={model} />;
}
