from __future__ import annotations
from collections import Counter
from io import BytesIO
import json
import openpyxl

QUERY_VERSION='2026-10-22-v1'

class ClassificationError(Exception):pass

def text(value):
    if value is None:return ''
    if isinstance(value,float) and value.is_integer():return str(int(value))
    return str(value).strip()
def blank(value):return text(value)==''
def present(value):return not blank(value)
def equal(value,expected):return text(value)==expected
def material_ok(value):
    value=text(value).upper();return value.startswith('SM') or value.startswith('SP')

RULES=[
 ('1','Liberar pedido','Creando pedido',lambda r:blank(r['Solicitud de pedido']) and blank(r['Documento compras']) and equal(r['Status de usuario'],'ZCRE') and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('2','Compra de máquina','Solicitando máquina',lambda r:present(r['Solicitud de pedido']) and blank(r['Documento compras']) and equal(r['Status de usuario'],'ZREL') and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('3','Compra de accesorios','Solicitando accesorios',lambda r:present(r['Solicitud de pedido']) and present(r['Documento compras']) and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('4','En fabricación','En fabricación',lambda r:equal(r['La entrada de mercancías está abierta'],'Y') and equal(r['PP DLV Status'],'N') and blank(r['Entrega']) and blank(r['Doc.facturación']) and blank(r['Número de serie']) and material_ok(r['Material'])),
 ('5','Fabricado','Fabricado',lambda r:equal(r['La entrada de mercancías está abierta'],'Y') and equal(r['PP DLV Status'],'N') and blank(r['Entrega']) and blank(r['Doc.facturación']) and present(r['Número de serie']) and material_ok(r['Material'])),
 ('6','Taller','Implementando cambios',lambda r:equal(r['La entrada de mercancías está abierta'],'N') and equal(r['PP DLV Status'],'N') and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('7','Planning','Planificando la entrega',lambda r:(((equal(r['La entrada de mercancías está abierta'],'Y') and equal(r['PP DLV Status'],'Y') and blank(r['Solicitud de pedido']) and blank(r['Entrega']) and blank(r['Doc.facturación'])) or (equal(r['La entrada de mercancías está abierta'],'N') and equal(r['PP DLV Status'],'Y') and present(r['Internal Note Line']))) and material_ok(r['Material']))),
 ('8','Para entregar','Coordinando transporte',lambda r:equal(r['La entrada de mercancías está abierta'],'N') and equal(r['PP DLV Status'],'Y') and blank(r['Solicitud de pedido']) and blank(r['Entrega']) and blank(r['Doc.facturación']) and blank(r['Internal Note Line']) and material_ok(r['Material'])),
 ('9','Arcese','Gestionando envío',lambda r:present(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('10','Entregada','Entregada a cliente',lambda r:present(r['Entrega']) and present(r['Doc.facturación']) and material_ok(r['Material'])),
 ('R2','Sin datos','Sin datos de aprovisionamiento',lambda r:blank(r['Solicitud de pedido']) and blank(r['Documento compras']) and blank(r['La entrada de mercancías está abierta']) and blank(r['PP DLV Status']) and equal(r['Status de usuario'],'ZREL') and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('R3','No Open GR','No Open GR',lambda r:blank(r['Solicitud de pedido']) and blank(r['Documento compras']) and blank(r['La entrada de mercancías está abierta']) and equal(text(r['PP DLV Status']).upper(),'N') and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
 ('R4','No PP DLV','No PP DLV',lambda r:blank(r['Solicitud de pedido']) and present(r['Documento compras']) and equal(r['La entrada de mercancías está abierta'],'Y') and blank(r['PP DLV Status']) and blank(r['Entrega']) and blank(r['Doc.facturación']) and material_ok(r['Material'])),
]
REQUIRED=['Documento de ventas','Solicitud de pedido','Documento compras','Status de usuario','Entrega','Doc.facturación','Material','La entrada de mercancías está abierta','PP DLV Status','Número de serie','Internal Note Line']

def _snapshot_sheet(workbook):
    for name in ('Data','Base'):
        if name in workbook.sheetnames:return workbook[name]
    return None

def _rows(sheet):
    iterator=sheet.iter_rows(values_only=True);headers=list(next(iterator))
    # Relevant query columns are unique even if unrelated headers repeat.
    index={name:headers.index(name) for name in REQUIRED if name in headers}
    missing=[name for name in REQUIRED if name not in index]
    if missing:raise ClassificationError('Faltan columnas requeridas: '+', '.join(missing))
    for excel_row,values in enumerate(iterator,2):
        yield excel_row,{name:(values[pos] if pos<len(values) else None) for name,pos in index.items()}

def can_classify_snapshot(raw):
    try:
        workbook=openpyxl.load_workbook(BytesIO(raw),read_only=True,data_only=True)
        try:return _snapshot_sheet(workbook) is not None
        finally:workbook.close()
    except Exception:return False

def classify_snapshot(raw,config=None):
    try:workbook=openpyxl.load_workbook(BytesIO(raw),read_only=True,data_only=True)
    except Exception as exc:raise ClassificationError('No se puede leer el Excel base.') from exc
    try:
        sheet=_snapshot_sheet(workbook)
        if sheet is None:raise ClassificationError('Falta la hoja Data o Base.')
        records=[];warnings=[];seen=set();row_counts=Counter();documents=set();unclassified=set()
        for row_num,row in _rows(sheet):
            document=text(row['Documento de ventas'])
            if not document:continue
            documents.add(document);matched=False
            for stage_id,source,name,predicate in RULES:
                if predicate(row):
                    matched=True;row_counts[stage_id]+=1;key=(document,stage_id)
                    if key in seen:continue
                    seen.add(key);records.append({'machine':document,'stage':stage_id,'source_stage':f'Query: {source}','source_sheet':sheet.title,'source_table':'Tabla1/Data','source_row':row_num,'query_version':QUERY_VERSION})
            if not matched and material_ok(row['Material']):unclassified.add(document)
        if not records:raise ClassificationError('Las queries no han clasificado ningún registro.')
        duplicates=sum(row_counts.values())-len(records)
        warnings.extend([f'Clasificación PROOF queries {QUERY_VERSION} desde hoja {sheet.title}.',f'{duplicates} pertenencias repetidas documento-etapa consolidadas.',f'{len(unclassified)} documentos SM/SP sin clasificación.'])
        audit={'query_version':QUERY_VERSION,'sheet':sheet.title,'source_documents':len(documents),'classified_memberships':len(records),'unclassified_documents':len(unclassified),'row_matches':dict(row_counts),'unique_by_stage':dict(Counter(r['stage'] for r in records))}
        return records,warnings,audit
    finally:workbook.close()

def classification_records(raw,config=None):
    records,warnings,_=classify_snapshot(raw,config);return records,warnings
