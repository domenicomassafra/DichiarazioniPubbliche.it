export type AssessmentCode =
  | "SUPPORTED"
  | "FACTUALLY_FALSE"
  | "OUTDATED_DATA"
  | "INSUFFICIENT_EVIDENCE"
  | "UNRESOLVED";

export interface PublicEvidence {
  id: string;
  url: string;
  publisher: string;
  source_type: string;
  publication_date?: string | null;
  observed_at?: string | null;
  content_sha256?: string | null;
  reference_period?: string | null;
  rights_status?: string | null;
  relation?: string | null;
}

export interface PublicDossier {
  finding_id: string;
  claim_id: string;
  claim: string;
  claim_type:
    | "ARITHMETIC"
    | "CAUSAL_CLAIM"
    | "CURRENT_FOREIGN_POLICY"
    | "CURRENT_POLICY"
    | "CURRENT_POLICY_POSITION"
    | "DISTRIBUTIONAL_CLAIM"
    | "ELECTION_PREDICTION"
    | "FISCAL_INFERENCE"
    | "GROUP_MOTIVE"
    | "HISTORICAL_ATTRIBUTION"
    | "HISTORICAL_CLAIM"
    | "HISTORICAL_POLITICAL"
    | "LEGAL_POLICY_STATUS"
    | "LEGAL_QUOTE"
    | "MOTIVE_ATTRIBUTION"
    | "NUMERIC_STATISTIC"
    | "POLICY_DIFFERENCE"
    | "POLICY_SCOPE"
    | "POLITICAL_ATTRIBUTION"
    | "PRICE_STATISTIC"
    | "QUOTE_ATTRIBUTION"
    | "RHETORICAL_GENERALIZATION"
    | "SYSTEMIC_CLAIM"
    | "SYSTEMIC_INFERENCE"
    | "TAX_RATE"
    | "VALUE_JUDGMENT";
  speaker: {
    id: string;
    name: string;
    public_role?: string | null;
    public_roles?: Array<{
      organization_id: string;
      organization_name?: string | null;
      role: string;
      start_date?: string | null;
      end_date?: string | null;
      review_event_ids: string[];
    }>;
    provenance?: Array<Record<string, unknown>>;
  };
  source: {
    content_id: string;
    url: string;
    title: string;
    published_at?: string | null;
    segments?: Array<{
      segment_id: string;
      segment_index: number;
      start_ms?: number | null;
      end_ms?: number | null;
    }>;
    text_provenance?: Array<{
      id: string;
      selector_type: "TEXT_QUOTE_HASH" | "TEXT_POSITION_HASH";
      quote_sha256: string;
      source_sha256?: string | null;
      start_char?: number | null;
      end_char?: number | null;
      attribution_method: string;
      attribution_version: string;
      review_event_ids: string[];
    }>;
  };
  finding: {
    assessment: AssessmentCode;
    publication_status: string;
    rationale: string;
    policy_version?: string | null;
    verification_run_id?: string | null;
    created_at?: string | null;
    published_at?: string | null;
    supersedes_id?: string | null;
  };
  evidence: PublicEvidence[];
  corrections: Array<Record<string, unknown>>;
  rights_of_reply: Array<Record<string, unknown>>;
  relations?: Array<{
    id: string;
    relation_type: string;
    relation_version: string;
    status: "APPROVED";
    role: string;
    related_claim_id: string;
    related_claim: string;
    related_statement_date?: string | null;
    rationale_codes: string[];
    review_event_id: string;
  }>;
}

export interface PublicProjection {
  schema_version: "dichiarazioni-pubbliche-public-v2";
  generated_at: string;
  dataset_sha256: string;
  methodology: {
    claim_level_only: boolean;
    aggregate_person_score: boolean;
    requires_publication_gate: boolean;
    requires_approved_evidence: boolean;
    requires_resolved_transcript: boolean;
  };
  dossier_count: number;
  omitted_count: number;
  dossiers: PublicDossier[];
}

export interface ContentAuditMoment {
  id: string;
  timestamp: string;
  seconds: number;
  claim: string;
  assessment: AssessmentCode;
  summary: string;
  sources: Array<{ publisher: string; label: string }>;
}

export interface ContentAuditFixture {
  slug: string;
  title: string;
  source: string;
  date: string;
  duration: string;
  description: string;
  moments: ContentAuditMoment[];
}
