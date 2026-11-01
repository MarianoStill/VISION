import lion


def test_stage_progress_preserves_simultaneous_received_states():
    result = lion.stage_progress("En fabricación + Taller")

    assert result["states"] == ["En fabricación", "Taller"]
    assert result["display_status"] == "Fabricando la máquina + Implementando cambios"
    assert result["caption"] == "Etapas 4 y 6 de 10"
    assert [row["percent"] for row in result["timeline"]] == [
        100,
        100,
        100,
        50,
        0,
        50,
        0,
        0,
        0,
        0,
    ]


def test_stage_progress_marks_received_delivered_state_complete():
    result = lion.stage_progress("Entregadas")

    assert result["caption"] == "Etapa 10 de 10"
    assert result["display_status"] == "Entregada a cliente"
    assert all(row["percent"] == 100 for row in result["timeline"])


def test_stage_progress_keeps_unknown_state_behavior():
    result = lion.stage_progress("Synthetic unknown state")

    assert result["states"] == []
    assert result["display_status"] == "Estado desconocido"
    assert result["caption"] == "Estado por determinar"
    assert all(row["percent"] == 0 for row in result["timeline"])
