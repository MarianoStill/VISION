# Testing and CI

All commands use the project interpreter (`.venv`); never an interpreter from another checkout.

## Setup (Windows)

```powershell
uv python install 3.14
uv venv --python 3.14 .venv
uv sync --locked --all-extras
.\.venv\Scripts\python.exe -m playwright install chromium
```

Use the single local validation command after browser installation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

Verify that imports resolve to this checkout:

```powershell
.\.venv\Scripts\python.exe -c "import covision, lion, proof, vision; print(covision.__file__, lion.__file__, proof.__file__, vision.__file__)"
```

## Test suites

| Command | Scope |
| --- | --- |
| `python scripts/check.py` | Canonical check (pytest + module entry points) |
| `python -m pytest` | Unit, integration, regression (default `testpaths`) |
| `python -m pytest tests/e2e` | Playwright UI tests: O2C, Commercial, Manager, Administrator |
| `python scripts/regression_compare.py baseline.xml candidate.xml` | Differential comparison of two JUnit reports |

The UI tests start Streamlit on `127.0.0.1` with a synthetic data root (`tests/e2e/seed.py`). They never read real SAP data, need no Microsoft SSO, and the data lives in a temporary directory.

## Skipped tests

26 tests in `tests/regression/` are skipped unless the received original sources are available. They compare the migrated modules with those sources and cannot be replaced by synthetic fixtures without losing their purpose:

- `CO_VISION_LION_SOURCE_DIR`: received LION sources.
- `CO_VISION_PROOF_SOURCE_DIR`: received PROOF sources.
- One test also needs a workbook, a reference database and an observation date (see the skip message).

They are not run in GitHub Actions because those sources and the corporate data must not be committed.

## Differential regression

CI runs the suite on the branch and on `origin/main`, then `scripts/regression_compare.py` classifies each test (PASS→FAIL regression, FAIL→PASS fixed, FAIL→FAIL with same or changed signature, new, removed, PASS→SKIP). It exits 1 on a regression, a changed failure signature, a removed or newly skipped passing test, or a collection error. Only test ids and hashed failure signatures are reported, never data.

## CI

`.github/workflows/validation.yml` runs on every push, on pull requests to `main`, and manually: `check` (imports, Ruff on touched application/test surfaces, pip-audit, canonical check, JUnit and coverage), `regression-vs-main`, and `e2e` (Playwright). JUnit and coverage XML/HTML reports are uploaded as artifacts. The current report measures 58% overall; Streamlit's `AppTest` executes `development_app.py` in its script runner, which coverage.py does not currently trace (the module appears as 0%), while browser and functional assertions independently exercise its flows. Treat this as a coverage instrumentation gap, not evidence that the UI is untested.

`uv.lock` is the generated, cross-platform lock for all extras. `requirements-dev.lock` was removed because it contained only the minimal pytest environment and did not lock application, browser-test, or quality-tool dependencies.
