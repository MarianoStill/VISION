from datetime import datetime
from io import BytesIO

import openpyxl
import pytest

from lion.sap_engine import REQUIRED


@pytest.fixture
def synthetic_sap_xlsx():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(list(REQUIRED))
    row = {name: None for name in REQUIRED}
    row.update(
        {
            "Documento de ventas": "SYNTHETIC-ORDER-001",
            "Número de serie": "SYNTHETIC-CHASSIS-001",
            "Denomin.posición": "SYNTHETIC-MODEL",
            "Material": "SM-SYNTHETIC",
            "Status de usuario": "ZCRE",
            "Fecha de precio": datetime(2026, 1, 1),
        }
    )
    sheet.append([row[name] for name in REQUIRED])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()
