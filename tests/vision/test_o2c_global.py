import pandas as pd
import pytest

pytest.importorskip("streamlit")

from vision import o2c_global, o2c_workspace





def _model(rows):
    return pd.DataFrame(rows, columns=["ID", "Pedido", "Oficina de ventas", "Estado"])


def test_empty_or_missing_columns_return_no_rows():
    assert o2c_global.delegation_breakdown(pd.DataFrame()).empty
    assert o2c_global.delegation_breakdown(None).empty


def test_duplicate_rows_count_each_machine_and_order_once():
    model = _model([
        ("M1", "P1", "Madrid", None),
        ("M1", "P1", "Madrid", None),
        ("M2", "P1", "Madrid", None),
        ("M3", "P2", "Sevilla", None),
    ])
    table = o2c_global.delegation_breakdown(model).set_index("Delegación / área")
    assert table.loc["Madrid", "Máquinas"] == 2
    assert table.loc["Madrid", "Pedidos"] == 1
    assert table.loc["Sevilla", "Máquinas"] == 1
    assert table.loc["Total", "Máquinas"] == 3
    assert table.loc["Total", "Pedidos"] == 2


def test_machine_in_several_delegations_is_not_split_or_double_counted():
    model = _model([
        ("M1", "P1", "Madrid", None),
        ("M1", "P1", "Sevilla", None),
        ("M2", "P2", "Madrid", None),
    ])
    table = o2c_global.delegation_breakdown(model).set_index("Delegación / área")
    assert table.loc[o2c_global.MULTIPLE_AREAS, "Máquinas"] == 1
    assert table.loc["Madrid", "Máquinas"] == 1
    assert "Sevilla" not in table.index
    assert table.loc["Total", "Máquinas"] == 2
    assert table["Máquinas"].drop("Total").sum() == table.loc["Total", "Máquinas"]


def test_blank_ids_are_ignored_and_missing_delegation_is_labelled():
    model = _model([("", "P1", "Madrid", None), (None, "P2", "Madrid", None), ("M1", "P3", None, None)])
    table = o2c_global.delegation_breakdown(model).set_index("Delegación / área")
    assert list(table.index) == [o2c_global.NO_AREA, "Total"]
    assert table.loc["Total", "Máquinas"] == 1


def test_every_delegation_is_visible_and_stage_columns_match_lion_labels():
    model = _model([("M1", "P1", "Barcelona", None), ("M2", "P2", "Madrid", None), ("M3", "P3", "Sevilla", None)])
    table = o2c_global.delegation_breakdown(model)
    assert list(table["Delegación / área"]) == ["Barcelona", "Madrid", "Sevilla", "Total"]
    assert list(table.columns[3:]) == o2c_workspace.stage_labels()


def test_stage_counts_use_each_machine_once_per_stage(monkeypatch):
    first, second = o2c_workspace.stage_labels()[:2]
    mapping = {"A": (first,), "B": (first, second), "C": (second,)}
    monkeypatch.setattr(o2c_workspace, "stages_for_state", lambda estado: mapping.get(estado, ()))
    model = _model([
        ("M1", "P1", "Madrid", "A"),
        ("M1", "P1", "Madrid", "A"),
        ("M2", "P2", "Sevilla", "B"),
        ("M3", "P3", "Sevilla", "C"),
    ])
    table = o2c_global.delegation_breakdown(model).set_index("Delegación / área")
    assert table.loc["Madrid", first] == 1 and table.loc["Madrid", second] == 0
    assert table.loc["Sevilla", first] == 1 and table.loc["Sevilla", second] == 2
    assert table.loc["Total", first] == 2 and table.loc["Total", second] == 2
    assert table.loc["Total", "Máquinas"] == 3
