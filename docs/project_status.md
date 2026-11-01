# Project status

## Persistent agent mode

- Active mode: `DAY`, recorded in `config/active_mode.json`. The mode commands and operating rules are defined in `docs/agent_modes/README.md`.

## Current local delivery

- The project is on `chore/technical-foundation`. The received source folders and operational files remain outside the repository; no Azure or production changes were made.
- LION now exposes the received workbook processing and search behavior through public services. VISION consumes them through `vision.lion_adapter`.
- PROOF now exposes the received snapshot classifier and observation storage. A new input is stored in a DEV SQLite database outside Git. The one-file path does not rebuild events or infer historical evolution.
- The local VISION screen retains the synthetic projection example and adds a local XLSX workflow. It separates LION operational urgency from commercial priority; no commercial priority is calculated.
- The user confirmed the workbook's observation date as `2026-10-26`. A read-only fingerprint check found the same content already registered in the isolated PROOF history copy for that date. Processing recognizes this duplicate rather than writing another copy.
- Source provenance, process details, and limitations are recorded in `docs/local_data_workflow.md`. Migrated-file hashes identify only the received local source copies; LION's match with Azure remains unverified.
- `flow_model.py` remains inactive. Its migration, cohorts, and metrics remain deferred. The isolated `inventory_chart.chart_rows` projection remains available through `proof.project_inventory`.
- The user reviewed the synthetic screen states on 2026-10-26. That bounded visual review is not business validation or production approval.

## Environment and validation

- `.venv` uses CPython 3.14.10 x64, pandas 2.3.3, openpyxl 3.1.5, Streamlit 1.66.1, and pytest 9.1.1. The interpreter was not changed.
- Optional workbook comparisons ran against the received source copies. The migrated LION and PROOF outputs matched for the same received workbook; its exact fingerprint was found in the read-only history copy.
- The source-independent tests use labelled synthetic workbooks. Source/data comparisons remain separate under `tests/regression`.
- LION emitted NumPy deprecation warnings from the received timedelta expressions during the real workbook comparison. They were preserved; this is a future dependency-compatibility risk, not a failing comparison.
- Latest complete technical check without external paths: 41 passed, 0 failed, 26 skipped; the skips require received sources or the received workbook/database. PROOF, LION, and integrated VISION entry points ran successfully.
- Complete technical check with both source folders: 65 passed, 0 failed, 2 skipped. The focused received-workbook equivalence and reference duplicate check separately passed 2 tests, 0 failed, 0 skipped. Source equivalence is not business approval.

## Pending decisions and work

- PROOF and LION contain differing stage-classification and identity behavior. The user decided to keep their outputs independent in DEV until the inter-module contract is agreed. This is an interim scope decision, not business validation or a resolution of classification ownership or identifier matching; the screen does not merge their outputs or invent a shared key.
- Azure shows Python 3.12 and `bash startup_lion.sh`; the received LION files have not been compared to deployed content. The portal's deployment identifier is not a verified Git commit.
- Python 3.14.10 execution does not establish compatibility with LION's Python 3.12 Azure runtime.
- PROOF history from one new file is not inferred. Existing transitions, cohort/flow behavior, and timeline semantics require confirmed rules and source contracts.
- SAP field mappings, progressive identifier matching, business approval, and the definitive VISION design remain pending.
- DEV processing is local only. TEST and PROD storage, release promotion, approval, rollback, and deployment infrastructure are not configured.

## Safeguards

- No original input/source file was modified.
- Excel and SQLite files are excluded from Git. The optional reference path is configured with `CO_VISION_PROOF_REFERENCE_DB` and opened read-only; DEV uses a separate path.
- The local Streamlit screen must bind to `127.0.0.1`. No publish, merge, or Azure operation was performed.
