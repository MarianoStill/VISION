import pytest

from lion import is_delivered


@pytest.mark.parametrize(
    ("synthetic_status", "expected"),
    [
        ("Entregadas", True),
        ("Planning | Entregadas", True),
        ("Entregadas | Taller", True),
        ("Taller | Planning", False),
        ("entregadas", False),
        (" Entregadas ", False),
        ("Entregadas extra", False),
        ("", False),
        (None, False),
    ],
    ids=[
        "exact-label",
        "exact-label-in-second-segment",
        "exact-label-in-first-segment",
        "other-labels",
        "case-sensitive",
        "whitespace-not-normalized",
        "substring-not-enough",
        "empty-string",
        "none",
    ],
)
def test_is_delivered_characterizes_received_behavior(synthetic_status, expected):
    assert is_delivered(synthetic_status) is expected


def test_public_lion_service_delegates_to_internal_function(monkeypatch):
    import lion.delivery

    received = []
    expected_result = object()

    def internal_function(status):
        received.append(status)
        return expected_result

    monkeypatch.setattr(lion.delivery, "is_delivered", internal_function)
    synthetic_status = "Taller | Entregadas"

    assert is_delivered(synthetic_status) is expected_result
    assert received == [synthetic_status]
