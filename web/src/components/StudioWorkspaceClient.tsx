import { useMemo, useState } from "react";
import type { StudioSourceBoundStatus, StudioVerifyViewModel } from "../lib/studioViewModel";

function SourceBoundStatus({ status }: { status: StudioSourceBoundStatus }) {
  return (
    <span
      className="studio-v3-status studio-v3-status--compact"
      data-studio-status
      data-source-kind={status.source_kind}
      data-source-ref={status.source_ref}
      data-query-state={status.query_state}
      data-blocker-code={status.blocker_code ?? "NONE"}
    >
      <span>{status.label}</span>
      {status.value !== undefined ? <strong>{status.value}</strong> : null}
      {status.blocker_code ? <code>{status.blocker_code}</code> : null}
    </span>
  );
}

export interface StudioWorkspaceClientProps {
  model: StudioVerifyViewModel;
}

export default function StudioWorkspaceClient({ model }: StudioWorkspaceClientProps) {
  const [selectedId, setSelectedId] = useState(model.claims[0]?.id ?? "");
  const selected = useMemo(
    () => model.claims.find((claim) => claim.id === selectedId) ?? model.claims[0],
    [model.claims, selectedId],
  );

  if (!selected) {
    return <div className="studio-v3-unavailable">Nessun claim nella query di verifica corrente.</div>;
  }

  const analysisActions = model.actions.filter((action) => action.domain === "analysis");
  const reviewActions = model.actions.filter((action) => action.domain === "review");

  return (
    <div className="workspace-grid studio-v3-verify-grid" data-verify-three-pane="true">
      <section className="workspace-pane" aria-label="Fonte e trascrizione">
        <div className="pane-header"><h2>Fonte e trascrizione</h2><span className="eyebrow">Fonte</span></div>
        <div className="claim-detail">
          <strong>{model.source_title}</strong>
        </div>
        <div className="transcript-list">
          {model.transcript.map((line) => {
            const active = line.time === selected.time;
            return (
              <button className={`transcript-line ${active ? "is-active" : ""}`} type="button" key={line.time} onClick={() => {
                const claim = model.claims.find((item) => item.time === line.time);
                if (claim) setSelectedId(claim.id);
              }}>
                <span className="transcript-time">{line.time}</span>
                <span>{line.text}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="workspace-pane" aria-label="Claim da verificare">
        <div className="pane-header"><h2>Claim</h2><span className="eyebrow">Query corrente</span></div>
        <div className="claim-queue">
          {model.claims.map((claim) => (
            <button className={`queue-row ${claim.id === selectedId ? "is-active" : ""}`} type="button" key={claim.id} onClick={() => setSelectedId(claim.id)}>
              <span className="queue-time">{claim.time}</span>
              <span>
                <span className="queue-claim">{claim.statement}</span>
                <SourceBoundStatus status={claim.status} />
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="workspace-pane" aria-label="Evidenze e revisione">
        <div className="pane-header"><h2>Evidenze e revisione</h2><span className="eyebrow">{selected.time}</span></div>
        <div className="claim-detail" aria-live="polite">
          <SourceBoundStatus status={selected.status} />
          <h2 className="studio-v3-selected-claim">{selected.statement}</h2>
          <div className="detail-block">
            <h3>Claim normalizzato</h3>
            <p>{selected.normalized}</p>
          </div>
          <div className="detail-block">
            <h3>Osservazione</h3>
            <p>{selected.observation}</p>
          </div>
          {selected.original_source_resolution ? (
            <div
              className="detail-block"
              data-original-source-resolution="true"
              data-source-ref={selected.original_source_resolution.source_ref}
              data-root-content-id={selected.original_source_resolution.root_content_id}
            >
              <h3>Origine revisionata</h3>
              <p>
                <strong>{selected.original_source_resolution.status}</strong>
                {" · "}{selected.original_source_resolution.need_type}
              </p>
              <p>Root: <code>{selected.original_source_resolution.root_content_id}</code></p>
              <ol>
                {selected.original_source_resolution.path_content_ids.map((contentId, index) => (
                  <li key={contentId}>
                    <code>{contentId}</code>
                    {index < selected.original_source_resolution!.path_edge_ids.length ? (
                      <small> via {selected.original_source_resolution!.path_edge_ids[index]}</small>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          <div className="detail-block">
            <h3>Evidenze collegate</h3>
            {selected.evidence.length === 0 ? <p>Nessuna evidenza nella query corrente.</p> : selected.evidence.map((item) => (
              <div className="evidence-review-row" key={item.id}>
                <span><strong>{item.source}</strong><br /><small>{item.date}</small></span>
                <SourceBoundStatus status={item.status} />
              </div>
            ))}
          </div>
          <div className="studio-v3-action-groups">
            <div className="studio-v3-action-group" data-action-domain="analysis">
              <span className="eyebrow">Analisi</span>
              {analysisActions.map((action) => (
                <div key={action.id}>
                  <button className="secondary-button" type="button" disabled={!action.enabled}>{action.label}</button>
                  <SourceBoundStatus status={action.availability} />
                </div>
              ))}
            </div>
            <div className="studio-v3-action-group" data-action-domain="review">
              <span className="eyebrow">Revisione</span>
              {reviewActions.map((action) => (
                <div key={action.id}>
                  <button className="primary-button" type="button" disabled={!action.enabled}>{action.label}</button>
                  <SourceBoundStatus status={action.availability} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
