import hashlib
import json
import sqlite3

import pytest

import proof
from proof.engine import Engine


def test_classification_returns_only_the_current_synthetic_snapshot(
    synthetic_sap_xlsx,
):
    records, warnings = proof.classify_snapshot(synthetic_sap_xlsx)

    assert len(records) == 1
    assert records[0]["machine"] == "SYNTHETIC-ORDER-001"
    assert records[0]["stage"] == "1"
    assert warnings


def test_register_snapshot_stores_one_observation_without_deriving_history(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "proof-dev.sqlite3"
    result = proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )

    assert result["status"] == "registered"
    assert result["observed_date"] == "2026-10-26"
    assert result["record_count"] == 1
    assert result["warning_count"] >= 0
    assert result["events_created"] == 0
    stored = Engine(database, {})
    try:
        assert len(stored.observations()) == 1
        assert stored.events() == []
        assert json.loads(stored.observations()[0]["effective_json"]) == []
    finally:
        stored.close()


def test_reference_lookup_is_read_only_and_matches_content(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "reference.sqlite3"
    registered = proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )
    before = hashlib.sha256(database.read_bytes()).digest()

    match = proof.find_reference_observation(database, synthetic_sap_xlsx)

    after = hashlib.sha256(database.read_bytes()).digest()
    assert registered["status"] == "registered"
    assert match == {"observed_date": "2026-10-26", "record_count": 1}
    assert before == after


def test_existing_reference_observation_is_not_copied_to_dev(
    synthetic_sap_xlsx, tmp_path
):
    reference = tmp_path / "reference.sqlite3"
    development = tmp_path / "development.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        reference,
    )

    result = proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        development,
        reference_database_path=reference,
    )

    assert result == {
        "status": "already_in_reference",
        "observed_date": "2026-10-26",
        "record_count": 1,
    }
    assert not development.exists()


def test_read_history_is_read_only_and_does_not_infer_events(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "reference.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )
    before = hashlib.sha256(database.read_bytes()).digest()

    history = proof.read_history(database)

    after = hashlib.sha256(database.read_bytes()).digest()
    assert before == after
    assert history["dates"] == ["2026-10-26"]
    assert len(history["observations"]) == 1
    assert len(history["observations"][0]["memberships"]) == 1
    assert history["events"] == []
    assert history["instances"] == []


def test_read_only_engine_blocks_database_writes(synthetic_sap_xlsx, tmp_path):
    database = tmp_path / "reference.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )

    read_only = Engine.open_read_only(database)
    try:
        assert read_only.db.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            read_only.db.execute("CREATE TABLE forbidden (value TEXT)")
    finally:
        read_only.close()


def test_completion_query_on_one_observation_does_not_invent_completions(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "reference.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )

    metrics = proof.calculate_completion_metrics(database)

    assert metrics["completed_count"] == 0
    assert metrics["baseline_date"] == "26/10/2026"
    assert metrics["registered_completed_count"] == 0
    assert metrics["rows"] == []


def test_history_search_index_uses_exact_serial_aliases_without_writes(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "reference.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )
    before = hashlib.sha256(database.read_bytes()).digest()

    index = proof.read_search_index(database)
    selections = {
        label: {
            row.get(label) or "Sin dato"
            for document in index["documents"].values()
            for row in document["rows"]
        }
        for label in ("Delegación", "Comercial", "Cliente")
    }
    all_documents = proof.filter_history_documents(
        index, [], selections
    )
    exact_serial_match = proof.filter_history_documents(
        index, [], selections, "SYNTHETIC-CHASSIS-001"
    )
    no_match = proof.filter_history_documents(
        index, [], selections, "UNKNOWN-SYNTHETIC-IDENTIFIER"
    )
    after = hashlib.sha256(database.read_bytes()).digest()

    assert all_documents == ["SYNTHETIC-ORDER-001"]
    assert exact_serial_match == ["SYNTHETIC-ORDER-001"]
    assert no_match == []
    assert before == after


def test_history_search_empty_filters_return_no_documents(synthetic_sap_xlsx, tmp_path):
    database = tmp_path / "reference.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )
    index = proof.read_search_index(database)

    assert proof.filter_history_documents(
        index,
        [],
        {"Delegación": set(), "Comercial": set(), "Cliente": set()},
    ) == []


def test_history_filter_keeps_observation_dates_and_does_not_change_source(
    synthetic_sap_xlsx, tmp_path
):
    database = tmp_path / "reference.sqlite3"
    proof.register_snapshot(
        synthetic_sap_xlsx,
        "synthetic-fixture.xlsx",
        "2026-10-26",
        database,
    )
    history = proof.read_history(database)

    filtered = proof.filter_history(history, set())

    assert history["dates"] == ["2026-10-26"]
    assert len(history["observations"][0]["memberships"]) == 1
    assert filtered["dates"] == history["dates"]
    assert filtered["observations"][0]["memberships"] == []
    assert filtered["events"] == []
    assert filtered["instances"] == []


def test_dev_and_reference_must_not_be_the_same_database(tmp_path):
    database = tmp_path / "same.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE observations (observed_date TEXT, summary_json TEXT, fingerprint TEXT)"
    )
    connection.commit()
    connection.close()

    with pytest.raises(ValueError, match="deben ser distintas"):
        proof.register_snapshot(
            b"synthetic",
            "synthetic-fixture.xlsx",
            "2026-10-26",
            database,
            reference_database_path=database,
        )
