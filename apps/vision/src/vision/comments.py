"""Comentarios compartidos de VISION, persistidos fuera de SAP/LION y de PROOF.

Un comentario pertenece a la máquina, no al perfil. La máquina se identifica con
la identidad progresiva existente: documento de ventas, documento de compras y
número de serie/chasis. El autor es el contexto seleccionado en VISION; no hay
autenticación real todavía.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from uuid import uuid4

import pandas as pd

from vision.data_sources import resolve_external_sources

SALES = "Pedido"
PURCHASE = "Documento de compras"
SERIAL = "Número de serie"
MAX_LENGTH = 2000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS machine_comments (
    comment_id TEXT PRIMARY KEY,
    sales_document TEXT NOT NULL,
    purchase_document TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    body TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class MachineIdentity:
    sales_document: str
    purchase_document: str = ""
    serial_number: str = ""


def _clean(value) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def identity_of(row) -> MachineIdentity | None:
    """Identidad de la máquina; None si no hay documento de ventas."""
    sales = _clean(row.get(SALES))
    if not sales:
        return None
    return MachineIdentity(sales, _clean(row.get(PURCHASE)), _clean(row.get(SERIAL)))


def _matches(stored: MachineIdentity, machine: MachineIdentity) -> bool:
    """El comentario aplica si sus identificadores guardados no contradicen a la máquina."""
    return (
        stored.sales_document == machine.sales_document
        and stored.purchase_document in ("", machine.purchase_document)
        and stored.serial_number in ("", machine.serial_number)
    )


def database_path() -> Path:
    return resolve_external_sources()["root"] / "vision" / "vision.sqlite"


def _connect(create: bool) -> sqlite3.Connection | None:
    path = database_path()
    if not path.exists():
        if not create:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(_SCHEMA)
    return connection


def add_comment(
    machine: MachineIdentity, *, author: str, role: str, body: str, now: datetime | None = None
) -> str:
    text = body.strip()
    if not text:
        raise ValueError("El comentario está vacío.")
    if len(text) > MAX_LENGTH:
        raise ValueError(f"El comentario supera {MAX_LENGTH} caracteres.")
    comment_id = uuid4().hex
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    with _connect(True) as connection:
        connection.execute(
            "INSERT INTO machine_comments VALUES (?,?,?,?,?,?,?,?)",
            (
                comment_id,
                machine.sales_document,
                machine.purchase_document,
                machine.serial_number,
                author,
                role,
                stamp,
                text,
            ),
        )
    return comment_id


def _all_rows() -> list[sqlite3.Row]:
    connection = _connect(False)
    if connection is None:
        return []
    with connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM machine_comments ORDER BY created_at DESC, rowid DESC"
        ).fetchall()


def _stored(row) -> MachineIdentity:
    return MachineIdentity(row["sales_document"], row["purchase_document"], row["serial_number"])


def comments_for(machine: MachineIdentity) -> list[dict]:
    """Comentarios de la máquina, el más reciente primero."""
    return [dict(row) for row in _all_rows() if _matches(_stored(row), machine)]


def counts_for(model: pd.DataFrame) -> pd.Series:
    """Número de comentarios por fila del modelo."""
    rows = _all_rows()
    if not rows:
        return pd.Series(0, index=model.index, dtype=int)
    by_sales: dict[str, list[MachineIdentity]] = {}
    for row in rows:
        by_sales.setdefault(row["sales_document"], []).append(_stored(row))
    counts = []
    for _, machine_row in model.iterrows():
        machine = identity_of(machine_row)
        counts.append(
            0
            if machine is None
            else sum(_matches(s, machine) for s in by_sales.get(machine.sales_document, []))
        )
    return pd.Series(counts, index=model.index, dtype=int)


def format_count(count: int) -> str:
    return f"💬 {count}" if count else ""
