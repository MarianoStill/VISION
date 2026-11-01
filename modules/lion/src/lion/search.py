import pandas as pd

from .sap_engine import norm


CHASSIS_NAMES = (
    "Chasis",
    "Bastidor",
    "Chassis",
    "Número de bastidor",
    "Numero de bastidor",
    "Número de chasis",
    "Numero de chasis",
)


def search(model,query,mode,exact=False):
 q=norm(query)
 if not q:return model.iloc[:0]
 fields={"Todo":["Pedido","Máquina","Número de serie","Cliente","Material","Documento de compras"],"Pedido":["Pedido"],"Máquina":["Máquina","Número de serie","Material"],"Cliente":["Cliente"]}[mode]
 mask=pd.Series(False,index=model.index)
 for f in fields:
  s=model[f].map(norm);mask |= s.eq(q) if exact else s.str.contains(q,regex=False,na=False)
 return model.loc[mask]


def chassis_columns(frame):
    accepted = {norm(name) for name in CHASSIS_NAMES}
    return [column for column in frame.columns if norm(column) in accepted]


def match_values(values, query, exact):
    normalized_query = norm(query)
    return any(
        norm(value) == normalized_query if exact else normalized_query in norm(value)
        for value in values
        if norm(value)
    )


def filter_machines(model, details, global_query="", filters=None, exact=False):
    """Apply the received LION global and field-specific machine filters."""
    filters = filters or {}
    active = {key: value for key, value in filters.items() if norm(value)}
    if not norm(global_query) and not active:
        return model.iloc[:0].copy()

    result = search(model, global_query, "Todo", exact) if norm(global_query) else model.copy()
    mapping = {
        "Comercial": "Comercial",
        "Cliente": "Cliente",
        "Pedido": "Pedido",
        "Máquina": "Máquina",
    }
    source_fields = {
        "Comercial": "Sales Representive Name",
        "Cliente": "Nombre del solicitante",
        "Pedido": "Documento de ventas",
        "Máquina": "Denomin.posición",
    }
    for label, column in mapping.items():
        if label not in active:
            continue
        if column not in model.columns:
            raise ValueError(
                "No se puede aplicar el filtro " + label + ": falta la columna " + column + "."
            )

        def matches(row):
            frame = details.get(row["ID"])
            source = source_fields[label]
            values = (
                frame[source].tolist()
                if frame is not None and source in frame.columns
                else [row[column]]
            )
            return match_values(values, active[label], exact)

        mask = result.apply(matches, axis=1) if not result.empty else pd.Series(
            False, index=result.index, dtype=bool
        )
        result = result.loc[mask.astype(bool)]

    if "Chasis" in active:
        direct = chassis_columns(model)
        source_columns = sorted(
            {
                column
                for frame in details.values()
                for column in chassis_columns(frame)
            }
        )
        if not direct and not source_columns:
            raise ValueError(
                "No hay una columna explícita de Chasis o Bastidor. "
                "No se utiliza Número de serie como sustituto. Deja Chasis vacío para buscar."
            )

        def matches_chassis(row):
            values = [row[column] for column in direct]
            frame = details.get(row["ID"])
            if frame is not None:
                for column in chassis_columns(frame):
                    values.extend(frame[column].tolist())
            return match_values(values, active["Chasis"], exact)

        mask = result.apply(matches_chassis, axis=1) if not result.empty else pd.Series(
            False, index=result.index, dtype=bool
        )
        result = result.loc[mask.astype(bool)]
    return result.copy()
