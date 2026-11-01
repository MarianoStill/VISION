# Technical decisions

## Runtime

- Selected CPython 3.14.10 x64, a stable maintenance release supported by the selected pytest version. Python 3.13.17 had been superseded by 3.13.18, which had no Windows installer, so 3.14.10 was selected instead.
- Installed from the official Python.org Windows installer for the current user at `%LOCALAPPDATA%\Programs\Python\Python314`. The installer SHA-256 was checked against the official release page. The installation did not add Python to PATH or change global Git configuration.
- `.venv` is created inside the repository and is excluded by `.gitignore`.

## Python packaging and tests

- Use a single root `pyproject.toml` and setuptools editable installation for the module packages. This keeps each package in its existing product area while allowing imports from the project virtual environment.
- Pin setuptools and pytest in project metadata. Record the resolved environment in `requirements-dev.lock` for repeatable local setup.
- Use pytest for technical and characterization checks. Streamlit 1.66.1 is an optional dependency for the local VISION development screen only; it is installed in `.venv` and does not add database or deployment infrastructure.
- `scripts/check.py` is the single local technical check command and requires the project virtual environment interpreter.

## Module loading

- PROOF, LION, and VISION are separate importable Python packages with technical availability entry points.
- VISION's integration entry point imports PROOF and LION. The verified integration tests exercise independent imports and multiple import orders to detect circular imports in those paths.
- The shared status string is technical scaffolding only; it is not a business result, rule, data contract, or readiness claim about business functionality.

## Business ownership and scope

- Existing classification-rule ownership is not validated. The repository contains only the prior scaffold and no business implementation or approved classification rules to inspect.
- No classification code is migrated or implemented. The proposed architecture alone is not used as proof of the existing owner.
- No SAP schema, definitive inter-module data contract, sample business data, database, or UI framework is introduced.
- DEV, TEST, and PROD remain future environments; no deployment or remote repository is configured.

## PROOF inventory projection

- The first PROOF migration preserves the inventory projection used by the received copy: isolate `period_key` and `chart_rows` from `inventory_chart.py` into `modules/proof/src/proof/inventory_projection.py`.
- Keep `flow_model.py` and its characterization tests untouched and inactive. Its cohort/flow metrics are a future enhancement requiring business definition; do not treat them as current behavior.
- Keep the extracted component independent from Streamlit, Altair, Engine/storage, and VISION. Characterize it with synthetic fixtures and compare its output with the received source before wiring it into a UI.
- Preserve current filtering/counting semantics exactly. Tests establish technical equivalence for covered inputs, not approval of business criteria.
- Expose the projection through `proof.project_inventory(...)` as a thin public service that delegates to `inventory_projection.chart_rows`; do not duplicate calculations or add input validation that changes behavior.
- Keep product tests self-contained. Tests that compare with files in `CO-VISION-inputs` belong under `tests/regression` and may be skipped when the external source path is not configured.
- Use Streamlit 1.66.1 as an optional VISION-only dependency for the first local development screen; pin it in `pyproject.toml` and install it only in `.venv`. Bind the local server to `127.0.0.1`.

## LION delivery predicate

- Migrate only the pure `is_delivered` predicate from the received `lion_sap_engine.py`; keep `assign_colors` and urgency calculations out of scope.
- Preserve the exact delimiter and case-sensitive matching behavior. Expose it as a public `lion.is_delivered` service and have `vision.lion_adapter` delegate without interpretation.
- Keep source comparisons optional and isolated: parse the received file and execute only the AST definition of `is_delivered`, never import the full LION engine for this check.

## Local workbook workflow

- After explicit authorization to continue the local delivery, migrate the active received LION path (`logic.lion_v03.load_model` → `lion_sap_engine.load_model`) and its search helper. Preserve its current behavior, including classification, operational urgency, and color assignment; use a caller-supplied observation date rather than a temporary-file modification time.
- Migrate the received PROOF snapshot classifier and Engine into the product package. The local VISION workflow stores an observation in a separate DEV database only when its content is not already present in the configured read-only reference. It does not call `rebuild` for one-file input, so it creates no inferred history.
- Keep LION's and PROOF's observed classifications separate until their differences and ownership are explicitly resolved. Do not create a shared identity key or treat LION urgency as VISION commercial priority.
- Keep pandas/openpyxl/Streamlit as optional extras; ordinary package availability imports stay independent of these dependencies.
- The default DEV SQLite location is outside the repository. The reference path is supplied through `CO_VISION_PROOF_REFERENCE_DB`; code contains no personal source-input path. No Azure, TEST, or PROD configuration is added.
