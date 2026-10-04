import { useMemo, useState } from "react";
import { studioWorkspace } from "../data/studio";

export default function StudioWorkspaceClient() {
  const [selectedId, setSelectedId] = useState(studioWorkspace.claims[0].id);
  const selected = useMemo(
    () => studioWorkspace.claims.find((claim) => claim.id === selectedId) ?? studioWorkspace.claims[0],
    [selectedId]
  );

  return (
    <div className="workspace-grid">
      <section className="workspace-pane" aria-label="Fonte e trascrizione">
        <div className="pane-header"><h2>Fonte e trascrizione</h2><span className="eyebrow">Video</span></div>
        <div className="studio-media"><span className="audit-player-play">▶</span></div>
        <div className="transcript-list">
          {studioWorkspace.transcript.map((line) => {
            const active = line.time === selected.time;
            return (
              <button className={`transcript-line ${active ? "is-active" : ""}`} type="button" key={line.time} onClick={() => {
                const claim = studioWorkspace.claims.find((item) => item.time === line.time);
                if (claim) setSelectedId(claim.id);
              }}>
                <span className="transcript-time">{line.time}</span>
                <span>{line.text}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="workspace-pane" aria-label="Claim rilevate">
        <div className="pane-header"><h2>Claim rilevate</h2><span className="eyebrow">{studioWorkspace.claims.length} claim</span></div>
        <div className="claim-queue">
          {studioWorkspace.claims.map((claim) => (
            <button className={`queue-row ${claim.id === selectedId ? "is-active" : ""}`} type="button" key={claim.id} onClick={() => setSelectedId(claim.id)}>
              <span className="queue-time">{claim.time}</span>
              <span>
                <span className="queue-claim">{claim.statement}</span>
                <span className="queue-state">{claim.state} · {claim.evidence.length} fonti</span>
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="workspace-pane" aria-label="Dettaglio claim">
        <div className="pane-header"><h2>Dettaglio claim</h2><span className="eyebrow">{selected.time}</span></div>
        <div className="claim-detail" aria-live="polite">
          <div className="eyebrow">{selected.state}</div>
          <h1>{selected.statement}</h1>
          <div className="detail-block">
            <h3>Claim normalizzato</h3>
            <p>{selected.normalized}</p>
          </div>
          <div className="detail-block">
            <h3>Osservazione</h3>
            <p>{selected.observation}</p>
          </div>
          <div className="detail-block">
            <h3>Fonti collegate ({selected.evidence.length})</h3>
            {selected.evidence.map((item) => (
              <div className="evidence-review-row" key={`${item.source}-${item.date}`}>
                <span><strong>{item.source}</strong><br /><small>{item.date}</small></span>
                <span>{item.state}</span>
              </div>
            ))}
          </div>
          <div className="studio-actions">
            <button className="primary-button" type="button">Invia a revisione</button>
            <button className="secondary-button" type="button">Metti in attesa</button>
          </div>
        </div>
      </section>
    </div>
  );
}
