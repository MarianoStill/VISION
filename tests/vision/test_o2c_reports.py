import pandas as pd

from vision.o2c_reports import filter_scope


def _model():
    return pd.DataFrame(
        {
            "ID": ["1", "2", "3", "4"],
            "Oficina de ventas": ["A", "A", "B", "C"],
            "Comercial": ["x", "y", "z", "x"],
            "Cliente": ["c1", "c2", "c3", "c1"],
            "Pedido": ["p1", "p2", "p3", "p4"],
        }
    )


def test_no_filters_returns_everything():
    assert len(filter_scope(_model())) == 4


def test_multiple_areas_are_added():
    assert set(filter_scope(_model(), areas=["A", "B"])["ID"]) == {"1", "2", "3"}


def test_dimensions_combine_with_and():
    result = filter_scope(_model(), areas=["A", "C"], commercials=["x"], clients=["c1"])
    assert set(result["ID"]) == {"1", "4"}


def test_missing_column_does_not_restrict():
    model = _model().drop(columns=["Cliente"])
    assert len(filter_scope(model, clients=["c1"])) == 4
