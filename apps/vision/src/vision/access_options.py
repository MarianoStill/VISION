"""Catálogo de acceso sin ejecutar LION ni consultar PROOF."""
from pathlib import Path
from openpyxl import load_workbook

def read_access_options(path):
    workbook = load_workbook(Path(path), read_only=True, data_only=True, keep_links=False)
    try:
        # Misma hoja inicial que la lectura Excel predeterminada. No se mezclan hojas.
        sheet = workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        header = None
        for index, row in enumerate(rows):
            names = [str(v).strip() if v is not None else "" for v in row]
            if "Sales Representive Name" in names:
                header = names
                break
            if index >= 29:
                break
        if header is None:
            raise ValueError("No se encontró Sales Representive Name en las primeras 30 filas de la primera hoja SAP.")
        commercial_index = header.index("Sales Representive Name")
        office_index = header.index("Oficina de ventas") if "Oficina de ventas" in header else None
        commercials, offices = set(), set()
        for row in rows:
            for column, values in ((commercial_index, commercials), (office_index, offices)):
                if column is not None and column < len(row) and row[column] is not None:
                    text = str(row[column]).strip()
                    if text:
                        values.add(text)
        return sorted(commercials, key=str.casefold), sorted(offices, key=str.casefold)
    finally:
        workbook.close()
