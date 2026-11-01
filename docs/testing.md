# Testing and CI

All commands use the project interpreter (`.venv`); never an interpreter from another checkout.

## Setup (Windows)

```powershell
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[test,vision,lion,proof,e2e]"
.\.venv\Scripts\python.exe -m playwright install chromium
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

`.github/workflows/validation.yml` runs on every push, on pull requests to `main`, and manually: `check` (imports, canonical check, JUnit), `regression-vs-main`, and `e2e` (Playwright). Artifacts contain JUnit XML only.
