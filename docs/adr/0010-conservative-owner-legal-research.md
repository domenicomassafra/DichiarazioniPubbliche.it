# ADR 0010 — Owner-delegated conservative legal research dispositions

Status: Accepted (product risk controls only)
Date: 2026-10-20
Scope: Italy/EU; no source-specific release authorization
Authority: [owner direction, issue #55, 20 October 2026](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/55#issuecomment-6287288216)

## Context

DP-306/307 previously required an outside qualified legal reviewer. The owner now directs the project to undertake primary-source legal research and select the safest documented product option where the law or deployment facts do not give a determinate answer. The original register has 16 launch-sensitive questions. Public statements, private data, copyright and rights of reply have distinct eligibility requirements. Publishing a researched decision must not silently unlock a surface.

## Decision

1. The dated, question-by-question [research decisions](../policy/legal-research-decisions-2026-10-20.md) guide conservative product design. They separate what a primary legal text says from the project's interpretation, conditions and residual risk.
2. External counsel is no longer a mandatory project staffing prerequisite under the owner's current instruction. No agent or automated test is represented as professionally qualified counsel or as capable of certifying compliance.
3. Maintain individual case/source rights receipts, documented human editorial decisions, privacy purpose/basis and rights workflows. Open or unimplemented surface conditions still block release. A policy default is not a licence, retention approval or content-specific publication event.
4. Preserve the DP-306 register's OPEN/BLOCKED statuses and the existing release NO-GO until operational evidence exists. Any status promotion to DECIDED requires explicit owner acceptance of a dated, bounded disposition and satisfaction of the associated release conditions. The owner's general staffing decision does not accept each concrete publication risk.
5. Material changes to source family, licence, data class, role, jurisdiction, hosting, account/intake, public AI, wording or privacy practices reopen the affected determination. Reassess before real launch.

## Consequences

The historical mandatory-external-counsel premise in DP-307 is superseded by the owner direction, while fail-closed safeguards remain. Technical tickets #54, #61, #78, #80, #81 and #82 require their independent acceptance evidence; a legal research PR cannot close those engineering obligations. Release decisions require a separate actual owner acceptance and operational readback.

## Alternatives considered

- Treating public availability or attribution as automatic legal permission: rejected; rights and privacy are independent.
- Setting a global excerpt length, legal retention term or automatic DSA exemption: rejected; the official rules and deployment facts do not establish those universal answers.
- Declaring all 16 questions DECIDED when the research is written: rejected; it would cause the current launch preflight to mistake research for acceptance of all real production conditions.
