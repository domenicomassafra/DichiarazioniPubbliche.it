import type {
  StudioCollectionRow,
  StudioCorpusResult,
  StudioInboxRow,
  StudioSourceBoundStatus,
} from "./studioViewModel.ts";

// DP-415..419: browser-side fixture navigation only. Never accept private
// database material here; real operator queries must run behind private auth.
export const STUDIO_READ_ONLY_VERSION = "studio-readonly-fixture-v1" as const;

function normalized(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase("it").trim();
}

export function filterCorpusResults(
  results: readonly StudioCorpusResult[],
  query: string,
  kind = "all",
  limit = 30,
): StudioCorpusResult[] {
  const clean = normalized(query).slice(0, 128);
  const terms = clean.split(/\s+/u).filter(Boolean);
  const maximum = Math.min(Math.max(1, Math.floor(limit)), 30);
  return results.filter((row) => {
    if (kind !== "all" && row.kind !== kind) return false;
    const searchable = normalized(`${row.title} ${row.excerpt} ${row.kind} ${row.source_ref}`);
    return terms.every((term) => searchable.includes(term));
  }).slice(0, maximum);
}

export function filterInboxRows(
  rows: readonly StudioInboxRow[],
  state: "all" | "ready" | "blocked",
): StudioInboxRow[] {
  return rows.filter((row) => state === "all" || row.status.query_state === state);
}

export function filterCollections(
  rows: readonly StudioCollectionRow[],
  query: string,
): StudioCollectionRow[] {
  const clean = normalized(query).slice(0, 128);
  return rows.filter((row) => normalized(`${row.title} ${row.scope}`).includes(clean)).slice(0, 30);
}

export function explainSourceBoundStatus(status: StudioSourceBoundStatus): string {
  if (status.query_state === "blocked") {
    return status.blocker_code
      ? `Operazione bloccata: ${status.blocker_code}. Nessuna modifica autorizzata.`
      : "Stato non valido: blocco senza codice.";
  }
  if (status.query_state === "empty") return "Nessun elemento disponibile nella fonte corrente.";
  if (status.query_state === "error") return "Errore della fonte; nessuna approvazione implicita.";
  if (status.query_state === "loading") return "Fonte in caricamento; esito ancora sconosciuto.";
  return "Record consultabile; non equivale a revisione o pubblicazione.";
}
