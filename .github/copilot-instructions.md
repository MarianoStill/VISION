# Instructions for GitHub Copilot

## Persistent work mode

The active work mode is recorded in `config/active_mode.json`. Recognize the exact commands `SWITCH DAY`, `SWITCH NIGHT`, and `STATUS`. Follow `docs/agent_modes/README.md` as the single source of truth; do not duplicate its mode rules here. The current mode is DAY.

## Product architecture

CO-VISION is one product in one repository, composed of independently developable, testable, and maintainable modules:

- `modules/proof/` (PROOF) is the proposed owner of SAP data ingestion and normalization, stage classification, historical reconstruction, stage transitions, machine evolution over time, and evidence explaining each classification. Classification ownership is not validated until existing code and approved rules are reviewed.
- `modules/lion/` (LION) owns current operational status, operational urgency, delay signals, operational metrics, and operational filters and queries. Its dependency on PROOF classification outputs is proposed and must be validated before any migration.
- `apps/vision/` (VISION) is proposed to consume PROOF and LION and owns the user experience: machine search, cards and details, timelines, profile views, filters, requests, notes, replies, escalations, and commercial priority.
- `shared/` is for explicitly agreed shared models, identifiers, contracts, constants, and validation. It must not become a place to hide duplicated business rules.

The modules must work together when CO-VISION runs, while remaining separately testable and maintainable. See `docs/architecture.md` for the initial boundaries.

## Single source of truth

- Every business rule has exactly one owning module.
- The received LION and PROOF classification code has been migrated as separate source-copy behavior. Do not reconcile, replace, or extend those rule sets until their owner and differences are confirmed against approved requirements.
- Once ownership is validated, the owning module is the sole source of truth; consumers use its outputs instead of reproducing its rules.
- VISION must consume PROOF and LION outputs and must not duplicate their rules.
- When an owning rule changes, downstream modules should consume the changed output through the established contract; do not copy the change into consumers.
- Operational urgency belongs to LION. Commercial priority belongs to VISION. Never merge or substitute one for the other.

## Business and data constraints

- Do not invent business rules, stages, SAP columns, data fields, or machine identifiers.
- The known progressive business identifiers are the sales document/order, the purchasing document (available when factory work begins), and the serial/chassis number (available after the machine is created). Do not introduce a substitute business key.
- Treat all unspecified schemas, mappings, lifecycle details, and business behavior as undecided. Record open questions rather than filling gaps with assumptions.
- Do not add synthetic data that could be mistaken for real business data.

## Environments and releases

- Keep DEV, TEST, and PROD concerns separate. TEST and PROD must be able to use separate configuration and storage.
- The intended flow is change in DEV, automated tests, deployment to TEST, human approval, then promotion to PROD.
- PROD must never receive experimental changes directly. Do not modify production directly or configure production as part of the initial scaffold.
- The exact version validated in TEST must be the version promoted to PROD. Preserve the ability to roll back to the previous version.
- Never commit credentials, secrets, SAP data, or corporate data. No remote repository has been authorized or configured.

## Changes and tests

- Work in the module that owns the requested behavior. Update its contract and relevant consumers rather than duplicating rules.
- Keep module boundaries explicit and changes focused. Do not implement application or business behavior unless requested and supported by approved requirements.
- Add or update focused tests for code changes, then run the relevant automated tests before reporting completion. Do not claim tests passed unless they were run.
- Before a test framework or build workflow is selected, do not assume a language, framework, package manager, or CI implementation.
- Technical availability messages are not business readiness or business results.

## Current local migration boundary

- The received LION processing, search, filters, and stage-progress behavior are under `modules/lion/`; the source-copy LION identity with Azure remains unverified. Do not describe this migration as production-equivalent.
- The received PROOF classifier and Engine are under `modules/proof/`. Its public services expose the read-only history, filters, temporal inventory, operational summaries, and completion query used by the local development screen.
- `apps/vision/` calls public module services through `vision.lion_adapter` and `proof`; it must not import internal calculation modules.
- The received LION and PROOF classifiers differ. Preserve each received behavior and do not reconcile or duplicate either rule set without an explicit business decision.
- The local Excel workflow requires an explicit observation date unless its content fingerprint matches the configured read-only history reference. Keep the reference and DEV storage separate and outside Git.
- The local VISION screen is a development prototype. Run it on loopback only. No Azure, production, TEST infrastructure, or commercial-priority logic is configured.
- Run focused tests and `scripts/check.py`; run optional source-equivalence checks only when their source paths are explicitly configured. Do not expose workbook cells, identifiers, database contents, or input-file hashes in test output.
