import importlib.util
import os
from pathlib import Path

import pytest
from pandas.testing import assert_frame_equal

import lion
import proof


def load_module(path: Path, module_name: str):
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        pytest.fail("No se pudo cargar el módulo fuente configurado.")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def assert_lion_outputs_equal(received, migrated):
    received_model, received_details, received_issues, _, received_sheet = received
    migrated_model, migrated_details, migrated_issues, _, migrated_sheet = migrated
    try:
        assert_frame_equal(received_model, migrated_model)
        assert_frame_equal(received_issues, migrated_issues)
        assert set(received_details) == set(migrated_details)
        for key in received_details:
            assert_frame_equal(received_details[key], migrated_details[key])
        assert received_sheet == migrated_sheet
    except AssertionError:
        return False
    return True


@pytest.fixture
def received_lion_module():
    source_directory = os.environ.get("CO_VISION_LION_SOURCE_DIR")
    if not source_directory:
        pytest.skip("Set CO_VISION_LION_SOURCE_DIR to compare with received LION sources")
    source = Path(source_directory).expanduser().resolve() / "lion_sap_engine.py"
    if not source.is_file():
        pytest.fail("lion_sap_engine.py not found in the configured source folder.")
    return load_module(source, "received_lion_sap_engine")


@pytest.fixture
def received_proof_module():
    source_directory = os.environ.get("CO_VISION_PROOF_SOURCE_DIR")
    if not source_directory:
        pytest.skip("Set CO_VISION_PROOF_SOURCE_DIR to compare with received PROOF sources")
    source = Path(source_directory).expanduser().resolve() / "classification_engine.py"
    if not source.is_file():
        pytest.fail("classification_engine.py not found in the configured source folder.")
    return load_module(source, "received_proof_classification_engine")


@pytest.fixture
def received_lion_search_module(received_lion_module, monkeypatch):
    source_directory = Path(os.environ["CO_VISION_LION_SOURCE_DIR"]).expanduser().resolve()
    monkeypatch.syspath_prepend(str(source_directory))
    source = source_directory / "services" / "search.py"
    if not source.is_file():
        pytest.fail("The received LION search module is missing.")
    return load_module(source, "received_lion_search")


def test_synthetic_lion_workbook_matches_received_engine(
    received_lion_module, synthetic_sap_xlsx, tmp_path
):
    source_path = tmp_path / "synthetic.xlsx"
    source_path.write_bytes(synthetic_sap_xlsx)

    received = received_lion_module.load_model(
        source_path, reference_date="2026-10-26"
    )
    migrated = lion.process_workbook(
        synthetic_sap_xlsx, reference_date="2026-10-26"
    )

    assert assert_lion_outputs_equal(received, migrated), (
        "LION outputs differ for the synthetic workbook."
    )


def test_synthetic_proof_classification_matches_received_engine(
    received_proof_module, synthetic_sap_xlsx
):
    received = received_proof_module.classification_records(
        synthetic_sap_xlsx, {}
    )
    migrated = proof.classify_snapshot(synthetic_sap_xlsx)

    assert received == migrated, "PROOF memberships differ for the synthetic workbook."


@pytest.mark.parametrize(
    ("query", "mode", "exact"),
    [
        ("synthetic-order", "Pedido", False),
        ("synthetic", "Máquina", False),
        ("SYNTHETIC-ORDER-001", "Todo", True),
    ],
)
def test_synthetic_lion_search_matches_received_behavior(
    received_lion_search_module,
    received_lion_module,
    synthetic_sap_xlsx,
    tmp_path,
    query,
    mode,
    exact,
):
    source_path = tmp_path / "synthetic.xlsx"
    source_path.write_bytes(synthetic_sap_xlsx)
    received_model = received_lion_module.load_model(
        source_path, reference_date="2026-10-26"
    )[0]
    migrated_model = lion.process_workbook(
        synthetic_sap_xlsx, reference_date="2026-10-26"
    )[0]

    received = received_lion_search_module.search(
        received_model, query, mode, exact
    )
    migrated = lion.search_machines(migrated_model, query, mode, exact)

    try:
        assert_frame_equal(received.reset_index(drop=True), migrated.reset_index(drop=True))
    except AssertionError:
        pytest.fail("LION search outputs differ for the synthetic workbook.")


def test_received_excel_matches_received_lion_and_proof_implementations(
    received_lion_module, received_proof_module
):
    input_path = os.environ.get("CO_VISION_DEVELOPMENT_FILE")
    reference_date = os.environ.get("CO_VISION_OBSERVATION_DATE")
    if not input_path or not reference_date:
        pytest.skip(
            "Set CO_VISION_DEVELOPMENT_FILE and CO_VISION_OBSERVATION_DATE "
            "to compare the received workbook."
        )
    workbook_path = Path(input_path).expanduser().resolve()
    if not workbook_path.is_file():
        pytest.fail("The configured development workbook is unavailable.")
    try:
        content = workbook_path.read_bytes()
        received_lion = received_lion_module.load_model(
            workbook_path, reference_date=reference_date
        )
        migrated_lion = lion.process_workbook(content, reference_date=reference_date)
        received_proof = received_proof_module.classification_records(content, {})
        migrated_proof = proof.classify_snapshot(content)
    except Exception as exc:
        pytest.fail(
            "The configured workbook could not be compared ("
            + type(exc).__name__
            + ")."
        )

    assert assert_lion_outputs_equal(received_lion, migrated_lion), (
        "LION outputs differ for the configured workbook."
    )
    assert received_proof == migrated_proof, (
        "PROOF memberships differ for the configured workbook."
    )


def test_received_excel_is_already_registered_in_reference():
    workbook_path = os.environ.get("CO_VISION_DEVELOPMENT_FILE")
    reference_database = os.environ.get("CO_VISION_PROOF_REFERENCE_DB")
    expected_date = os.environ.get("CO_VISION_OBSERVATION_DATE")
    if not workbook_path or not reference_database or not expected_date:
        pytest.skip(
            "Set the workbook, reference database, and observation date "
            "to check the known duplicate."
        )
    content = Path(workbook_path).expanduser().resolve().read_bytes()

    match = proof.find_reference_observation(reference_database, content)

    assert match is not None, "The received workbook was not found in the reference."
    assert match["observed_date"] == expected_date
