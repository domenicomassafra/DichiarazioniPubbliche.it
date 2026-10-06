export const STUDIO_VIEW_MODEL_VERSION = "studio-private-view-v1" as const;

export type StudioWorkspaceKind = "corpus" | "inbox" | "collections" | "verify";

export type StudioSourceKind =
  | "corpus_query"
  | "discovery_queue"
  | "research_collection"
  | "verification_run"
  | "review_event"
  | "runtime_config";

export type StudioQueryState = "ready" | "empty" | "blocked" | "loading" | "error";

export interface StudioSourceBoundStatus {
  id: string;
  label: string;
  value?: string | number;
  source_kind: StudioSourceKind;
  source_ref: string;
  query_state: StudioQueryState;
  blocker_code: string | null;
}

export interface StudioAction {
  id: string;
  label: string;
  domain: "analysis" | "review";
  enabled: boolean;
  availability: StudioSourceBoundStatus;
}

export interface StudioBaseViewModel {
  contract_version: typeof STUDIO_VIEW_MODEL_VERSION;
  workspace: StudioWorkspaceKind;
  title: string;
  dominant_task: string;
  fixture_only: boolean;
  statuses: StudioSourceBoundStatus[];
}

export interface StudioCorpusResult {
  id: string;
  kind: "content" | "passage" | "statement" | "claim" | "person" | "topic" | "collection";
  title: string;
  source_ref: string;
  excerpt: string;
}

export interface StudioCorpusViewModel extends StudioBaseViewModel {
  workspace: "corpus";
  query: string;
  results: StudioCorpusResult[];
}

export interface StudioInboxRow {
  id: string;
  title: string;
  provenance_ref: string;
  status: StudioSourceBoundStatus;
}

export interface StudioInboxViewModel extends StudioBaseViewModel {
  workspace: "inbox";
  rows: StudioInboxRow[];
}

export interface StudioCollectionRow {
  id: string;
  title: string;
  scope: string;
  status: StudioSourceBoundStatus;
}

export interface StudioCollectionsViewModel extends StudioBaseViewModel {
  workspace: "collections";
  collections: StudioCollectionRow[];
}

export interface StudioTranscriptLine {
  time: string;
  text: string;
}

export interface StudioEvidenceRow {
  id: string;
  source: string;
  date: string;
  status: StudioSourceBoundStatus;
}

export interface StudioVerifyClaim {
  id: string;
  time: string;
  statement: string;
  normalized: string;
  observation: string;
  status: StudioSourceBoundStatus;
  evidence: StudioEvidenceRow[];
}

export interface StudioVerifyViewModel extends StudioBaseViewModel {
  workspace: "verify";
  source_title: string;
  transcript: StudioTranscriptLine[];
  claims: StudioVerifyClaim[];
  actions: StudioAction[];
}

export type StudioViewModel =
  | StudioCorpusViewModel
  | StudioInboxViewModel
  | StudioCollectionsViewModel
  | StudioVerifyViewModel;

export interface StudioUnavailableViewModel extends StudioBaseViewModel {
  fixture_only: false;
  unavailable: true;
}

function assertText(value: unknown, field: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`STUDIO_${field.toUpperCase()}_REQUIRED`);
  }
}

export function assertSourceBoundStatus(status: StudioSourceBoundStatus): void {
  assertText(status.id, "status_id");
  assertText(status.label, "status_label");
  assertText(status.source_kind, "source_kind");
  assertText(status.source_ref, "source_ref");
  assertText(status.query_state, "query_state");
  if (status.query_state === "blocked" && !status.blocker_code) {
    throw new Error("STUDIO_BLOCKED_STATUS_REQUIRES_BLOCKER_CODE");
  }
  if (status.query_state !== "blocked" && status.blocker_code) {
    throw new Error("STUDIO_NONBLOCKED_STATUS_HAS_BLOCKER_CODE");
  }
}

function collectStatuses(model: StudioViewModel): StudioSourceBoundStatus[] {
  const nested: StudioSourceBoundStatus[] = [];
  if (model.workspace === "inbox") {
    nested.push(...model.rows.map((row) => row.status));
  }
  if (model.workspace === "collections") {
    nested.push(...model.collections.map((collection) => collection.status));
  }
  if (model.workspace === "verify") {
    nested.push(...model.claims.map((claim) => claim.status));
    nested.push(...model.claims.flatMap((claim) => claim.evidence.map((evidence) => evidence.status)));
    nested.push(...model.actions.map((action) => action.availability));
  }
  return [...model.statuses, ...nested];
}

export function assertStudioViewModel(model: StudioViewModel): void {
  if (model.contract_version !== STUDIO_VIEW_MODEL_VERSION) {
    throw new Error("STUDIO_VIEW_MODEL_VERSION_INVALID");
  }
  assertText(model.title, "title");
  assertText(model.dominant_task, "dominant_task");
  for (const status of collectStatuses(model)) assertSourceBoundStatus(status);
  if (model.workspace === "verify") {
    const domains = new Set(model.actions.map((action) => action.domain));
    if (!domains.has("analysis") || !domains.has("review")) {
      throw new Error("STUDIO_VERIFY_ACTION_DOMAINS_REQUIRED");
    }
    if (model.fixture_only && model.actions.some((action) => action.enabled)) {
      throw new Error("STUDIO_FIXTURE_MUTATION_ACTION_FORBIDDEN");
    }
  }
}

export function fixtureOptInEnabled(value: string | boolean | undefined): boolean {
  return value === true || value === "1" || value === "true";
}

export function resolveStudioViewModel(
  fixture: StudioViewModel,
  options: { allow_fixture: boolean },
): StudioViewModel | StudioUnavailableViewModel {
  assertStudioViewModel(fixture);
  if (!fixture.fixture_only || options.allow_fixture) return fixture;
  return {
    contract_version: STUDIO_VIEW_MODEL_VERSION,
    workspace: fixture.workspace,
    title: fixture.title,
    dominant_task: fixture.dominant_task,
    fixture_only: false,
    unavailable: true,
    statuses: [
      {
        id: `studio-${fixture.workspace}-source`,
        label: "Fonte privata Studio non configurata",
        source_kind: "runtime_config",
        source_ref: "env:DICHIARAZIONI_PUBBLICHE_STUDIO_FIXTURE_ONLY",
        query_state: "blocked",
        blocker_code: "STUDIO_PRIVATE_SOURCE_REQUIRED",
      },
    ],
  };
}

export function isStudioUnavailable(
  model: StudioViewModel | StudioUnavailableViewModel,
): model is StudioUnavailableViewModel {
  return "unavailable" in model && model.unavailable === true;
}
