from datetime import datetime

import pandas as pd
import pytest

from vision import comments


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("CO_VISION_DATA_ROOT", str(tmp_path))
    return tmp_path


def machine(sales="S1", purchase="", serial=""):
    return comments.MachineIdentity(sales, purchase, serial)


def test_no_database_until_first_write(data_root):
    assert comments.comments_for(machine()) == []
    assert not comments.database_path().exists()


def test_comments_are_shared_and_newest_first(data_root):
    comments.add_comment(
        machine(), author="A", role="Comercial", body="primero", now=datetime(2030, 1, 1, 9)
    )
    comments.add_comment(
        machine(), author="B", role="O2C", body="segundo", now=datetime(2030, 1, 2, 9)
    )
    listed = comments.comments_for(machine())
    assert [c["body"] for c in listed] == ["segundo", "primero"]
    assert [c["role"] for c in listed] == ["O2C", "Comercial"]
    assert comments.database_path().is_relative_to(data_root)


def test_progressive_identity_does_not_conflict():
    comments.add_comment(machine("S1"), author="A", role="Comercial", body="x")
    assert comments.comments_for(machine("S1", "P1", "N1"))
    comments.add_comment(machine("S1", "P1"), author="B", role="O2C", body="y")
    assert len(comments.comments_for(machine("S1", "P1", "N1"))) == 2
    assert len(comments.comments_for(machine("S1", "P2"))) == 1
    assert comments.comments_for(machine("S2")) == []


def test_validation():
    with pytest.raises(ValueError):
        comments.add_comment(machine(), author="A", role="O2C", body="   ")
    with pytest.raises(ValueError):
        comments.add_comment(
            machine(), author="A", role="O2C", body="x" * (comments.MAX_LENGTH + 1)
        )


def test_counts_and_identity():
    model = pd.DataFrame(
        {"Pedido": ["S1", "S2", ""], "Documento de compras": ["", "", ""], "Número de serie": ["", "", ""]}
    )
    assert comments.identity_of(model.iloc[2]) is None
    assert comments.counts_for(model).tolist() == [0, 0, 0]
    comments.add_comment(machine("S1"), author="A", role="Comercial", body="x")
    assert comments.counts_for(model).tolist() == [1, 0, 0]
    assert comments.format_count(0) == ""
    assert comments.format_count(2) == "💬 2"
