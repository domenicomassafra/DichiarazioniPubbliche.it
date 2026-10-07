import type {
  StudioCollectionsViewModel,
  StudioCorpusViewModel,
  StudioInboxViewModel,
  StudioVerifyViewModel,
} from "../lib/studioViewModel.ts";
import { STUDIO_VIEW_MODEL_VERSION } from "../lib/studioViewModel.ts";

export const studioCorpusFixture: StudioCorpusViewModel = {
  contract_version: STUDIO_VIEW_MODEL_VERSION,
  workspace: "corpus",
  title: "Corpus",
  dominant_task: "Cerca nei contenuti già acquisiti",
  fixture_only: true,
  query: "servizi pubblici territorio",
  statuses: [
    {
      id: "corpus-result-count",
      label: "Risultati query",
      value: 3,
      source_kind: "corpus_query",
      source_ref: "fixture:corpus-query:servizi-pubblici-territorio",
      query_state: "ready",
      blocker_code: null,
    },
  ],
  results: [
    {
      id: "passage:servizi:0312",
      kind: "passage",
      title: "Intervista: servizi pubblici e territorio · 03:12",
      source_ref: "fixture:capture:servizi:v1#passage-0312",
      excerpt: "I tempi medi di attesa sono diminuiti in tutte le aree del territorio.",
    },
    {
      id: "content:trasporti:2027",
      kind: "content",
      title: "Piano trasporti 2027",
      source_ref: "fixture:capture:trasporti:v2",
      excerpt: "Documento acquisito con passaggi indicizzati e provenienza di cattura.",
    },
    {
      id: "collection:servizi-locali",
      kind: "collection",
      title: "Servizi locali 2026",
      source_ref: "fixture:collection:servizi-locali",
      excerpt: "Raccolta di ricerca con fonti, passaggi e claim collegati.",
    },
  ],
};

export const studioInboxFixture: StudioInboxViewModel = {
  contract_version: STUDIO_VIEW_MODEL_VERSION,
  workspace: "inbox",
  title: "Inbox",
  dominant_task: "Esamina il prossimo elemento da triagiare",
  fixture_only: true,
  statuses: [
    {
      id: "inbox-visible-count",
      label: "Elementi nella query corrente",
      value: 2,
      source_kind: "discovery_queue",
      source_ref: "fixture:discovery-query:triage-open",
      query_state: "ready",
      blocker_code: null,
    },
  ],
  rows: [
    {
      id: "discovery:new-content:1",
      title: "Nuovo contenuto rilevato dalla fonte monitorata",
      provenance_ref: "fixture:discovery-run:2026-10-05:item-1",
      status: {
        id: "discovery:new-content:1:status",
        label: "Da ispezionare",
        source_kind: "discovery_queue",
        source_ref: "fixture:discovery-run:2026-10-05:item-1",
        query_state: "ready",
        blocker_code: null,
      },
    },
    {
      id: "discovery:blocked:2",
      title: "Cattura modificata con verifica diritti richiesta",
      provenance_ref: "fixture:discovery-run:2026-10-05:item-2",
      status: {
        id: "discovery:blocked:2:status",
        label: "Bloccato",
        source_kind: "discovery_queue",
        source_ref: "fixture:discovery-run:2026-10-05:item-2",
        query_state: "blocked",
        blocker_code: "RIGHTS_REVIEW_REQUIRED",
      },
    },
  ],
};

export const studioCollectionsFixture: StudioCollectionsViewModel = {
  contract_version: STUDIO_VIEW_MODEL_VERSION,
  workspace: "collections",
  title: "Collections",
  dominant_task: "Apri una raccolta e individua il prossimo gap di ricerca",
  fixture_only: true,
  statuses: [
    {
      id: "collection-query-count",
      label: "Raccolte nella query corrente",
      value: 2,
      source_kind: "research_collection",
      source_ref: "fixture:collection-query:active",
      query_state: "ready",
      blocker_code: null,
    },
  ],
  collections: [
    {
      id: "collection:servizi-locali",
      title: "Servizi locali 2026",
      scope: "Tempi di attesa, mobilità e servizi territoriali.",
      status: {
        id: "collection:servizi-locali:status",
        label: "Ricerca aperta",
        source_kind: "research_collection",
        source_ref: "fixture:collection:servizi-locali",
        query_state: "ready",
        blocker_code: null,
      },
    },
    {
      id: "collection:energia-reti",
      title: "Energia e reti locali",
      scope: "Produzione locale, capacità di rete e serie territoriali.",
      status: {
        id: "collection:energia-reti:status",
        label: "Copertura incompleta",
        source_kind: "research_collection",
        source_ref: "fixture:collection:energia-reti",
        query_state: "blocked",
        blocker_code: "COVERAGE_NEED_OPEN",
      },
    },
  ],
};

export const studioVerifyFixture: StudioVerifyViewModel = {
  contract_version: STUDIO_VIEW_MODEL_VERSION,
  workspace: "verify",
  title: "Verify",
  dominant_task: "Verifica il claim selezionato contro le evidenze disponibili",
  fixture_only: true,
  source_title: "Intervista: servizi pubblici e territorio",
  statuses: [
    {
      id: "verify-transcript-state",
      label: "Trascrizione",
      value: "completa",
      source_kind: "verification_run",
      source_ref: "fixture:verification-run:servizi:v1",
      query_state: "ready",
      blocker_code: null,
    },
    {
      id: "verify-claim-count",
      label: "Claim nella sessione",
      value: 3,
      source_kind: "verification_run",
      source_ref: "fixture:verification-run:servizi:v1#claims",
      query_state: "ready",
      blocker_code: null,
    },
  ],
  transcript: [
    { time: "00:18", text: "Il programma parte da una fotografia aggiornata dei servizi." },
    { time: "03:12", text: "I tempi medi di attesa sono diminuiti in tutte le aree del territorio." },
    { time: "08:46", text: "Il programma di borse di studio ha raggiunto tutti i posti previsti." },
    { time: "14:05", text: "La rete locale copre già quasi tutto il fabbisogno energetico." },
  ],
  claims: [
    {
      id: "claim-wait",
      time: "03:12",
      statement: "I tempi medi di attesa sono diminuiti in tutte le aree del territorio.",
      normalized: "I tempi medi di attesa sono diminuiti uniformemente nel territorio.",
      observation: "I dati disponibili non sostengono ancora una diminuzione uniforme.",
      status: {
        id: "claim-wait:status",
        label: "Revisione richiesta",
        source_kind: "verification_run",
        source_ref: "fixture:verification-run:servizi:v1#claim-wait",
        query_state: "ready",
        blocker_code: null,
      },
      original_source_resolution: {
        status: "RESOLVED",
        need_type: "PRIMARY_SOURCE",
        root_content_id: "content:fixture:servizi:originale",
        path_content_ids: [
          "content:fixture:servizi:ripubblicazione",
          "content:fixture:servizi:originale",
        ],
        path_edge_ids: ["derivation:fixture:servizi:ripubblicazione-originale"],
        source_ref: "fixture:coverage-need:claim-wait#original_source_resolution",
      },
      evidence: [
        {
          id: "evidence:wait:1",
          source: "Osservatorio sanitario",
          date: "18 set 2026",
          status: {
            id: "evidence:wait:1:status",
            label: "Approvata per la verifica",
            source_kind: "review_event",
            source_ref: "fixture:review:evidence:wait:1",
            query_state: "ready",
            blocker_code: null,
          },
        },
        {
          id: "evidence:wait:2",
          source: "Rapporto territoriale",
          date: "10 set 2026",
          status: {
            id: "evidence:wait:2:status",
            label: "Recuperata, non ancora approvata",
            source_kind: "verification_run",
            source_ref: "fixture:verification-run:servizi:v1#evidence-wait-2",
            query_state: "ready",
            blocker_code: null,
          },
        },
      ],
    },
    {
      id: "claim-study",
      time: "08:46",
      statement: "Il programma di borse di studio ha raggiunto tutti i posti previsti.",
      normalized: "Il programma ha coperto il numero di borse pianificato per il periodo.",
      observation: "Il rendiconto pubblicato è coerente con l'obiettivo numerico indicato.",
      status: {
        id: "claim-study:status",
        label: "Analisi completata; revisione separata",
        source_kind: "verification_run",
        source_ref: "fixture:verification-run:servizi:v1#claim-study",
        query_state: "ready",
        blocker_code: null,
      },
      evidence: [],
    },
    {
      id: "claim-energy",
      time: "14:05",
      statement: "La rete locale copre già quasi tutto il fabbisogno energetico.",
      normalized: "La produzione locale copre una quota prossima al totale del fabbisogno.",
      observation: "Le serie disponibili hanno perimetri diversi.",
      status: {
        id: "claim-energy:status",
        label: "Verifica bloccata",
        source_kind: "verification_run",
        source_ref: "fixture:verification-run:servizi:v1#claim-energy",
        query_state: "blocked",
        blocker_code: "EVIDENCE_SCOPE_MISMATCH",
      },
      evidence: [],
    },
  ],
  actions: [
    {
      id: "analyze-selected-claim",
      label: "Aggiorna analisi",
      domain: "analysis",
      enabled: false,
      availability: {
        id: "analyze-selected-claim:availability",
        label: "Runtime di analisi non collegato nella fixture",
        source_kind: "runtime_config",
        source_ref: "fixture:mutation-authority:none",
        query_state: "blocked",
        blocker_code: "FIXTURE_NO_MUTATION_AUTHORITY",
      },
    },
    {
      id: "request-review",
      label: "Invia a revisione",
      domain: "review",
      enabled: false,
      availability: {
        id: "request-review:availability",
        label: "Runtime di revisione non collegato nella fixture",
        source_kind: "runtime_config",
        source_ref: "fixture:mutation-authority:none",
        query_state: "blocked",
        blocker_code: "FIXTURE_NO_MUTATION_AUTHORITY",
      },
    },
  ],
};

export const studioFixtures = {
  corpus: studioCorpusFixture,
  inbox: studioInboxFixture,
  collections: studioCollectionsFixture,
  verify: studioVerifyFixture,
} as const;
