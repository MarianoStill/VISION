"""Conciliación carpeta SAP / PROOF. Escrituras solo mediante lote PROOF y backup previo."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
from threading import RLock

_SYNC_LOCK = RLock()


def database_rows(database_path):
    path=Path(database_path).expanduser().resolve()
    connection=sqlite3.connect(f"{path.as_uri()}?mode=ro",uri=True)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        rows=[dict(row) for row in connection.execute(
            "SELECT observed_date,fingerprint,source_name,summary_json,rules_version FROM observations ORDER BY observed_date,seq")]
        rule=connection.execute("SELECT version,config_json FROM rule_versions ORDER BY version DESC LIMIT 1").fetchone()
        return rows,dict(rule) if rule else None
    finally:connection.close()


def _stable_bytes(snapshot):
    path=Path(snapshot.path)
    before=path.stat()
    if (before.st_mtime_ns,before.st_size)!=(snapshot.modified_ns,snapshot.size):
        raise ValueError("El archivo cambió antes de la lectura: "+path.name)
    content=path.read_bytes();after=path.stat()
    if (after.st_mtime_ns,after.st_size)!=(snapshot.modified_ns,snapshot.size) or len(content)!=snapshot.size:
        raise ValueError("El archivo cambió durante la lectura: "+path.name)
    return content


def audit_folder(database_path, directory):
    from vision.sap_snapshots import discover_daily_snapshots
    snapshots=discover_daily_snapshots(directory)
    saved,rule=database_rows(database_path)
    by_date={row['observed_date']:row for row in saved}
    by_hash={row['fingerprint']:row for row in saved}
    files=[]
    for snapshot in snapshots:
        item=dict(date=snapshot.observation_date,name=snapshot.path.name,path=str(snapshot.path),
                  modified_ns=snapshot.modified_ns,size=snapshot.size,filename_date=snapshot.date_from_filename)
        try:item['fingerprint']=hashlib.sha256(_stable_bytes(snapshot)).hexdigest()
        except OSError as exc:item['error']=type(exc).__name__
        except ValueError as exc:item['error']=str(exc)
        files.append(item)
    grouped=defaultdict(list)
    for item in files:grouped[item['date']].append(item)
    rows=[];pending=[];conflicts=[]
    all_dates=set(grouped)|set(by_date)
    if all_dates:
        first,last=date.fromisoformat(min(all_dates)),date.fromisoformat(max(all_dates))
        if (last-first).days<=3660:
            all_dates.update((first+timedelta(days=i)).isoformat() for i in range((last-first).days+1))
    for day in sorted(all_dates):
        items=grouped.get(day,[]);registered=by_date.get(day)
        status='Registrado sin archivo en carpeta' if registered else 'Sin archivo ni observación'
        detail='';candidate=None
        if items:
            errors=[item for item in items if item.get('error')]
            hashes={item.get('fingerprint') for item in items}
            if errors:
                status='Error de lectura';detail='; '.join(item['error'] for item in errors)
            elif not all(item['filename_date'] for item in items):
                status='Revisar fecha del archivo';detail='La fecha no es inequívoca en el nombre; no se importa automáticamente.'
            elif len(hashes)>1:
                status='Conflicto: varios archivos para la fecha'
            else:
                candidate=sorted(items,key=lambda item:item['name'].casefold())[0]
                fp=candidate['fingerprint']
                if registered:
                    status='Registrado' if registered['fingerprint']==fp else 'Conflicto: contenido distinto al registrado'
                elif fp in by_hash:
                    status='Conflicto: contenido registrado con otra fecha'
                    detail='Fecha ya guardada: '+by_hash[fp]['observed_date']
                else:status='Pendiente de incorporar'
            if status.startswith('Conflicto') or status in ('Error de lectura','Revisar fecha del archivo'):
                conflicts.append(day)
            if status=='Pendiente de incorporar':pending.append(candidate)
        rows.append(dict(Fecha=day,Archivos=' · '.join(item['name'] for item in items),
                         Excel=bool(items),PROOF=bool(registered),Estado=status,Detalle=detail,
                         **{'Versión de reglas':registered.get('rules_version') if registered else None}))
    # El mismo contenido en dos fechas nuevas también es un conflicto, no dos días distintos.
    duplicates=defaultdict(list)
    for item in pending:duplicates[item['fingerprint']].append(item['date'])
    duplicate_dates={day for days in duplicates.values() if len(days)>1 for day in days}
    for row in rows:
        if row['Fecha'] in duplicate_dates:
            row['Estado']='Conflicto: contenido repetido en varias fechas';conflicts.append(row['Fecha'])
    pending=[item for item in pending if item['date'] not in duplicate_dates]
    return dict(rows=rows,pending=sorted(pending,key=lambda item:item['date']),
                conflicts=sorted(set(conflicts)),registered_dates=sorted(by_date),
                rule=rule,files=files)


def synchronize_folder(database_path,directory,backup_directory):
    """Lote atómico existente: incorpora huecos y reconstruye eventos con las reglas guardadas."""
    from proof.engine import Engine
    with _SYNC_LOCK:
        audit=audit_folder(database_path,directory)
        # Los conflictos se excluyen en audit_folder; no bloquean fechas nuevas válidas.
        if not audit['pending']:
            if audit['conflicts']:
                return dict(status='blocked',added=0,backup=None,audit=audit,
                            message='No hay pendientes válidos. Los conflictos siguen sin resolverse; no se sobrescribió nada.')
            return dict(status='up_to_date',added=0,backup=None,audit=audit,message='No hay Excel pendientes de incorporar.')
        if not audit['rule']:
            raise ValueError('No hay reglas PROOF guardadas; no se crea una configuración nueva.')
        # Revalidar bytes antes de la escritura. No retener datos de archivos ya registrados.
        from types import SimpleNamespace
        batch=[]
        for item in audit['pending']:
            raw=_stable_bytes(SimpleNamespace(path=Path(item['path']),modified_ns=item['modified_ns'],size=item['size']))
            if hashlib.sha256(raw).hexdigest()!=item['fingerprint']:
                raise ValueError('El contenido cambió desde la conciliación.')
            batch.append(dict(raw=raw,name=item['name'],date=item['date']))
        path=Path(database_path).expanduser().resolve()
        backup_dir=Path(backup_directory).expanduser().resolve();backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/('proof-before-sync-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite')
        source=sqlite3.connect(f"{path.as_uri()}?mode=ro",uri=True)
        destination=sqlite3.connect(backup)
        try:source.backup(destination)
        finally:destination.close();source.close()
        cfg=json.loads(audit['rule']['config_json'])
        engine=Engine(path,cfg)
        try:
            if engine.current_version()!=audit['rule']['version']:
                raise ValueError('Las reglas cambiaron durante la conciliación. Reintenta.')
            result=engine.add_batch(batch)
        finally:engine.close()
        after=audit_folder(database_path,directory)
        report=dict(status='partial' if after['conflicts'] else 'synchronized',added=len(result),backup=str(backup),audit=after,
                    message=('Pendientes válidos incorporados. Los conflictos se conservan para revisión, sin sobrescribirlos.' if after['conflicts'] else 'Observaciones incorporadas y eventos reconstruidos por PROOF.'),
                    dates=[item['date'] for item in batch])
        # Traza externa; no se inserta una tabla nueva ni se altera el esquema PROOF.
        try:
            log=backup.with_suffix('.json')
            log.write_text(json.dumps({key:value for key,value in report.items() if key!='audit'},ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:report['message']+=' No se pudo escribir la traza JSON; se conserva el backup.'
        return report
