# CO-VISION

CO-VISION is one product composed of three independently maintainable modules:

- **PROOF** is the proposed owner of SAP data ingestion and normalization, stage classification, historical reconstruction, transitions, machine evolution, and classification evidence. Classification ownership remains to be validated against approved rules and existing implementations before any migration or business logic is added.
- **LION** owns operational status, operational urgency, delay signals, operational metrics, and operational queries. Its dependency on process/history outputs is subject to the classification-ownership and contract validation described above.
- **VISION** is the user-facing application. It consumes PROOF and LION and owns the user experience, requests and communications, and commercial priority.

The modules are designed to be developed and tested separately and integrated when CO-VISION runs. A business rule has one owner; consumers use that owner's outputs instead of reimplementing its logic. Operational urgency and commercial priority are distinct concepts.

The local development workflow migrates the received copies of LION and PROOF. It is not a production release: LION's identity with Azure is unverified, business rules are not approved, and there is no SAP connection. See [docs/local_data_workflow.md](docs/local_data_workflow.md).

See [docs/architecture.md](docs/architecture.md), [docs/testing.md](docs/testing.md) (tests, UI automation, skips, CI), [docs/business_rules.md](docs/business_rules.md), [docs/data_contract.md](docs/data_contract.md), and [docs/release_process.md](docs/release_process.md).

## Development environment and technical check

The project requires Python 3.13 or newer. Python 3.14 is used for cloud validation. Install `uv`, then create a project virtual environment and install all documented test and application extras.

### Windows (PowerShell)

```powershell
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[test,vision,lion,proof]"
```

Run the canonical check with the project interpreter:

```powershell
.\.venv\Scripts\python.exe scripts\check.py
```

### Linux (including GitHub Actions and cloud agents)

```bash
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -e ".[test,vision,lion,proof]"
.venv/bin/python scripts/check.py
```

The check verifies the project interpreter, the Python minimum declared in `pyproject.toml`, and required development dependencies before running the full pytest suite and the PROOF, LION, and VISION module entry points.

## VISION development MVP

VISION is a Spanish-language Streamlit development interface, not a production
application. Start it on loopback from the repository root:

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m streamlit run apps\vision\src\vision\development_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
```

### Linux and GitHub cloud

```bash
.venv/bin/python -m streamlit run apps/vision/src/vision/development_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
```

The initial **Demostración (DEMO)** mode is safe to review without operational
files or databases. Its visibly synthetic machine and PROOF projection are UI
fixtures only: they are not operational evidence and do not represent real
identifiers, customers, classifications, urgency, or history. The demo routes
search and stage presentation through the public VISION-to-LION adapter and
uses the public PROOF projection service.

Choose **Datos operacionales (DEV)** only to process an authorized local XLSX.
Select the file and its observation date; no SAP, TEST, or PROD connection is
configured. Optional environment variables are:

- `CO_VISION_PROOF_REFERENCE_DB`: isolated SQLite reference database, opened
  read-only. If the uploaded content matches a stored observation, its date is
  reused.
- `CO_VISION_PROOF_DEV_DB`: path for the separate DEV SQLite database. If unset,
  Windows uses `%LOCALAPPDATA%\CO-VISION\DEV\proof.sqlite3`; Linux uses
  `~/CO-VISION/DEV/proof.sqlite3`.

Neither variable is needed for DEMO. Keep uploaded workbooks, reference and DEV
databases, and their SQLite sidecar files outside the repository. There is no
authentication or role-based authorization in this prototype; organizational
roles remain undecided. Operational data and business rules have not been
validated for production.

The local data workflow uses the received code copies and one uploaded XLSX. It requires an explicit observation date for a new file. Set `CO_VISION_PROOF_REFERENCE_DB` to an isolated SQLite reference copy to detect an already registered file without writing to that reference. DEV storage defaults to `%LOCALAPPDATA%\CO-VISION\DEV\proof.sqlite3`, outside Git; `CO_VISION_PROOF_DEV_DB` overrides it.

Start the development screen only on loopback:

```powershell
.\.venv\Scripts\python.exe -m streamlit run apps\vision\src\vision\development_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
```

The screen keeps the synthetic projection demonstration and adds local XLSX processing. One PROOF upload records an observation only; it does not infer transitions or duration. Automated equivalence with the received source copies is not business approval or proof of Azure identity.
