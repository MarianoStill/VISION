# LION and PROOF capability inventory

This inventory compares the local CO-VISION development experience with the active application paths in the received source copies. It describes technical coverage, not business approval, Azure identity, or production readiness. Workbook and SQLite contents remain outside Git.

## Implemented in CO-VISION

| Capability | Local implementation |
| --- | --- |
| LION workbook processing | `lion_adapter.process_workbook` delegates to the public LION service and retains the received classification, grouping, urgency, evidence, and warnings. |
| LION simultaneous stages and process timeline | `lion.stage_progress`, consumed through `lion_adapter`, presents the received stage sequence and progress values. It does not calculate elapsed time. |
| LION search and filters | Global and exact/partial search plus Comercial, Cliente, Pedido, Máquina, and explicit Chasis/Bastidor filters. A serial number is not substituted for Chasis. |
| LION machine detail | The selected result shows existing progressive identifiers, stage(s), operational urgency and its source fields, sales and delivery information, evidence, warnings, ambiguous source relationships, and the original XLSX rows in a diagnostic section. |
| PROOF observations and history | The local screen reads stored observations, memberships, events, and instances. A single observation remains a single observation; missing observations are not presented as transitions. |
| PROOF identifier and metadata queries | Delegación, Comercial, and Cliente filters, with exact serial or purchase-document lookup against stored XLSX sources. Matching results remain separate by Documento de ventas. |
| PROOF follow-up and delay view | Public PROOF service summarizes open standard-stage instances and exposes the received stage thresholds and detail rows. Results remain independent of LION urgency. |
| PROOF temporal inventory | The existing inventory projection is consumed through `proof.project_inventory` with the received date range and day/week/month aggregation. |
| PROOF completion/time query | The received completion query is available on demand. Its complete result for the provided history copy matched the isolated received implementation, including all aggregate fields and detail rows. |
| LION-to-PROOF side-by-side context | A selected LION result is linked only by exact Documento de ventas when that order has one LION result and PROOF has records. Otherwise the screen explains why it is unlinked. |
| Read-only reference use | The configured PROOF history is opened read-only; index preparation reads one saved XLSX at a time and keeps its derived index in the current session. DEV observation storage remains separate. |

## Pending

- The LION files received locally have not been proven byte-identical to the Azure deployment. The Azure Python 3.12 runtime has not been checked for compatibility with this project's Python 3.14.10.
- LION and PROOF retain independent classification and identity behavior. No shared classification contract or business reconciliation has been approved.
- PROOF history is keyed by Documento de ventas. If multiple LION results share that order, its events and durations cannot be attributed to one physical machine. Serial/purchase lookup finds relevant orders but does not split order-level history.
- The user has not yet reviewed this expanded local screen. Its technical behavior is not business validation or production approval.
- `flow_model.py`, its cohorts, and its metrics remain inactive as explicitly decided. The active received dashboard imports `project` and `aggregate` but does not invoke them.
- TEST/PROD configuration, separate storage, human approval, release promotion, rollback, and deployment are not configured.

## Discarded intentionally from this development delivery

- Connecting to SAP, Azure, production storage, or deployed services.
- PROOF load-management actions that add batches, replace/change/delete observations, change dates, rebuild rules, or create backups against received storage. The local screen only reads the configured reference; uploads go through the separate DEV path.
- VISION profiles, requests, notes, responses, escalations, commercial priority, executive dashboards, and the definitive UI design.
- Reconciliation of LION urgency with PROOF delay metrics or invention of a replacement machine key.

## Not used by the active received applications

- PROOF `flow_model.project` and `flow_model.aggregate`: imported by `dashboard_filters_flow.py`, not called by the active route. Their migration and behavior remain deferred.
- PROOF load-management operations: implemented in `load_management.py` but not called by the active `app.py` dashboard route.
- PROOF special-category cards: the received dashboard renders static “No disponible” placeholders for the listed categories; it supplies no underlying classification or metric for them.

## Received-source evidence

Hashes identify these local reference files only; they do not identify Azure-deployed files.

| Application area | Received reference file | SHA-256 |
| --- | --- | --- |
| LION stage labels and timeline | `LION/lion_v05_ui.py` | `0ED59EDEDCCB60EF9A38B854D0228C3F8A2FC95E4C6C8701ED49133D8A7F036C` |
| PROOF dashboard metrics and attention view | `PROOF/dashboard.py` | `A1F36388ABC947653D0DFCB8B44DF75BC0AE108440BC1E12BC6E1DCC4EF99490` |
| PROOF filters and index behavior | `PROOF/dashboard_filters_flow.py` | `EBA6E3486B2E04CBD0253D3D9A57A9BAF9AAA01D6AD7AD9AC00D863E96477B6E` |
| PROOF completion query | `PROOF/completion_metrics.py` | `237BDA0B6D9AE014C96BB1F917C8AFCD2B6511F089D2BAEEF5220DF7D132D44D` |
| PROOF temporal inventory | `PROOF/inventory_chart.py` | `74FC04B32D95C31411C4F2E5A495315655F0C98EFAC5C3109FCD74724724BA8F` |
| PROOF application route | `PROOF/app.py` | `B3738A072AE4C6097D2A4244CA554ECF3AF19DDD30579F68D95881722D628C75` |
