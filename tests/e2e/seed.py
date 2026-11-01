"""Synthetic, non-business data root for UI automation. Never reads real SAP data."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import sys

import openpyxl

import proof
from lion.sap_engine import REQUIRED

COMMERCIAL = "SYNTHETIC-COMMERCIAL"
OFFICE = "SYNTHETIC-OFFICE"
CONFIG = {
    "sources": [{"id": "1", "name": "Etapa PROOF", "kind": "standard"}],
    "calendar": {"weekdays": [0, 1, 2, 3, 4], "holidays": []},
}


def workbook_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(list(REQUIRED) + ["Sales Representive Name", "Oficina de ventas", "Descripción de oficina de ventas"])
    row = {name: None for name in REQUIRED}
    row.update(
        {
            "Documento de ventas": "SYNTHETIC-ORDER-001",
            "Número de serie": "SYNTHETIC-CHASSIS-001",
            "Denomin.posición": "SYNTHETIC-MODEL",
            "Material": "SM-SYNTHETIC",
            "Nombre del solicitante": "SYNTHETIC-CLIENT",
            "Status de usuario": "ZCRE",
            "Fecha de precio": datetime(2026, 1, 1),
        }
    )
    sheet.append([row[name] for name in REQUIRED] + [COMMERCIAL, OFFICE, OFFICE])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def seed(root: Path, day: str = "2026-10-26") -> Path:
    content = workbook_bytes()
    daily = root / "sap" / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    (daily / f"snapshot_{day}.xlsx").write_bytes(content)
    database = root / "proof" / "proof.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    proof.register_snapshot(
        content, f"snapshot_{day}.xlsx", day, database_path=database, config=CONFIG
    )
    return root


if __name__ == "__main__":
    seed(Path(sys.argv[1]))
