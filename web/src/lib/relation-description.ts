/** Human-readable descriptions of reviewed public relations, without inference. */
export interface ReviewedRelationDescriptionInput {
  relationType: string;
  rationaleCodes: readonly string[];
  participantPersonIds: readonly string[];
}

export interface ReviewedRelationDescription {
  label: string;
  copy: string;
}

const generic: ReviewedRelationDescription = {
  label: "Relazione revisionata",
  copy: "Le dichiarazioni sono collegate da una relazione approvata. Il rapporto descrive testi, fonti e tempo senza attribuire intenzioni."
};

/**
 * No textual comparison, semantic similarity or opposite stance is inferred
 * in the public reader. An agreement/divergence needs an explicit reviewed
 * rationale and distinct identities; conflicting rationale falls back to an
 * unqualified description. This function grants no publication eligibility.
 */
export function describeReviewedRelation(input: ReviewedRelationDescriptionInput): ReviewedRelationDescription {
  const ids = input.participantPersonIds;
  if (ids.length !== 2 || ids.some((value) => typeof value !== "string" || !value.trim())) return generic;
  const crossPerson = ids[0] !== ids[1];
  const codes = new Set(input.rationaleCodes);
  const agreement = codes.has("CROSS_PERSON_AGREEMENT_REVIEWED");
  const divergence = codes.has("CROSS_PERSON_DIVERGENCE_REVIEWED");

  if (crossPerson && input.relationType === "SAME_PROPOSITION" && agreement !== divergence) {
    if (agreement) return {
      label: "Accordo tra persone",
      copy: "La relazione approvata registra due posizioni concordi sulla stessa proposizione e nel medesimo perimetro. Le fonti e gli esiti restano distinti."
    };
    return {
      label: "Divergenza tra persone",
      copy: "La relazione approvata registra posizioni differenti sulla stessa proposizione e nel medesimo perimetro. Non determina chi abbia ragione né attribuisce intenzioni."
    };
  }
  if (crossPerson && (agreement || divergence)) return generic;
  if (input.relationType === "SAME_PROPOSITION") return {
    label: "Stessa proposizione",
    copy: "Le dichiarazioni sono state collegate come formulazioni della stessa proposizione nel perimetro revisionato."
  };
  if (input.relationType === "POSITION_CHANGE_CANDIDATE" && !crossPerson) return {
    label: "Cambiamento di posizione revisionato",
    copy: "La relazione approvata segnala un cambiamento di posizione nel tempo della stessa persona, senza attribuire intenzioni."
  };
  if (input.relationType === "CONTRADICTION_CANDIDATE" && !crossPerson) return {
    label: "Contraddizione revisionata",
    copy: "La relazione approvata segnala dichiarazioni non allineate della stessa persona nel perimetro revisionato, senza attribuire intenzioni."
  };
  if (input.relationType === "CLARIFICATION" && !crossPerson) return {
    label: "Chiarimento",
    copy: "La relazione revisionata segnala un chiarimento successivo della stessa persona. Il rapporto descrive testi e tempo."
  };
  if (input.relationType === "UPDATE") return {
    label: "Aggiornamento",
    copy: "La relazione revisionata segnala un aggiornamento. Ogni dichiarazione conserva il proprio esito e la propria fonte."
  };
  return generic;
}
