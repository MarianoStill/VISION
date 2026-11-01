import proof


def test_operational_summary_uses_received_proof_thresholds_for_synthetic_rows():
    history = {
        "sources": [
            {
                "id": "SYNTHETIC-OPEN",
                "name": "Synthetic stage",
                "kind": "standard",
                "target": 10,
                "terminal": False,
            },
            {
                "id": "SYNTHETIC-TERMINAL",
                "name": "Synthetic terminal stage",
                "kind": "standard",
                "target": None,
                "terminal": True,
            },
        ],
        "instances": [
            {
                "machine": "SYNTHETIC-ORDER-001",
                "stage": "SYNTHETIC-OPEN",
                "stage_name": "Synthetic stage",
                "kind": "standard",
                "status": "Abierta",
                "elapsed": 8,
                "target": 10,
                "consumption": 80,
            },
            {
                "machine": "SYNTHETIC-ORDER-002",
                "stage": "SYNTHETIC-OPEN",
                "stage_name": "Synthetic stage",
                "kind": "standard",
                "status": "Abierta",
                "elapsed": 12,
                "target": 10,
                "consumption": 120,
            },
            {
                "machine": "SYNTHETIC-ORDER-003",
                "stage": "SYNTHETIC-OPEN",
                "stage_name": "Synthetic stage",
                "kind": "standard",
                "status": "Abierta",
                "elapsed": 13,
                "target": 10,
                "consumption": 130,
            },
            {
                "machine": "SYNTHETIC-ORDER-004",
                "stage": "SYNTHETIC-TERMINAL",
                "stage_name": "Synthetic terminal stage",
                "kind": "standard",
                "status": "Abierta",
                "elapsed": 15,
                "target": 10,
                "consumption": 150,
            },
        ],
    }

    summary = proof.operational_summary(history)

    assert summary["monitored_count"] == 3
    assert summary["overdue_count"] == 2
    assert summary["calculable_count"] == 3
    assert summary["ontime_count"] == 1
    assert summary["stage_rows"][0]["before_target"] == 0
    assert summary["stage_rows"][0]["around_target"] == 2
    assert summary["stage_rows"][0]["over_target"] == 1
    assert [row["Documento de ventas"] for row in summary["attention_rows"]] == [
        "SYNTHETIC-ORDER-003",
        "SYNTHETIC-ORDER-002",
        "SYNTHETIC-ORDER-001",
    ]
