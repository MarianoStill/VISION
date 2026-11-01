from datetime import date
from io import BytesIO
import os
from pathlib import Path
import sqlite3
from zipfile import BadZipFile

import proof
import pytest
import openpyxl
import pandas as pd

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest
from vision import daily_ingestion, lion_adapter
from vision.synthetic_examples import (
    EMPTY_INVENTORY_INPUTS,
    SYNTHETIC_INVENTORY_INPUTS,
)


APP_FILE = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "vision"
    / "src"
    / "vision"
    / "development_app.py"
)


@pytest.fixture(autouse=True)
def isolate_external_operational_sources(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CO_VISION_DATA_ROOT",
        str(tmp_path / "synthetic-external-data-not-created"),
    )
    for variable in (
        "CO_VISION_SAP_FILE",
        "CO_VISION_PROOF_DB",
        "CO_VISION_PROOF_REFERENCE_DB",
    ):
        monkeypatch.delenv(variable, raising=False)


def _enter_as(app, commercial):
    app.button(key="role_commercial").click().run(timeout=60)
    app.selectbox(key="commercial_owner_picker").set_value(commercial).run(timeout=60)
    app.button(key="enter_vision").click().run(timeout=60)
    return app


def test_initial_screen_asks_for_role_and_hides_data_administration():
    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)

    assert not app.exception
    assert any("¿Cómo vas a utilizar VISION?" in item.value for item in app.markdown)
    assert app.button(key="role_commercial").disabled
    assert app.button(key="role_Taller").label == "Próximamente"
    assert app.button(key="role_Taller").disabled
    assert app.button(key="role_o2c").disabled
    assert "role_Logística" not in [b.key for b in app.button]
    assert "role_Backoffice" not in [b.key for b in app.button]
    assert app.toggle[0].label == "Administración / Datos"
    assert not app.segmented_control
    assert not app.file_uploader
    assert not app.pills


def test_commercial_workspace_filters_owner_and_clients_using_lion():
    model = pd.DataFrame(
        [
            {
                "ID": "machine-a",
                "Comercial": "Comercial A",
                "Cliente": "Cuenta A",
                "Pedido": "ORDER-A",
            },
            {
                "ID": "machine-b",
                "Comercial": "Comercial B",
                "Cliente": "Cuenta B",
                "Pedido": "ORDER-B",
            },
        ]
    )
    details = {
        "machine-a": pd.DataFrame(
            {
                "Sales Representive Name": ["Comercial A"],
                "Nombre del solicitante": ["Cuenta A"],
            }
        ),
        "machine-b": pd.DataFrame(
            {
                "Sales Representive Name": ["Comercial B"],
                "Nombre del solicitante": ["Cuenta B"],
            }
        ),
    }

    scoped = lion_adapter.filter_machines(
        model, details, filters={"Comercial": "Comercial A"}
    )

    assert scoped["ID"].tolist() == ["machine-a"]
    assert scoped["Cliente"].tolist() == ["Cuenta A"]


def test_automatic_sources_load_lion_and_proof_without_manual_widgets(
    synthetic_sap_xlsx, tmp_path, monkeypatch
):
    root = tmp_path / "CO-VISION-data"
    sap_file = root / "sap" / "daily" / "snapshot_2026-10-27.xlsx"
    proof_database = root / "proof" / "proof.db"
    sap_file.parent.mkdir(parents=True)
    proof_database.parent.mkdir(parents=True)
    sap_file.write_bytes(synthetic_sap_xlsx)
    proof_database.touch()
    monkeypatch.setenv("CO_VISION_DATA_ROOT", str(root))
    monkeypatch.delenv("CO_VISION_PROOF_DB", raising=False)
    monkeypatch.delenv("CO_VISION_PROOF_REFERENCE_DB", raising=False)

    model = pd.DataFrame(
        [
            {
                "ID": "machine-a",
                "Comercial": "Comercial A",
                "Cliente": "Cuenta A",
                "Pedido": "ORDER-A",
                "Máquina": "Modelo A",
                "Estado": "Taller",
                "Urgencia": 12,
                "Documento de compras": "PURCHASE-A",
                "Número de serie": "SERIAL-A",
            },
            {
                "ID": "machine-b",
                "Comercial": "Comercial B",
                "Cliente": "Cuenta B",
                "Pedido": "ORDER-B",
                "Máquina": "Modelo B",
                "Estado": "En fabricación",
                "Urgencia": 8,
                "Documento de compras": "PURCHASE-B",
                "Número de serie": "SERIAL-B",
            },
        ]
    )
    details = {
        "machine-a": pd.DataFrame(
            {
                "Sales Representive Name": ["Comercial A"],
                "Nombre del solicitante": ["Cuenta A"],
            }
        ),
        "machine-b": pd.DataFrame(
            {
                "Sales Representive Name": ["Comercial B"],
                "Nombre del solicitante": ["Cuenta B"],
            }
        ),
    }
    lion_calls = []
    proof_calls = []

    def process_workbook(content, reference_date):
        lion_calls.append((content, reference_date))
        return model, details, pd.DataFrame(), None, "Base"

    history = {
        "sources": [{"id": "1", "name": "Etapa PROOF", "kind": "standard"}],
        "dates": [],
        "observations": [
            {
                "observed_date": "2026-10-27",
                "memberships": [{"machine": "ORDER-A", "stage": "1"}],
            }
        ],
        "events": [],
        "instances": [],
    }

    def read_history(path):
        proof_calls.append(path)
        return history

    ingestion_calls = []

    def ingest_snapshot(*args):
        ingestion_calls.append(args)
        return {"status": "registered"}

    monkeypatch.setattr(lion_adapter, "process_workbook", process_workbook)
    monkeypatch.setattr(proof, "read_history", read_history)
    monkeypatch.setattr(daily_ingestion, "ingest_proof_snapshot", ingest_snapshot)

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)

    assert not app.exception
    assert len(lion_calls) == 1
    assert lion_calls[0][0] == synthetic_sap_xlsx
    assert ingestion_calls[0][0] == str(proof_database.resolve())
    assert ingestion_calls[0][2:] == (sap_file.name, "2026-10-27")
    assert proof_calls == [str(proof_database.resolve())]
    app.button(key="role_commercial").click().run(timeout=60)
    assert app.selectbox(key="commercial_owner_picker").options == [
        "Comercial A",
        "Comercial B",
    ]
    assert app.button(key="enter_vision").disabled
    assert not app.file_uploader
    assert not app.date_input

    app.selectbox(key="commercial_owner_picker").set_value("Comercial A").run(timeout=60)
    app.button(key="enter_vision").click().run(timeout=60)
    assert not app.exception
    rendered_markdown = "\n".join(item.value for item in app.markdown)
    assert "Situación actual · LION" in rendered_markdown
    assert "Evolución · PROOF" not in rendered_markdown
    assert app.selectbox(key="commercial_client").options == [
        "Todos los clientes",
        "Cuenta A — 1 máquina",
    ]
    assert "ORDER-A" in app.dataframe[0].value["Referencia / pedido"].tolist()

    app.selectbox(key="commercial_client").set_value("Cuenta A — 1 máquina").run(timeout=60)
    assert not app.exception
    assert app.dataframe[0].value["Cliente"].tolist() == ["Cuenta A"]

    app.button(key="change_profile").click().run(timeout=60)
    assert not app.exception
    assert any("¿Cómo vas a utilizar VISION?" in item.value for item in app.markdown)
    assert len(lion_calls) == 1
    app = _enter_as(app, "Comercial B")
    assert app.selectbox(key="commercial_client").options[0] == "Todos los clientes"
    assert "ORDER-A" not in app.dataframe[0].value["Referencia / pedido"].tolist()

    workbook = openpyxl.load_workbook(BytesIO(synthetic_sap_xlsx))
    workbook["Data"]["A2"] = "SYNTHETIC-ORDER-UPDATED"
    updated = BytesIO()
    workbook.save(updated)
    workbook.close()
    sap_file.write_bytes(updated.getvalue())
    app.run()
    assert not app.exception
    assert len(lion_calls) == 2
    assert len(proof_calls) == 1

    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert len(lion_calls) == 2
    assert len(proof_calls) == 1
    displayed_text = "\n".join(
        item.value
        for collection in (
            app.caption,
            app.info,
            app.success,
            app.warning,
            app.error,
        )
        for item in collection
    )
    assert sap_file.name in displayed_text
    assert "Base de datos: OK" in displayed_text
    assert "NUEVO REGISTRADO" in displayed_text
    assert str(tmp_path) not in displayed_text


def test_manager_scopes_workspace_by_delegation_and_optional_commercial(
    synthetic_sap_xlsx, tmp_path, monkeypatch
):
    root = tmp_path / "CO-VISION-data"
    sap_file = root / "sap" / "daily" / "snapshot_2026-10-27.xlsx"
    proof_database = root / "proof" / "proof.db"
    sap_file.parent.mkdir(parents=True)
    proof_database.parent.mkdir(parents=True)
    sap_file.write_bytes(synthetic_sap_xlsx)
    proof_database.touch()
    monkeypatch.setenv("CO_VISION_DATA_ROOT", str(root))

    rows = [
        ("machine-a", "Comercial A", "Cuenta A", "Delegación X"),
        ("machine-b", "Comercial B", "Cuenta B", "Delegación X"),
        ("machine-c", "Comercial C", "Cuenta C", "Delegación Y"),
    ]
    model = pd.DataFrame(
        [
            {
                "ID": identifier,
                "Comercial": commercial,
                "Cliente": client,
                "Pedido": "ORDER-" + identifier[-1].upper(),
                "Máquina": "Modelo " + identifier[-1].upper(),
                "Estado": "Taller",
                "Oficina de ventas": delegation,
            }
            for identifier, commercial, client, delegation in rows
        ]
    )
    details = {
        identifier: pd.DataFrame(
            {
                "Sales Representive Name": [commercial],
                "Nombre del solicitante": [client],
            }
        )
        for identifier, commercial, client, _ in rows
    }
    lion_calls = []

    def process_workbook(content, reference_date):
        lion_calls.append(reference_date)
        return model, details, pd.DataFrame(), None, "Base"

    history = {"sources": [], "dates": [], "observations": [], "events": [], "instances": []}
    monkeypatch.setattr(lion_adapter, "process_workbook", process_workbook)
    monkeypatch.setattr(proof, "read_history", lambda path: history)
    monkeypatch.setattr(
        daily_ingestion, "ingest_proof_snapshot", lambda *a: {"status": "registered"}
    )

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)
    assert not app.button(key="role_manager").disabled
    app.button(key="role_manager").click().run(timeout=60)
    assert app.selectbox(key="delegation_picker").options == [
        "Delegación X",
        "Delegación Y",
    ]
    app.selectbox(key="delegation_picker").set_value("Delegación X").run(timeout=60)
    app.button(key="enter_vision").click().run(timeout=60)
    assert not app.exception

    assert app.selectbox(key="manager_commercial::Delegación X").options == [
        "Todos los comerciales",
        "Comercial A",
        "Comercial B",
    ]
    table = app.dataframe[0].value
    assert sorted(table["Referencia / pedido"]) == ["ORDER-A", "ORDER-B"]
    assert "Comercial" in table.columns
    assert app.selectbox(key="commercial_client").options == [
        "Todos los clientes",
        "Cuenta A — 1 máquina",
        "Cuenta B — 1 máquina",
    ]

    app.selectbox(key="manager_commercial::Delegación X").set_value("Comercial A").run(
        timeout=60
    )
    assert not app.exception
    assert app.dataframe[0].value["Referencia / pedido"].tolist() == ["ORDER-A"]

    app.selectbox(key="manager_commercial::Delegación X").set_value(
        "Todos los comerciales"
    ).run(timeout=60)
    assert len(app.dataframe[0].value) == 2

    app.session_state["vision_navigation"] = "Informes"
    app.run(timeout=60)
    assert not app.exception
    assert not [item for item in app.selectbox if item.label == "Delegación"]
    assert app.selectbox(key="manager_report_client::Delegación X::Todos los comerciales").options == [
        "Todos los clientes",
        "Cuenta A",
        "Cuenta B",
    ]
    app.selectbox(key="manager_commercial::Delegación X").set_value("Comercial A").run(
        timeout=60
    )
    assert not app.exception
    assert app.selectbox(key="manager_report_client::Delegación X::Comercial A").options == [
        "Todos los clientes",
        "Cuenta A",
    ]
    app.session_state["vision_navigation"] = "Mis clientes"
    app.selectbox(key="manager_commercial::Delegación X").set_value(
        "Todos los comerciales"
    ).run(timeout=60)

    app.button(key="change_profile").click().run(timeout=60)
    assert any("¿Cómo vas a utilizar VISION?" in item.value for item in app.markdown)
    assert len(lion_calls) == 1


def test_invalid_latest_xlsx_falls_back_to_newest_lion_valid_snapshot(
    synthetic_sap_xlsx, tmp_path, monkeypatch
):
    root = tmp_path / "CO-VISION-data"
    daily = root / "sap" / "daily"
    proof_database = root / "proof" / "proof.db"
    daily.mkdir(parents=True)
    proof_database.parent.mkdir(parents=True)
    proof_database.touch()
    latest_invalid = daily / "snapshot_2026-10-28.xlsx"
    latest_valid = daily / "snapshot_2026-10-27.xlsx"
    latest_invalid.write_bytes(b"invalid synthetic workbook")
    latest_valid.write_bytes(synthetic_sap_xlsx)
    monkeypatch.setenv("CO_VISION_DATA_ROOT", str(root))
    monkeypatch.delenv("CO_VISION_PROOF_DB", raising=False)
    monkeypatch.delenv("CO_VISION_PROOF_REFERENCE_DB", raising=False)
    monkeypatch.setattr(
        proof,
        "read_history",
        lambda *_: {
            "sources": [],
            "dates": [],
            "observations": [],
            "events": [],
            "instances": [],
        },
    )
    processed = []

    def process_workbook(content, reference_date):
        processed.append(content)
        if content.startswith(b"invalid"):
            raise BadZipFile("invalid synthetic workbook")
        return (
            pd.DataFrame(
                [{"ID": "machine-a", "Comercial": "Comercial sintético", "Pedido": "ORDER-A"}]
            ),
            {},
            pd.DataFrame(),
            None,
            "Data",
        )

    monkeypatch.setattr(lion_adapter, "process_workbook", process_workbook)
    monkeypatch.setattr(
        daily_ingestion,
        "ingest_proof_snapshot",
        lambda *_: {"status": "registered"},
    )

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)

    assert not app.exception
    assert processed == [b"invalid synthetic workbook", synthetic_sap_xlsx]
    app.button(key="role_commercial").click().run(timeout=60)
    assert app.selectbox(key="commercial_owner_picker").options == ["Comercial sintético"]
    app.toggle[0].set_value(True).run()
    displayed = "\n".join(
        item.value for collection in (app.caption, app.success) for item in collection
    )
    assert latest_valid.name in displayed
    assert latest_invalid.name not in displayed


def test_streamlit_reruns_do_not_duplicate_daily_proof_observation(
    synthetic_sap_xlsx, tmp_path, monkeypatch
):
    root = tmp_path / "CO-VISION-data"
    sap_file = root / "sap" / "daily" / "snapshot_2026-10-27.xlsx"
    database = root / "proof" / "proof.db"
    sap_file.parent.mkdir(parents=True)
    database.parent.mkdir(parents=True)

    proof.register_snapshot(
        synthetic_sap_xlsx,
        "snapshot_2026-10-26.xlsx",
        "2026-10-26",
        database_path=database,
    )
    workbook = openpyxl.load_workbook(BytesIO(synthetic_sap_xlsx))
    workbook["Data"]["O2"] = date(2026, 1, 2)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    sap_file.write_bytes(output.getvalue())

    monkeypatch.setenv("CO_VISION_DATA_ROOT", str(root))
    monkeypatch.delenv("CO_VISION_PROOF_DB", raising=False)
    monkeypatch.delenv("CO_VISION_PROOF_REFERENCE_DB", raising=False)
    lion_calls = []
    model = pd.DataFrame(
        [{"ID": "machine-a", "Comercial": "Comercial sintético", "Pedido": "ORDER-A"}]
    )

    def process_workbook(content, reference_date):
        lion_calls.append((content, reference_date))
        return model, {}, pd.DataFrame(), None, "Data"

    monkeypatch.setattr(
        lion_adapter,
        "process_workbook",
        process_workbook,
    )

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)
    assert not app.exception
    app.run()
    assert not app.exception

    history = proof.read_history(database)
    assert len(lion_calls) == 1
    assert history["dates"] == ["2026-10-26", "2026-10-27"]
    assert len(history["observations"]) == 2


def test_missing_external_sources_are_reported_in_administration(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CO_VISION_DATA_ROOT", str(tmp_path / "missing-data"))
    monkeypatch.delenv("CO_VISION_PROOF_DB", raising=False)
    monkeypatch.delenv("CO_VISION_PROOF_REFERENCE_DB", raising=False)

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)
    app.toggle[0].set_value(True).run()

    assert not app.exception
    assert any("sap/daily" in item.value for item in app.error)
    assert any("Base de datos: ERROR" in item.value for item in app.error)
