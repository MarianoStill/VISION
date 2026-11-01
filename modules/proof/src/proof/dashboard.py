def operational_summary(history: dict) -> dict:
    """Summarize stored PROOF instances using the received dashboard conventions."""
    sources = history["sources"]
    standard_ids = [
        str(source["id"])
        for source in sources
        if source.get("kind") == "standard"
    ]
    if not standard_ids:
        raise ValueError("No hay etapas estandar configuradas.")

    rules = {str(source["id"]): source for source in sources}
    active = [
        instance
        for instance in history["instances"]
        if instance.get("status") == "Abierta"
        and instance.get("kind") == "standard"
        and str(instance.get("stage")) in standard_ids
        and not rules.get(str(instance.get("stage")), {}).get("terminal")
    ]
    monitored = {instance.get("machine") for instance in active}
    overdue = {
        instance.get("machine")
        for instance in active
        if instance.get("consumption") is not None
        and instance["consumption"] > 100
    }
    calculable = {
        instance.get("machine")
        for instance in active
        if instance.get("target") not in (None, 0)
        and instance.get("consumption") is not None
    }
    stage_rows = []
    for stage_id in standard_ids:
        rule = rules.get(stage_id, {})
        instances = [
            instance
            for instance in active
            if str(instance.get("stage")) == stage_id
        ]
        values = [
            instance["consumption"]
            for instance in instances
            if instance.get("consumption") is not None
        ]
        stage_rows.append(
            {
                "id": stage_id,
                "name": rule.get("name", f"Etapa {stage_id}"),
                "target": rule.get("target"),
                "terminal": bool(rule.get("terminal")),
                "documents": len({instance.get("machine") for instance in instances}),
                "average_consumption": (
                    sum(values) / len(values) if values else None
                ),
                "before_target": len(
                    {
                        instance.get("machine")
                        for instance in instances
                        if instance.get("consumption") is not None
                        and instance["consumption"] < 80
                    }
                ),
                "around_target": len(
                    {
                        instance.get("machine")
                        for instance in instances
                        if instance.get("consumption") is not None
                        and 80 <= instance["consumption"] <= 120
                    }
                ),
                "over_target": len(
                    {
                        instance.get("machine")
                        for instance in instances
                        if instance.get("consumption") is not None
                        and instance["consumption"] > 120
                    }
                ),
            }
        )

    attention = []
    for instance in active:
        target = instance.get("target")
        elapsed = instance.get("elapsed")
        consumption = instance.get("consumption")
        if consumption is None:
            status = "Sin objetivo definido"
        elif consumption < 80:
            status = "Antes del objetivo"
        elif consumption <= 120:
            status = "En torno al objetivo"
        else:
            status = "Fuera de plazo"
        attention.append(
            {
                "Documento de ventas": instance.get("machine"),
                "Etapa": (
                    f"{instance.get('stage')}. {instance.get('stage_name')}"
                ),
                "Días en etapa": elapsed,
                "Objetivo (días)": target,
                "Consumo de tiempo (%)": (
                    round(consumption, 1) if consumption is not None else None
                ),
                "Exceso (días laborables)": (
                    max(0, elapsed - target)
                    if elapsed is not None and target
                    else None
                ),
                "Exceso del objetivo (%)": (
                    round(max(0, consumption - 100), 1)
                    if consumption is not None
                    else None
                ),
                "Estado": status,
            }
        )
    attention.sort(
        key=lambda row: row["Consumo de tiempo (%)"] or -1,
        reverse=True,
    )
    return {
        "active": active,
        "monitored_count": len(monitored),
        "overdue_count": len(overdue),
        "calculable_count": len(calculable),
        "ontime_count": len(calculable - overdue),
        "stage_rows": stage_rows,
        "attention_rows": attention,
    }
