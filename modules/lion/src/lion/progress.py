import unicodedata


STAGES = (
    ("Liberar pedido", "Creando pedido"),
    ("Compra máquina", "Solicitando máquina"),
    ("Compra accesorios", "Solicitando accesorios"),
    ("En fabricación", "Fabricando la máquina"),
    ("Fabricado", "Gestionando máquina en fábrica"),
    ("Taller", "Implementando cambios"),
    ("Planning", "Planificando la entrega"),
    ("Para entregar", "Coordinando transporte"),
    ("Arcese", "Gestionando envío"),
    ("Entregadas", "Entregada a cliente"),
)
ALIASES = {
    "liberar pedido": "Liberar pedido",
    "compra maquina": "Compra máquina",
    "compra de maquina": "Compra máquina",
    "compra accesorios": "Compra accesorios",
    "compra de accesorios": "Compra accesorios",
    "en fabricacion": "En fabricación",
    "fabricado": "Fabricado",
    "taller": "Taller",
    "planning": "Planning",
    "para entregar": "Para entregar",
    "arcese": "Arcese",
    "entregada": "Entregadas",
    "entregadas": "Entregadas",
}


def _norm(value):
    text = (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return " ".join(text.casefold().split())


def stage_progress(status):
    """Return the received LION stage labels and visual progress values."""
    states = []
    raw_states = str(status).replace(" + ", " | ").split("|") if status is not None else []
    for item in raw_states:
        state = ALIASES.get(_norm(item))
        if state and state not in states:
            states.append(state)
    order = {key: index for index, (key, _) in enumerate(STAGES)}
    states.sort(key=lambda state: order[state])

    values = [0] * len(STAGES)
    if states:
        indexes = [order[state] for state in states]
        first = min(indexes)
        values[:first] = [100] * first
        for index in indexes:
            values[index] = 50
        if states == ["Entregadas"]:
            values = [100] * len(STAGES)

    active = [index + 1 for index, value in enumerate(values) if value == 50]
    if not active and values[-1] == 100:
        caption = f"Etapa {len(STAGES)} de {len(STAGES)}"
    elif not active:
        caption = "Estado por determinar"
    else:
        caption = (
            ("Etapa " if len(active) == 1 else "Etapas ")
            + " y ".join(map(str, active))
            + f" de {len(STAGES)}"
        )

    display_labels = {key: label for key, label in STAGES}
    display_status = (
        " + ".join(display_labels[state] for state in states)
        if states
        else "Estado desconocido"
    )
    timeline = [
        {
            "number": index + 1,
            "label": label,
            "percent": percent,
            "kind": "done" if percent == 100 else "current" if percent == 50 else "future",
        }
        for index, ((_, label), percent) in enumerate(zip(STAGES, values))
    ]
    return {
        "states": states,
        "display_status": display_status,
        "caption": caption,
        "timeline": timeline,
    }
