from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


HISTORY_FILTER_FIELDS = {
    "Delegación": "Descripción de oficina de ventas",
    "Comercial": "Sales Representive Name",
    "Cliente": "Nombre del solicitante",
    "Serie": "Número de serie",
    "Compra": "Documento compras",
    "Posición": "Posición",
}


def classify_snapshot(content: bytes, config: dict | None = None):
    """Classify one received PROOF snapshot without storing or deriving history."""
    from .engine import read_memberships

    return read_memberships(content, config or {})


def default_dev_database_path() -> Path:
    configured = os.environ.get("CO_VISION_PROOF_DEV_DB")
    if configured:
        return Path(configured).expanduser()
    root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return root / "CO-VISION" / "DEV" / "proof.sqlite3"


def find_reference_observation(database_path: str | Path, content: bytes):
    """Find a matching snapshot in a SQLite reference opened read-only."""
    path = Path(database_path).expanduser().resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        row = connection.execute(
            "SELECT observed_date, summary_json FROM observations WHERE fingerprint = ?",
            (hashlib.sha256(content).hexdigest(),),
        ).fetchone()
        if row is None:
            return None
        summary = json.loads(row[1])
        return {
            "observed_date": row[0],
            "record_count": summary.get("Expedientes inspeccionados"),
        }
    finally:
        connection.close()


def read_history(database_path: str | Path) -> dict:
    """Read stored PROOF observations and derived history without opening the database for writes."""
    from .engine import Engine

    engine = Engine.open_read_only(database_path)
    try:
        rows = engine.db.execute(
            """
            SELECT observed_date, source_name, processed_at, records_json,
                   summary_json, rules_version
              FROM observations
             ORDER BY observed_date, seq
            """
        ).fetchall()
        observations = []
        for row in rows:
            memberships = json.loads(row["records_json"])
            summary = json.loads(row["summary_json"])
            observations.append(
                {
                    "observed_date": row["observed_date"],
                    "source_name": row["source_name"],
                    "processed_at": row["processed_at"],
                    "record_count": summary.get(
                        "Expedientes inspeccionados",
                        len({record["machine"] for record in memberships}),
                    ),
                    "membership_count": len(memberships),
                    "summary": summary,
                    "memberships": memberships,
                    "rules_version": row["rules_version"],
                }
            )
        events = engine.events()
        return {
            "observations": observations,
            "dates": [observation["observed_date"] for observation in observations],
            "events": events,
            "instances": engine.instances(events=events),
            "sources": list(engine.cfg.get("sources", [])),
            "calendar": dict(engine.cfg.get("calendar", {})),
            "rules_version": engine.current_version(),
        }
    finally:
        engine.close()


def read_search_index(database_path: str | Path, progress=None) -> dict:
    """Index saved order attributes and exact serial/purchase aliases in memory."""
    from collections import defaultdict
    from io import BytesIO

    import openpyxl

    from .engine import Engine
    from .engine import txt

    engine = Engine.open_read_only(database_path)
    latest = {}
    aliases = defaultdict(set)
    missing = []
    try:
        observations = engine.db.execute(
            """
            SELECT id, observed_date
              FROM observations
             ORDER BY observed_date, seq
            """
        ).fetchall()
        for index, observation in enumerate(observations):
            raw_row = engine.db.execute(
                "SELECT raw FROM observations WHERE id = ?",
                (observation["id"],),
            ).fetchone()
            raw = raw_row["raw"] if raw_row else None
            if not raw:
                missing.append(observation["observed_date"])
                continue
            workbook = openpyxl.load_workbook(
                BytesIO(bytes(raw)),
                read_only=True,
                data_only=True,
            )
            try:
                sheet_name = next(
                    (
                        name
                        for name in ("Data", "Base")
                        if name in workbook.sheetnames
                    ),
                    None,
                )
                if sheet_name is None:
                    missing.append(observation["observed_date"])
                    continue
                rows = workbook[sheet_name].iter_rows(values_only=True)
                headers = [txt(value) for value in next(rows, ())]
                if "Documento de ventas" not in headers:
                    missing.append(observation["observed_date"])
                    continue
                document_index = headers.index("Documento de ventas")
                field_indexes = {
                    label: headers.index(field)
                    for label, field in HISTORY_FILTER_FIELDS.items()
                    if field in headers
                }
                current = defaultdict(list)
                for row in rows:
                    document = (
                        txt(row[document_index])
                        if document_index < len(row)
                        else ""
                    )
                    if not document:
                        continue
                    values = {
                        label: txt(row[column_index])
                        if column_index < len(row)
                        else ""
                        for label, column_index in field_indexes.items()
                    }
                    current[document].append(values)
                    for label in ("Serie", "Compra"):
                        if values.get(label):
                            aliases[values[label]].add(document)
                for document, records in current.items():
                    latest[document] = {
                        "date": observation["observed_date"],
                        "rows": records,
                    }
            finally:
                workbook.close()
            if progress is not None:
                progress((index + 1) / max(1, len(observations)))
        return {
            "documents": latest,
            "aliases": {key: sorted(values) for key, values in aliases.items()},
            "missing": missing,
        }
    finally:
        engine.close()


def filter_history_documents(
    search_index: dict,
    events: list[dict],
    selections: dict[str, set[str]],
    identifier_query: str = "",
) -> list[str]:
    """Apply the received PROOF metadata filters and exact serial/purchase lookup."""
    selected = {
        label: set(selections.get(label, set()))
        for label in ("Delegación", "Comercial", "Cliente")
    }
    options = {
        label: {
            row.get(label) or "Sin dato"
            for document in search_index["documents"].values()
            for row in document["rows"]
        }
        for label in selected
    }
    chosen = {
        document
        for document, indexed in search_index["documents"].items()
        if any(
            all((row.get(label) or "Sin dato") in selected[label] for label in selected)
            for row in indexed["rows"]
        )
    }
    if identifier_query:
        chosen &= set(search_index["aliases"].get(identifier_query, []))
    all_documents = {str(event.get("machine")) for event in events}
    unrestricted = not identifier_query and all(
        selected[label] == options[label] for label in selected
    )
    if unrestricted:
        chosen |= all_documents - set(search_index["documents"])
    return sorted(chosen)


def filter_history(history: dict, documents: set[str] | list[str]) -> dict:
    """Return a PROOF view scoped to exact sales documents without altering its source."""
    selected = {str(document) for document in documents}
    observations = []
    for observation in history["observations"]:
        memberships = [
            membership
            for membership in observation["memberships"]
            if str(membership.get("machine")) in selected
        ]
        observations.append(
            {
                **observation,
                "memberships": memberships,
                "membership_count": len(memberships),
            }
        )
    return {
        **history,
        "observations": observations,
        "events": [
            event
            for event in history["events"]
            if str(event.get("machine")) in selected
        ],
        "instances": [
            instance
            for instance in history["instances"]
            if str(instance.get("machine")) in selected
        ],
    }


def history_for_sales_document(history: dict, sales_document: str) -> dict:
    """Select stored PROOF records for one exact Documento de ventas."""
    document = str(sales_document).strip()
    observations = [
        observation
        for observation in history["observations"]
        if any(
            str(membership.get("machine", "")).strip() == document
            for membership in observation["memberships"]
        )
    ]
    events = [
        event
        for event in history["events"]
        if str(event.get("machine", "")).strip() == document
    ]
    instances = [
        instance
        for instance in history["instances"]
        if str(instance.get("machine", "")).strip() == document
    ]
    return {
        "observations": observations,
        "events": events,
        "instances": instances,
    }


def calculate_completion_metrics(
    database_path: str | Path,
    documents: set[str] | list[str] | None = None,
) -> dict:
    """Calculate the received PROOF completion query against stored data, read-only."""
    from .completion import calculate_completion_metrics as calculate
    from .engine import Engine

    engine = Engine.open_read_only(database_path)
    try:
        return calculate(engine, engine.cfg, documents)
    finally:
        engine.close()


def register_snapshot(
    content: bytes,
    source_name: str,
    observed_date: str,
    database_path: str | Path | None = None,
    *,
    reference_database_path: str | Path | None = None,
    config: dict | None = None,
) -> dict:
    """Store one snapshot in DEV, unless its content is already in the read-only reference."""
    from .engine import Engine

    destination = Path(database_path or default_dev_database_path()).expanduser().resolve()
    if reference_database_path is not None:
        reference = Path(reference_database_path).expanduser().resolve()
        if destination == reference:
            raise ValueError("La base DEV y la referencia de solo lectura deben ser distintas.")
        existing = find_reference_observation(reference, content)
        if existing is not None:
            return {"status": "already_in_reference", **existing}

    proof_engine = Engine(destination, config or {})
    try:
        warnings = proof_engine.add_observation(content, source_name, observed_date)
        proof_engine.db.commit()
        summary_row = proof_engine.db.execute(
            "SELECT summary_json FROM observations WHERE observed_date = ?",
            (observed_date,),
        ).fetchone()
        summary = json.loads(summary_row[0])
        return {
            "status": "registered",
            "observed_date": observed_date,
            "record_count": summary["Expedientes inspeccionados"],
            "warning_count": len(warnings),
            "events_created": 0,
        }
    finally:
        proof_engine.close()
