# ADR 0003 — Non-biometric speaker attribution

Status: Accepted  
Date: 2026-09-22

## Context

Claims must be attributable to a speaker, but biometric identity systems create privacy,
legal, security, and false-positive risks unnecessary for the product's core value.

## Decision

Speaker attribution uses bounded non-biometric provenance such as source metadata,
platform credits, transcript labels, official records, and explicit review. Face
recognition, voiceprints, and biometric matching are out of scope.

## Consequences

- Some content remains unpublished when attribution cannot be established safely.
- Diarization may separate speakers but cannot itself establish real-world identity.
