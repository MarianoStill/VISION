from collections import defaultdict
from datetime import date, timedelta


def period_key(d, grain):
    dt = date.fromisoformat(d)
    if grain == "Semana":
        dt -= timedelta(days=dt.weekday())
    elif grain == "Mes":
        dt = dt.replace(day=1)
    return dt.isoformat()


def chart_rows(instances, dates, rules, grain, start, end):
    stages = sorted(
        [
            stage
            for stage in rules
            if stage.get("kind") == "standard"
            and not stage.get("terminal")
            and str(stage["id"]) in {str(i) for i in range(1, 10)}
        ],
        key=lambda stage: int(stage["id"]),
    )
    periods = defaultdict(list)
    for observed_date in sorted(set(dates)):
        if start <= observed_date <= end:
            periods[period_key(observed_date, grain)].append(observed_date)

    rows = []
    for period, observed in sorted(periods.items()):
        last = observed[-1]
        for stage in stages:
            documents = {
                str(instance["machine"])
                for instance in instances
                if str(instance.get("stage")) == str(stage["id"])
                and str(instance["opening_date"])[:10] <= last
                and (
                    not instance.get("closure_date")
                    or str(instance["closure_date"])[:10] > last
                )
            }
            rows.append(
                {
                    "Periodo": period,
                    "Etapa": str(stage["id"]) + ". " + stage["name"],
                    "Expedientes pendientes": len(documents),
                    "Fecha observada": last,
                }
            )
    return rows, stages
