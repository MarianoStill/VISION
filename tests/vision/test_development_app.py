import time
from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

import openpyxl
import pandas as pd
import proof
import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest
from vision import lion_adapter

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


@pytest.fixture(autouse=True)
def isolate_background_work(monkeypatch):
    """Evita el proceso de calentamiento externo y la caché compartida entre tests."""
    import subprocess

    import streamlit as st

    st.cache_resource.clear()

    def fake_popen(args, *_, **__):
        # El calentamiento real arranca otro intérprete; aquí solo libera su marcador.
        Path(args[3]).unlink(missing_ok=True)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    yield
    st.cache_resource.clear()


def _picker(app):
    return next(
        s for s in app.selectbox if str(s.key).startswith("vision_access_category::")
    )


def _value_picker(app):
    return next(
        s for s in app.selectbox if str(s.key).startswith("vision_access_value::")
    )


def _enter_button(app):
    return next(b for b in app.button if str(b.key).startswith("vision_access_enter::"))


def _settle(app, attempts=80):
    """Repite la ejecución hasta que la precarga publica un estado final."""
    for _ in range(attempts):
        try:
            job = app.session_state["_vision_last_preload_job_v12"]
        except KeyError:
            job = None
        status = job.status() if job is not None else None
        if status is not None and (
            status["phase"] == "error"
            or (status["phase"] == "ready" and status["ingested"])
        ):
            return app.run(timeout=60)
        time.sleep(0.1)
        app.run(timeout=60)
    raise AssertionError("La precarga no terminó a tiempo")


def _enter_access(app, label, settle=True):
    if label == "O2C":
        category, value = "O2C", None
    elif label.endswith(" Manager"):
        category, value = "Delegación", label.removesuffix(" Manager")
    else:
        category, value = "Comercial", label
    _picker(app).set_value(category).run(timeout=60)
    if value is not None:
        _value_picker(app).set_value(value).run(timeout=60)
    _enter_button(app).click().run(timeout=60)
    return _settle(app) if settle else app


def _enter_as(app, commercial):
    return _enter_access(app, commercial)


def _fake_folder_sync(monkeypatch, added=0):
    """Sustituye la conciliación PROOF y devuelve las llamadas registradas."""
    from vision import folder_sync

    calls = []

    def synchronize_folder(database, directory, backup):
        calls.append((str(database), str(directory), str(backup)))
        return {
            "status": "synchronized" if added else "up_to_date",
            "added": added,
            "backup": None,
            "message": "synthetic",
        }

    monkeypatch.setattr(folder_sync, "synchronize_folder", synchronize_folder)
    return calls


def _text(app):
    return "\n".join(item.value for item in app.markdown)


def test_initial_screen_asks_who_signs_in_and_hides_data_administration():
    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)

    assert not app.exception
    assert "Bienvenido a <b>VISION</b>" in _text(app)
    assert "¿Cómo quieres acceder?" in _text(app)
    assert _picker(app).options == ["Comercial", "Delegación", "O2C"]
    assert _enter_button(app).disabled
    assert not app.file_uploader
    assert not app.segmented_control
    assert not app.pills
    assert not app.toggle
    assert not any("Administrator" in str(s.options) for s in app.selectbox)


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

    ingestion_calls = _fake_folder_sync(monkeypatch)

    monkeypatch.setattr(lion_adapter, "process_workbook", process_workbook)
    monkeypatch.setattr(proof, "read_history", read_history)

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)

    # La portada no procesa datos: LION y PROOF se preparan solo tras entrar.
    assert not app.exception
    assert lion_calls == []
    assert _picker(app).options == ["Comercial", "Delegación", "O2C"]
    app = _enter_access(app, "O2C")
    assert not app.exception
    assert len(lion_calls) == 1
    assert lion_calls[0][0] == synthetic_sap_xlsx
    assert len(ingestion_calls) == 1
    assert Path(ingestion_calls[0][0]).resolve() == proof_database.resolve()
    assert Path(ingestion_calls[0][1]).resolve() == sap_file.parent.resolve()
    assert proof_calls == [str(proof_database.resolve())]
    app.button(key="change_profile").click().run(timeout=60)
    assert _picker(app).options == ["Comercial", "Delegación", "O2C"]
    _picker(app).set_value("Comercial").run(timeout=60)
    assert _value_picker(app).options == ["Comercial A", "Comercial B"]
    assert _enter_button(app).disabled
    assert not app.file_uploader
    assert not app.date_input

    app = _enter_access(app, "Comercial A")
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
    assert "¿Cómo quieres acceder?" in _text(app)
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
    app.run(timeout=60)
    app = _settle(app)
    assert not app.exception
    assert len(lion_calls) == 2
    proof_reads = len(proof_calls)

    app.toggle(key="admin_data_mode").set_value(True).run(timeout=60)
    assert not app.exception
    assert len(lion_calls) == 2
    assert len(proof_calls) == proof_reads
    displayed_text = "\n".join(
        item.value for collection in (app.caption, app.error) for item in collection
    )
    assert any("control de fechas" in item.value for item in app.subheader)
    assert "Base PROOF configurada: proof.db" in displayed_text
    assert str(root) not in displayed_text
    assert "No se pudo conciliar el inventario de archivos" in displayed_text


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
    _fake_folder_sync(monkeypatch)

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)
    assert not app.exception
    # El catálogo de accesos se publica tras la primera preparación de datos.
    app = _enter_access(app, "O2C")
    app.button(key="change_profile").click().run(timeout=60)
    assert _picker(app).options == ["Comercial", "Delegación", "O2C"]
    _picker(app).set_value("Delegación").run(timeout=60)
    assert _value_picker(app).options == ["Delegación X", "Delegación Y"]
    app = _enter_access(app, "Delegación X Manager")
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
    assert "¿Cómo quieres acceder?" in _text(app)
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
    _fake_folder_sync(monkeypatch)

    app = AppTest.from_file(str(APP_FILE)).run(timeout=60)
    assert not app.exception
    app = _enter_access(app, "O2C")
    assert not app.exception
    assert processed == [b"invalid synthetic workbook", synthetic_sap_xlsx]
    app.button(key="change_profile").click().run(timeout=60)
    assert _picker(app).options == ["Comercial", "Delegación", "O2C"]
    _picker(app).set_value("Comercial").run(timeout=60)
    assert _value_picker(app).options == ["Comercial sintético"]
    app = _enter_access(app, "Comercial sintético")
    assert not app.exception
    assert "Mis clientes" in _text(app)
    assert any(b.key == "change_profile" for b in app.button)


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
        config={
            "sources": [{"id": "1", "name": "Etapa PROOF", "kind": "standard"}],
            "calendar": {"weekdays": [0, 1, 2, 3, 4], "holidays": []},
        },
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
    app = _enter_access(app, "O2C")
    assert not app.exception
    app.run(timeout=60)
    app = _settle(app)
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
    app.session_state["admin_data_mode"] = True
    app.run(timeout=60)

    assert not app.exception
    assert any("control de fechas" in item.value for item in app.subheader)
    assert any("sap" in item.value and "daily" in item.value for item in app.caption)
    assert any("No se encuentra la base PROOF" in item.value for item in app.error)
