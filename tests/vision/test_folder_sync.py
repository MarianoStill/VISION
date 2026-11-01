import sqlite3

import proof
from vision import folder_sync

CONFIG = {
    "sources": [{"id": "1", "name": "Etapa PROOF", "kind": "standard"}],
    "calendar": {"weekdays": [0, 1, 2, 3, 4], "holidays": []},
}


def _database(tmp_path, content):
    database = tmp_path / "proof" / "proof.db"
    database.parent.mkdir()
    proof.register_snapshot(
        content, "snapshot_2026-10-26.xlsx", "2026-10-26",
        database_path=database, config=CONFIG,
    )
    return database


def test_audit_marks_missing_day_and_registered_day(synthetic_sap_xlsx, tmp_path):
    database = _database(tmp_path, synthetic_sap_xlsx)
    folder = tmp_path / "daily"
    folder.mkdir()
    (folder / "snapshot_2026-10-26.xlsx").write_bytes(synthetic_sap_xlsx)
    audit = folder_sync.audit_folder(database, folder)
    assert [row["Estado"] for row in audit["rows"]] == ["Registrado"]
    assert audit["pending"] == [] and audit["conflicts"] == []


def test_synchronize_is_idempotent_and_backs_up_before_writing(
    synthetic_sap_xlsx, tmp_path
):
    database = _database(tmp_path, synthetic_sap_xlsx)
    folder = tmp_path / "daily"
    folder.mkdir()
    from datetime import date
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.load_workbook(BytesIO(synthetic_sap_xlsx))
    workbook["Data"]["O2"] = date(2026, 1, 2)
    output = BytesIO()
    workbook.save(output)
    (folder / "snapshot_2026-10-27.xlsx").write_bytes(output.getvalue())

    first = folder_sync.synchronize_folder(database, folder, tmp_path / "backups")
    assert first["added"] == 1 and first["backup"]
    backup = sqlite3.connect(first["backup"])
    try:
        assert backup.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    finally:
        backup.close()
    assert proof.read_history(database)["dates"] == ["2026-10-26", "2026-10-27"]

    second = folder_sync.synchronize_folder(database, folder, tmp_path / "backups")
    assert second["status"] == "up_to_date" and second["added"] == 0


def test_same_content_on_a_second_date_is_a_conflict_not_an_import(
    synthetic_sap_xlsx, tmp_path
):
    database = _database(tmp_path, synthetic_sap_xlsx)
    folder = tmp_path / "daily"
    folder.mkdir()
    (folder / "snapshot_2026-10-27.xlsx").write_bytes(synthetic_sap_xlsx)
    result = folder_sync.synchronize_folder(database, folder, tmp_path / "backups")
    assert result["status"] == "blocked" and result["added"] == 0
    assert proof.read_history(database)["dates"] == ["2026-10-26"]
