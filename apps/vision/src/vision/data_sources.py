from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


DEFAULT_DATA_DIRECTORY = "CO-VISION-data"
DEFAULT_SAP_DAILY_RELATIVE_PATH = Path("sap") / "daily"
DEFAULT_PROOF_RELATIVE_PATH = Path("proof") / "proof.db"


def _configured_path(value: str, *, base: Path) -> Path:
    path = Path(value).expanduser()
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def resolve_external_sources(
    environ: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> dict[str, Path | None]:
    environment = os.environ if environ is None else environ
    home_directory = (home or Path.home()).expanduser().resolve()
    configured_root = environment.get("CO_VISION_DATA_ROOT")
    root = (
        _configured_path(configured_root, base=Path.cwd())
        if configured_root
        else home_directory / DEFAULT_DATA_DIRECTORY
    )

    proof_db = environment.get("CO_VISION_PROOF_DB")
    proof_reference_db = environment.get("CO_VISION_PROOF_REFERENCE_DB")

    proof_default = root / DEFAULT_PROOF_RELATIVE_PATH
    sqlite_default = proof_default.with_suffix(".sqlite")
    if not proof_default.exists() and sqlite_default.exists():
        proof_default = sqlite_default

    return {
        "root": root,
        "sap_daily_dir": root / DEFAULT_SAP_DAILY_RELATIVE_PATH,
        "proof_db": (
            _configured_path(proof_db, base=root)
            if proof_db
            else proof_default
        ),
        "proof_reference_db": (
            _configured_path(proof_reference_db, base=root)
            if proof_reference_db
            else None
        ),
    }
