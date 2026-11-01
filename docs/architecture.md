# CO-VISION architecture

## Product boundary

CO-VISION is one product and one repository, organized as `apps/`, `modules/`, `shared/`, and `tests/`. PROOF, LION, and VISION have distinct ownership and can be developed and tested independently; the integrated product consumes their outputs together.

## Module responsibilities

| Component | Location | Owns | Depends on |
| --- | --- | --- | --- |
| PROOF | `modules/proof/` | Proposed responsibility: SAP ingestion and normalization; classification by stages; historical reconstruction; transitions; machine evolution; evidence for classifications | Shared contracts and approved source data definitions |
| LION | `modules/lion/` | Current operational situation; operational urgency; delay signals; operational metrics; operational filters and queries | Proposed dependency on approved process/history outputs and shared contracts; classification ownership and contract are not yet validated |
| VISION | `apps/vision/` | User interface; machine search, cards, details, and timeline; profile views and filters; requests, notes, replies, and escalations; commercial priority | Proposed PROOF and LION outputs and shared contracts; contracts remain to be validated |

The intended dependency direction is LION consuming PROOF and VISION consuming PROOF and LION. The current received LION and PROOF copies each contain classification logic with different behavior; ownership and a shared classification contract remain unresolved. The local workflow preserves each module's received result separately and does not reconcile them. It must not be treated as an approved integrated machine model. Once ownership is decided, consumers must use the owner's output rather than reimplement its rules. Shared code is limited to explicitly agreed structures and technical utilities, not duplicated policy.

## Current local implementation

- LION's public workbook service wraps the received engine and requires an explicit observation date. Public LION search, field filters, and stage-progress output are consumed through `vision.lion_adapter`. The Azure deployment has not been content-verified.
- PROOF exposes public services for snapshot classification/storage, read-only history, source-backed identifier filters, operational summaries, inventory, and completion/time queries. A newly uploaded single observation is not used to invent prior transitions.
- VISION's local development screen processes an uploaded XLSX without connecting to SAP or production, shows LION's selected result and its own timeline, and presents PROOF observations, history, and temporal queries separately. It can link the views only by an exact sales document when the order is unique in LION and has PROOF records.
- When order-level PROOF history cannot be attributed to one LION result, VISION leaves it unlinked and reports the reason. It does not create a shared business key or use serial/chassis as a substitute for PROOF's sales-document grain.
- The configured PROOF reference is opened read-only. New non-reference observations use the separate local DEV database. LION urgency and PROOF delay summaries remain separate; VISION does not calculate commercial priority.
- LION and PROOF receive the same uploaded bytes through their own received-source behavior. This preserves their independent outputs; it is not a decision that their classifications or identities are equivalent.

## Shared areas

- `shared/models/`: agreed cross-module model definitions; none have been decided yet.
- `shared/identifiers/`: agreed representation of the known progressive business identifiers; no replacement key may be introduced.
- `shared/contracts/`: versioned boundaries between modules; contract shapes are not yet specified.
- `shared/constants/` and `shared/validation/`: only values and validation rules with an agreed owner and purpose.

The three known machine identifiers become available progressively: sales document/order; purchasing document when factory work begins; and serial/chassis number after the machine is created. Their exact formats, SAP source fields, and matching behavior remain unspecified.

For each future contract, document its owner, consumers, versioning and compatibility policy, field definitions, lifecycle/availability, and validation behavior. This scaffold intentionally supplies no field list or payload example. Process/history and classification ownership must be confirmed before defining those contracts.

## Tests and integration

`tests/proof/`, `tests/lion/`, and `tests/vision/` contain module tests using synthetic inputs. `tests/integration/` covers package integration, and `tests/regression/` keeps source-copy and optional received-workbook comparisons separate. Equivalence proves only the tested outputs, not business approval or finalized contracts.

## Environments

Environment-specific configuration is separated under `config/base/`, `config/test/`, and `config/production/`. These remain placeholders. The local DEV database defaults outside the repository under `%LOCALAPPDATA%\CO-VISION\DEV`; a reference history path is configured separately and opened read-only. TEST and PROD are not configured and must use separate configuration and storage when approved. Do not put secrets or business data in the repository.
