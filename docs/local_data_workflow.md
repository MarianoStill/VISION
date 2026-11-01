# Local LION and PROOF workflow

## Scope

This is a local development path using the received LION and PROOF source copies. It does not connect to SAP, Azure, or production. LION's identity with Azure remains unverified. No commercial-priority calculation is included.

The current source entry paths were traced as:

- LION: `app.py` imports `logic.lion_v03.load_model`; that wrapper imports `lion_sap_engine.load_model`. The current query path uses `services.search.search`. `lion_sap_engine.load_model` executes the received classification, operational-urgency, and color-assignment calculations.
- PROOF: `app.py` constructs `proof.Engine`; `add_observation` calls `read_memberships`, which classifies `Data`/`Base` snapshots through `classification_engine.classification_records`. This local workflow invokes `add_observation` only. It does not call `rebuild`, so one file creates no transitions, durations, or reconstructed history.
- VISION: `development_app.py` calls `vision.lion_adapter` for LION and public `proof` services for PROOF. It does not import either module's internal calculation files.

## Source provenance

The migrated source files are copies, with the PROOF engine's import changed to be package-relative. Hashes below identify the received originals:

| Module | Received file | SHA-256 |
| --- | --- | --- |
| LION processing, classification, urgency | `lion_sap_engine.py` | `705CB8DDC67EF9843721E2C8B7A2347898F1F7BBC5465D573D35983410B54DBE` |
| LION search | `services/search.py` | `4A47E56C22903D5E368047C0ED90169B8EF8158ED39337BB1B1EAFE43CA59817` |
| PROOF snapshot classification | `classification_engine.py` | `D6F308C835E8921F46EAF020C2908B78EF1340C72600F0969D39D2B9A0A6282C` |
| PROOF observation storage and history engine | `proof.py` | `2A77FCEC37B90B6EF182BD0BB1F9C1A753F719644BC84F6DD9AEC1457AF5FD98` |

LION's implementation forms an existing internal group identifier from sales document plus serial when present, and uses the source row when serial is absent. PROOF uses the sales document for snapshot memberships. This is preserved per module, not promoted to a shared business key. Resolving their identity and classification differences remains a business decision.

## Processing and storage

1. VISION accepts one XLSX upload, reads its bytes in memory, and requires an explicit observation date for files not found in the configured reference.
2. LION writes those bytes to a temporary file, invokes the received loader with the explicit date, and removes the temporary file when processing ends. This path does not use file modification time as the observation date.
3. PROOF compares the exact content fingerprint against `CO_VISION_PROOF_REFERENCE_DB`, when configured. That SQLite database is opened read-only. A match is reported as already present and is not copied into DEV.
4. If the input is not in the reference, PROOF stores one observation in the DEV database. Its default is `%LOCALAPPDATA%\CO-VISION\DEV\proof.sqlite3`, overridable with `CO_VISION_PROOF_DEV_DB`. PROOF stores the source workbook and classification records as the received Engine does. Keep this database outside Git and separate from the reference or production.
5. The one-file upload path does not rebuild events or claim historical evolution for a new observation.

## Functional development views

- LION results preserve the received classification and urgency. The screen provides global and field-specific search, a detailed selected-result view, the received stage sequence, and the original source rows for diagnosis. The timeline's 0/50/100 values are stage-sequence display values, not elapsed-time measurements.
- PROOF's configured reference is read without writes. The screen presents its stored observations, memberships, events, instances, temporal inventory, and completion/time query. It does not infer movements between stored observations.
- PROOF's metadata and exact serial/purchase searches index stored workbooks only when requested. Filters can scope the temporal PROOF summaries, inventory, and completion query; serial and purchase identifiers find sales documents but do not change PROOF's sales-document history grain.
- The combined machine view uses an exact sales-document match only when that order maps to one LION result and has PROOF records. An ambiguous or missing relation is shown as unlinked with a reason.
- LION urgency and PROOF delay metrics are displayed separately. VISION does not calculate a commercial priority.

## Environment and checks

- Runtime used: CPython 3.14.10 x64, pandas 2.3.3, openpyxl 3.1.5, Streamlit 1.66.1, pytest 9.1.1.
- pandas/openpyxl/Streamlit remain optional extras. Ordinary `import lion` and `import proof` do not load those dependencies; workbook services require their extras.
- Tests in `tests/regression/` compare received sources and, when explicitly configured, the received workbook. They are separate from the source-independent product tests and do not print workbook rows or identifiers.
- Source-equivalence and received-workbook checks are optional and run only when their paths are explicitly configured. They do not establish business correctness or Azure identity.
- Existing LION timedelta expressions are preserved; no business behavior was changed to silence their NumPy deprecation warning.

Latest self-contained check results:

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Complete product check, no external paths | 67 | 0 | 26 |

The 26 skipped tests require optional external source paths or operational inputs. They were not configured for this check, and skipped tests are not validations.

The project requires Python 3.13 or newer. The validated cloud runtime is Python 3.14. Create the virtual environment and install the documented extras from the repository root.

### Windows (PowerShell)

```powershell
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[test,vision,lion,proof]"
.\.venv\Scripts\python.exe scripts\check.py
```

### Linux (including GitHub cloud agents)

```bash
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -e ".[test,vision,lion,proof]"
.venv/bin/python scripts/check.py
```

Optionally configure the isolated reference copy, then start Streamlit only on loopback:

```powershell
$env:CO_VISION_PROOF_REFERENCE_DB = "<path-to-read-only-history-copy>"
.\.venv\Scripts\python.exe -m streamlit run apps\vision\src\vision\development_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
```

Open `http://127.0.0.1:8503` on the same computer. Do not use `0.0.0.0`; this development screen is not intended to be network-exposed.

## Limits

- The comparison is against the received local copies; Azure's deployed files remain unverified.
- CPython 3.14.10 execution does not establish compatibility with LION's Python 3.12 Azure runtime.
- Source equivalence does not validate the business meaning or approval of either module's rules.
- A single snapshot does not prove stage transitions, duration, or machine evolution.
- No SAP mapping contract, identity reconciliation, TEST/PROD configuration, or production deployment is implemented.
