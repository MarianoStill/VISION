"""Prepara LION fuera del proceso Streamlit. No escribe PROOF ni usa APIs de UI."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import json,os,sys,time,traceback

def _bootstrap(root):
    for candidate in (root/'apps/vision/src',root/'modules/lion/src',root/'packages/lion/src',root/'apps/lion/src',root/'modules/proof/src',root/'packages/proof/src',root/'apps/proof/src'):
        if candidate.is_dir():sys.path.insert(0,str(candidate))

def main():
    root=Path(sys.argv[1]).resolve();marker=Path(sys.argv[2]);status=Path(sys.argv[3])
    _bootstrap(root)
    payload=dict(ok=False,started=time.time(),lion=False,proof=False,error=None)
    try:
        from vision.data_sources import resolve_external_sources
        from vision.sap_snapshots import discover_daily_snapshots
        from vision import lion_adapter
        import proof
        sources=resolve_external_sources();candidates=discover_daily_snapshots(sources['sap_daily_dir'])
        last=None
        for snapshot in candidates:
            try:
                before=snapshot.path.stat();raw=snapshot.path.read_bytes();after=snapshot.path.stat()
                if ((before.st_mtime_ns,before.st_size)!=(snapshot.modified_ns,snapshot.size) or
                    (after.st_mtime_ns,after.st_size)!=(snapshot.modified_ns,snapshot.size) or len(raw)!=snapshot.size):
                    raise ValueError('El Excel cambio durante la lectura.')
                lion_adapter.process_workbook(raw,reference_date=date.today().isoformat())
                payload['lion']=True;payload['snapshot']=snapshot.path.name;break
            except Exception as exc:last=exc
        if not payload['lion']:raise RuntimeError('No se pudo preparar ningun snapshot: '+type(last).__name__)
        db=Path(sources['proof_db'])
        if db.is_file():
            proof.read_history(str(db));payload['proof']=True
        payload['ok']=payload['lion'];payload['finished']=time.time()
    except Exception as exc:
        payload['error']=type(exc).__name__;payload['finished']=time.time()
    finally:
        try:
            status.parent.mkdir(parents=True,exist_ok=True)
            temporary=status.with_suffix('.tmp');temporary.write_text(json.dumps(payload),encoding='utf-8');os.replace(temporary,status)
        finally:
            marker.unlink(missing_ok=True)
if __name__=='__main__':main()
