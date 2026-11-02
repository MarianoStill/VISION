import pandas as pd
import pytest
from vision.auth import RoleAssignment
from vision.authorization import (
    AuthorizationDenied,
    assigned_scope,
    restrict_rows_to_stages,
    visible_stages,
)


def test_role_assignment_scope_is_resolved_separately_from_identity():
    commercial = RoleAssignment("commercial", {"commercial": "Synthetic Commercial"})
    assert assigned_scope(commercial, "commercial") == "Synthetic Commercial"
    with pytest.raises(AuthorizationDenied):
        assigned_scope(commercial, "delegation")


def test_o2c_row_scope_is_enforced_before_rows_are_rendered():
    model = pd.DataFrame({"ID": ["A", "B", "C"], "Estado": ["early", "late", "early"]})
    stages = {"A": ("Stage A", "Stage B"), "B": ("Stage B",), "C": ("Stage C",)}
    scoped = restrict_rows_to_stages(
        model,
        ["Stage A"],
        lambda frame: frame["ID"].map(stages),
    )
    assert scoped["ID"].tolist() == ["A"]
    assert model["ID"].tolist() == ["A", "B", "C"]


def test_empty_o2c_scope_is_denied_and_labels_are_restricted():
    with pytest.raises(AuthorizationDenied):
        restrict_rows_to_stages(
            pd.DataFrame({"ID": ["A"]}),
            [],
            lambda frame: pd.Series([("Stage A",)], index=frame.index),
        )
    assert visible_stages(["Stage A", "Stage B"], ["Stage B"]) == ["Stage B"]
