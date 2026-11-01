from datetime import datetime
from io import BytesIO

import openpyxl

import proof
from vision.daily_ingestion import ingest_proof_snapshot


def _updated_synthetic_workbook(content: bytes) -> bytes:
    workbook = openpyxl.load_workbook(BytesIO(content))
    workbook["Data"]["O2"] = datetime(2026, 1, 2)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_snapshot_ingestion_is_idempotent_and_preserves_older_history(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "proof.db"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "snapshot_2026-10-25.xlsx",
        "2026-10-25",
        database_path=database,
    )
    newer_snapshot = _updated_synthetic_workbook(synthetic_sap_xlsx)

    first_result = ingest_proof_snapshot(
        database, newer_snapshot, "snapshot_2026-10-27.xlsx", "2026-10-27"
    )
    repeated_result = ingest_proof_snapshot(
        database, newer_snapshot, "snapshot_2026-10-27.xlsx", "2026-10-27"
    )

    history = proof.read_history(database)
    assert first_result["status"] == "registered"
    assert repeated_result["status"] == "already_present"
    assert history["dates"] == ["2026-10-25", "2026-10-27"]
    assert len(history["observations"]) == 2
