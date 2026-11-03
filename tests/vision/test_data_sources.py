from pathlib import Path

from vision.data_sources import resolve_external_sources


def test_default_data_sources_resolve_under_external_user_directory(tmp_path):
    sources = resolve_external_sources({}, home=tmp_path)

    assert sources["root"] == tmp_path / "CO-VISION-data"
    assert sources["sap_daily_dir"] == (
        tmp_path / "CO-VISION-data" / "sap" / "daily"
    )
    assert sources["proof_db"] == (
        tmp_path / "CO-VISION-data" / "proof" / "proof.db"
    )


def test_configured_root_and_relative_overrides_resolve_from_data_root(tmp_path):
    root = tmp_path / "shared-operational-data"
    sources = resolve_external_sources(
        {
            "CO_VISION_DATA_ROOT": str(root),
            "CO_VISION_PROOF_DB": "history/proof-readonly.db",
        },
        home=tmp_path,
    )

    assert sources["root"] == root
    assert sources["sap_daily_dir"] == root / "sap" / "daily"
    assert sources["proof_db"] == root / "history" / "proof-readonly.db"


def test_legacy_read_only_proof_reference_is_supported(tmp_path):
    reference = tmp_path / "proof-reference.db"
    sources = resolve_external_sources(
        {"CO_VISION_PROOF_REFERENCE_DB": str(reference)},
        home=tmp_path,
    )

    assert sources["proof_db"] == tmp_path / "CO-VISION-data" / "proof" / "proof.db"
    assert sources["proof_reference_db"] == reference


def test_relative_data_root_resolves_from_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sources = resolve_external_sources(
        {"CO_VISION_DATA_ROOT": "external-data"},
        home=Path("unused-home"),
    )

    assert sources["root"] == tmp_path / "external-data"


def test_sap_daily_directory_can_be_configured_independently(tmp_path):
    folder = tmp_path / "Tracker"
    sources = resolve_external_sources(
        {"CO_VISION_DATA_ROOT": str(tmp_path / "root"), "CO_VISION_SAP_DAILY_DIR": str(folder)},
        home=tmp_path,
    )
    assert sources["sap_daily_dir"] == folder.resolve()
    assert sources["proof_db"] == (tmp_path / "root" / "proof" / "proof.db").resolve()
