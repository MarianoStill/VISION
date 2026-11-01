import warnings

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import lion


def test_public_service_processes_synthetic_workbook(synthetic_sap_xlsx):
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        model, details, issues, _, source_sheet = lion.process_workbook(
            synthetic_sap_xlsx, "2026-10-26"
        )

    assert source_sheet == "Data"
    assert len(model) == 1
    assert model.iloc[0]["Estado"] == "Liberar pedido"
    assert model.iloc[0]["Urgencia"] is not None
    assert details[model.iloc[0]["ID"]]["Estimado"].iloc[0] == pd.Timestamp(
        "2026-04-02"
    )
    assert model.iloc[0]["Urgencia"] == 207
    assert model.iloc[0]["Fecha de referencia de urgencia"] == "2026-10-26"
    assert list(details) == model["ID"].tolist()
    assert isinstance(issues, pd.DataFrame)


def test_public_service_requires_an_explicit_observation_date(synthetic_sap_xlsx):
    with pytest.raises(ValueError, match="fecha de observación explícita"):
        lion.process_workbook(synthetic_sap_xlsx, None)


def test_public_search_uses_received_lion_search_behavior(synthetic_sap_xlsx):
    model, _, _, _, _ = lion.process_workbook(synthetic_sap_xlsx, "2026-10-26")

    result = lion.search_machines(model, "synthetic-order", "Todo")

    assert_frame_equal(result.reset_index(drop=True), model.reset_index(drop=True))
    assert lion.search_machines(model, "", "Todo").empty


def test_global_search_includes_the_available_purchase_document_reference():
    model = pd.DataFrame(
        [
            {
                "ID": "synthetic-machine-001",
                "Pedido": "SYNTHETIC-ORDER-001",
                "Máquina": "Synthetic machine",
                "Número de serie": "",
                "Cliente": "Synthetic customer",
                "Material": "Synthetic material",
                "Documento de compras": "SYNTHETIC-PURCHASE-001",
            }
        ]
    )

    result = lion.search_machines(model, "synthetic-purchase", "Todo")

    assert result["ID"].tolist() == ["synthetic-machine-001"]


def test_service_runs_without_external_source_tree(
    synthetic_sap_xlsx, monkeypatch
):
    monkeypatch.delenv("CO_VISION_LION_SOURCE_DIR", raising=False)
    model, _, _, _, _ = lion.process_workbook(
        synthetic_sap_xlsx, "2026-10-26"
    )
    assert len(model) == 1


def test_public_filters_cover_received_fields_and_preserve_rows(synthetic_sap_xlsx):
    model, details, _, _, _ = lion.process_workbook(
        synthetic_sap_xlsx, "2026-10-26"
    )

    result = lion.filter_machines(
        model,
        details,
        filters={"Pedido": "synthetic-order-001"},
        exact=True,
    )

    assert_frame_equal(result.reset_index(drop=True), model.reset_index(drop=True))


def test_chassis_filter_does_not_substitute_serial_number(synthetic_sap_xlsx):
    model, details, _, _, _ = lion.process_workbook(
        synthetic_sap_xlsx, "2026-10-26"
    )

    with pytest.raises(ValueError, match="como sustituto"):
        lion.filter_machines(model, details, filters={"Chasis": "SYNTHETIC-CHASSIS-001"})
