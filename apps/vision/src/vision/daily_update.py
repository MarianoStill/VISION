"""Actualización diaria: incorpora los Excel nuevos a PROOF, precalienta LION y las cachés,
y avisa a la app (señal por archivo) para que refresque sus cachés en proceso."""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

SIGNAL_NAME = "refresh_signal.json"


def signal_path(root):
    return Path(root) / "vision" / "cache" / SIGNAL_NAME


def read_token(root):
    """Token de la última actualización; None si todavía no existe señal."""
    try:
        return json.loads(signal_path(root).read_text(encoding="utf-8")).get("token")
    except (OSError, ValueError, AttributeError):
        return None


def write_signal(root, payload):
    path = signal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload, token=f"{time.time_ns()}")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(body), encoding="utf-8")
    os.replace(temporary, path)
    return body["token"]


def run_daily_update(sources=None, reference_date=None):
    """Ejecuta los pasos en orden; un fallo detiene la señal para no publicar datos a medias."""
    import proof
    from vision import lion_adapter
    from vision.data_sources import resolve_external_sources
    from vision.folder_sync import synchronize_folder
    from vision.sap_snapshots import discover_daily_snapshots

    sources = sources or resolve_external_sources()
    root = Path(sources["root"])
    database = Path(sources["proof_db"])
    daily = Path(sources["sap_daily_dir"])
    report = dict(started=time.time(), added=0, snapshot=None)

    if not database.is_file():
        raise FileNotFoundError("No se encontró la base PROOF configurada.")
    response = synchronize_folder(database, daily, root / "proof" / "sync_backups")
    if response["status"] == "blocked":
        raise ValueError(response["message"])
    report["added"] = response["added"]

    snapshots = discover_daily_snapshots(daily)
    if not snapshots:
        raise FileNotFoundError("No hay snapshots SAP disponibles.")
    latest = snapshots[0]
    lion_adapter.process_workbook(
        latest.path.read_bytes(),
        reference_date=reference_date or date.today().isoformat(),
    )
    report["snapshot"] = latest.path.name

    proof.set_base_dates_cache_dir(root / "vision" / "cache")
    proof.read_history(str(database))
    metrics = proof.calculate_completion_metrics(str(database))
    report["calculable"] = metrics["calculable_count"]
    report["finished"] = time.time()
    report["token"] = write_signal(root, dict(report))
    return report
