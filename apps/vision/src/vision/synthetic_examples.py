SYNTHETIC_LION_MACHINE = {
    "ID": "demo-machine-001",
    "Pedido": "DEMO-ORDEN-001",
    "Máquina": "DEMO · Equipo técnico",
    "Número de serie": None,
    "Documento de compras": None,
    "Cliente": "DEMO · No aplica",
    "Material": "DEMO · No aplica",
    "Estado": "Planning",
    "Urgencia": None,
    "Color urgencia": None,
}

SYNTHETIC_INVENTORY_INPUTS = {
    "instances": [
        {
            "machine": "IDENTIFICADOR-SINTETICO-EJEMPLO",
            "stage": "1",
            "opening_date": "2026-01-02",
        }
    ],
    "dates": ["2026-01-02"],
    "rules": [
        {
            "id": "1",
            "name": "Etapa artificial de ejemplo técnico",
            "kind": "standard",
            "terminal": False,
        }
    ],
    "grain": "Día",
    "start": "2026-01-01",
    "end": "2026-01-31",
}

EMPTY_INVENTORY_INPUTS = {
    "instances": [],
    "dates": [],
    "rules": [],
    "grain": "Día",
    "start": "2026-01-01",
    "end": "2026-01-31",
}
