import { useEffect, useState } from "react";
import { assessmentLabel, assessmentTone } from "../lib/format";
import type { ContentAuditFixture } from "../lib/types";

export default function ContentAuditClient({ audit }: { audit: ContentAuditFixture }) {
  const [selectedId, setSelectedId] = useState(audit.moments[0]?.id ?? "");
  const selected = audit.moments.find((item) => item.id === selectedId) ?? audit.moments[0];

  useEffect(() => {
    // Read only IDs present in this already-public, demo-only moment list.
    // Keep the initial render deterministic for server/client hydration.
    const requested = new URLSearchParams(window.location.search).get("momento");
    if (requested && audit.moments.some((moment) => moment.id === requested)) {
      setSelectedId(requested);
    }
  }, [audit.moments]);

  const selectMoment = (id: string) => {
    setSelectedId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("momento", id);
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  };

  return (
    <div className="audit-layout">
      <div>
        <div className="audit-player" aria-label="Player dimostrativo del contenuto">
          <span className="audit-player-play" aria-hidden="true">▶</span>
        </div>

        <div className="evidence-tape" aria-label="Momenti verificati nel contenuto">
          <div className="tape-marks">
            {audit.moments.map((moment) => (
              <button key={moment.id} className={`tape-mark ${selectedId === moment.id ? "is-active" : ""}`} type="button" onClick={() => selectMoment(moment.id)} aria-pressed={selectedId === moment.id}>
                <span className="tape-dot" aria-hidden="true" />
                <span>{moment.timestamp}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="moment-list">
          {audit.moments.map((moment) => (
            <button key={moment.id} type="button" className={`moment-row ${selectedId === moment.id ? "is-active" : ""}`} onClick={() => selectMoment(moment.id)} aria-pressed={selectedId === moment.id}>
              <span className="moment-time">{moment.timestamp}</span>
              <span className="moment-claim">{moment.claim}</span>
              <span className={`assessment assessment-${assessmentTone(moment.assessment)} assessment-compact`}>
                <span className="assessment-mark" aria-hidden="true" />
                <span>{assessmentLabel(moment.assessment)}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <aside className="audit-detail" aria-live="polite">
          <div className="eyebrow">Momento selezionato · {selected.timestamp}</div>
          <h2>{selected.claim}</h2>
          <span className={`assessment assessment-${assessmentTone(selected.assessment)}`}>
            <span className="assessment-mark" aria-hidden="true" />
            <span>{assessmentLabel(selected.assessment)}</span>
          </span>
          <p>{selected.summary}</p>
          <div className="audit-sources">
            <strong>Fonti principali</strong>
            {selected.sources.map((source) => (
              <div className="audit-source" key={`${source.publisher}-${source.label}`}>
                <strong>{source.publisher}</strong><br />
                <span>{source.label}</span>
              </div>
            ))}
          </div>
        </aside>
      )}
    </div>
  );
}
