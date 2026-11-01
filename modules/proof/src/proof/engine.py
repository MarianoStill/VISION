from __future__ import annotations
import hashlib,io,json,re,sqlite3,uuid
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
import openpyxl
from .errors import ProofError
from .classification_engine import can_classify_snapshot, classification_records

def txt(v):
    if v is None:return ''
    if isinstance(v,float) and v.is_integer():return str(int(v))
    return str(v).strip()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def load_config(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def workdays(a,b,cal):
    """Mismo intervalo (a,b], sin iterar todos los días del recorrido."""
    a=date.fromisoformat(a);b=date.fromisoformat(b)
    days=(b-a).days
    if days<=0:return 0
    wd=set(cal.get('weekdays',[0,1,2,3,4])) & set(range(7))
    weeks,remainder=divmod(days,7)
    count=weeks*len(wd)+sum((a+timedelta(days=i)).weekday() in wd for i in range(1,remainder+1))
    for holiday in set(cal.get('holidays',[])):
        # El original solo descuenta cadenas ISO idénticas a date.isoformat().
        try:h=date.fromisoformat(holiday)
        except (TypeError,ValueError):continue
        if h.isoformat()==holiday and a<h<=b and h.weekday() in wd:count-=1
    return count
def infer_date(name):
    m=re.search(r'(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})(?!\d)',name)
    if not m:return None
    try:return date(int(m[3]),int(m[2]),int(m[1])).isoformat()
    except ValueError:return None

def _table(ws):
    if not ws.tables:raise ProofError(f'La hoja {ws.title} no contiene una tabla de Excel.')
    t=next(iter(ws.tables.values()));block=[[c.value for c in row] for row in ws[t.ref]];headers=[txt(x) for x in block[0]]
    if not headers or len(headers)!=len(set(headers)):raise ProofError(f'Cabeceras vacías o duplicadas en {ws.title}.')
    return t.name,headers,block[1:]
def read_memberships(raw,cfg):
    # PROOF v10: classify directly from the immutable Data/Base snapshot.
    if can_classify_snapshot(raw):
        return classification_records(raw,cfg)
    try:w=openpyxl.load_workbook(io.BytesIO(raw),data_only=True,read_only=False)
    except Exception as exc:raise ProofError('No se puede leer el archivo Excel.') from exc
    records=[];warnings=[];keycol=cfg['identity_column']
    try:
        for src in cfg['sources']:
            sn=src['sheet']
            if sn not in w.sheetnames:
                if src.get('required'):raise ProofError('Falta la hoja obligatoria: '+sn)
                warnings.append('Hoja opcional no disponible: '+sn);continue
            table,headers,rows=_table(w[sn])
            if keycol not in headers:raise ProofError(f'Falta la columna {keycol} en {sn}.')
            ix=headers.index(keycol);seen=set();dups=blanks=0
            for n,row in enumerate(rows,2):
                if not any(txt(v) for v in row):continue
                key=txt(row[ix])
                if not key:blanks+=1;continue
                pair=(key,src['id'])
                if pair in seen:dups+=1;continue
                seen.add(pair);records.append({'machine':key,'stage':src['id'],'source_stage':sn,'source_sheet':sn,'source_table':table,'source_row':n})
            if dups:warnings.append(f'{sn}: {dups} filas repetidas del mismo documento-etapa consolidadas.')
            if blanks:warnings.append(f'{sn}: {blanks} filas sin {keycol} excluidas.')
        if not records:raise ProofError('No hay registros identificables.')
        return records,warnings
    finally:w.close()

SCHEMA='''
CREATE TABLE IF NOT EXISTS observations(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,observed_date TEXT UNIQUE,processed_at TEXT,fingerprint TEXT UNIQUE,source_name TEXT,records_json TEXT,effective_json TEXT,summary_json TEXT,raw BLOB,rules_version INTEGER);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,observation_id TEXT,machine TEXT,stage TEXT,instance TEXT,type TEXT,payload TEXT);
CREATE TABLE IF NOT EXISTS rule_versions(version INTEGER PRIMARY KEY,created_at TEXT,config_json TEXT,note TEXT);
'''
class Engine:
    def __init__(self,path,cfg):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.cfg=cfg;self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA);self._migrate();self._ensure_rule()
    @classmethod
    def open_read_only(cls,path):
        resolved=Path(path).expanduser().resolve()
        if not resolved.is_file():raise FileNotFoundError(f'No se encuentra el historial PROOF: {resolved}')
        connection=sqlite3.connect(f'{resolved.as_uri()}?mode=ro',uri=True)
        try:
            connection.row_factory=sqlite3.Row
            connection.execute('PRAGMA query_only=ON')
            row=connection.execute('select config_json from rule_versions order by version desc limit 1').fetchone()
            instance=cls.__new__(cls);instance.path=resolved;instance.db=connection;instance.cfg=json.loads(row['config_json']) if row else {}
            return instance
        except Exception:
            connection.close()
            raise
    def _migrate(self):
        cols={r['name'] for r in self.db.execute('pragma table_info(observations)')}
        for col,kind in [('raw','BLOB'),('rules_version','INTEGER')]:
            if col not in cols:self.db.execute(f'alter table observations add column {col} {kind}')
        self.db.commit()
    def _ensure_rule(self):
        if not self.db.execute('select 1 from rule_versions').fetchone():
            self.db.execute('insert into rule_versions values(1,?,?,?)',(datetime.now(timezone.utc).isoformat(),json.dumps(self.cfg,ensure_ascii=False),'Configuración inicial/migrada'));self.db.commit()
    def close(self):self.db.close()
    def observations(self):return [dict(r) for r in self.db.execute('select * from observations order by observed_date,seq')]
    def events(self):return [json.loads(r[0]) for r in self.db.execute('select payload from events order by seq')]
    def current_version(self):return self.db.execute('select max(version) from rule_versions').fetchone()[0]
    def backup(self, dest):
        # PROOF_BACKUP_CLOSE_V1: cerrar siempre la conexion de destino.
        import sqlite3
        destination = sqlite3.connect(str(dest))
        try:
            self.db.backup(destination)
        finally:
            destination.close()
    def add_observation(self,raw,name,observed_date):
        try:date.fromisoformat(observed_date)
        except Exception as exc:raise ProofError('Fecha no válida.') from exc
        if self.db.execute('select 1 from observations where observed_date=?',(observed_date,)).fetchone():raise ProofError('Ya existe una observación en '+observed_date)
        fp=digest(raw)
        if self.db.execute('select 1 from observations where fingerprint=?',(fp,)).fetchone():raise ProofError('El archivo ya fue cargado: '+name)
        records,warnings=read_memberships(raw,self.cfg);oid=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat()
        summary={'Fecha de observación':observed_date,'Archivo':name,'Expedientes inspeccionados':len({r['machine'] for r in records}),'Advertencias de lectura':len(warnings),'Resultado':'Observación almacenada'}
        self.db.execute('insert into observations(id,observed_date,processed_at,fingerprint,source_name,records_json,effective_json,summary_json,raw,rules_version) values(?,?,?,?,?,?,?,?,?,?)',(oid,observed_date,now,fp,name,json.dumps(records,ensure_ascii=False),'[]',json.dumps(summary,ensure_ascii=False),raw,self.current_version()))
        return warnings
    def add_batch(self,items):
        dates=[x['date'] for x in items]
        if len(dates)!=len(set(dates)):raise ProofError('Hay fechas repetidas en el lote.')
        previews=[]
        for x in sorted(items,key=lambda z:z['date']):
            records,warnings=read_memberships(x['raw'],self.cfg);previews.append((x,records,warnings))
        try:
            self.db.execute('begin immediate')
            for x,records,warnings in previews:
                if self.db.execute('select 1 from observations where observed_date=?',(x['date'],)).fetchone():raise ProofError('Ya existe una observación en '+x['date'])
                fp=digest(x['raw'])
                if self.db.execute('select 1 from observations where fingerprint=?',(fp,)).fetchone():raise ProofError('Archivo duplicado: '+x['name'])
                oid=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat();summary={'Fecha de observación':x['date'],'Archivo':x['name'],'Expedientes inspeccionados':len({r['machine'] for r in records}),'Advertencias de lectura':len(warnings),'Resultado':'Observación almacenada'}
                self.db.execute('insert into observations(id,observed_date,processed_at,fingerprint,source_name,records_json,effective_json,summary_json,raw,rules_version) values(?,?,?,?,?,?,?,?,?,?)',(oid,x['date'],now,fp,x['name'],json.dumps(records,ensure_ascii=False),'[]',json.dumps(summary,ensure_ascii=False),x['raw'],self.current_version()))
            self._rebuild_in_transaction(self.cfg,self.current_version())
            self.db.commit()
        except Exception:self.db.rollback();raise
        return [{'Archivo':x['name'],'Fecha':x['date'],'Registros':len(r),'Advertencias':len(w)} for x,r,w in previews]
    def preview_rebuild(self,newcfg):
        old=self.events();new=self._derive(newcfg)
        sig=lambda e:(e['machine'],e['stage'],e['type'],e['observed_date'])
        a={sig(e) for e in old};b={sig(e) for e in new['events']}
        return {'Eventos actuales':len(a),'Eventos nuevos':len(b),'Añadidos':len(b-a),'Eliminados':len(a-b),'Observaciones':len(self.observations()),'_derived':new}
    def apply_rules(self,newcfg,note):
        preview=self.preview_rebuild(newcfg);version=self.current_version()+1
        try:
            self.db.execute('begin immediate');self.db.execute('insert into rule_versions values(?,?,?,?)',(version,datetime.now(timezone.utc).isoformat(),json.dumps(newcfg,ensure_ascii=False),note));self._write_derived(preview['_derived'],version);self.db.commit();self.cfg=newcfg
        except Exception:self.db.rollback();raise
        preview.pop('_derived');preview['Versión aplicada']=version;return preview
    def rebuild(self):
        v=self.current_version();cfg=json.loads(self.db.execute('select config_json from rule_versions where version=?',(v,)).fetchone()[0])
        try:self.db.execute('begin immediate');self._rebuild_in_transaction(cfg,v);self.db.commit();self.cfg=cfg
        except Exception:self.db.rollback();raise
    def _rebuild_in_transaction(self,cfg,version):self._write_derived(self._derive(cfg),version)
    def _derive(self,cfg):
        sources={s['id']:s for s in cfg['sources']};active={};terminal_seen=set();events=[];states=[];prev_machines=set()
        observations = (self.db.execute("select id,observed_date,records_json,summary_json from observations order by observed_date,seq")
                        if hasattr(self, "db") else self.observations())
        for obs in observations:
            records=json.loads(obs['records_json']);current={(r['machine'],r['stage']):r for r in records};datex=obs['observed_date'];oid=obs['id'];new_events=[]
            # close vanished nonterminal instances
            for pair in sorted(set(active)-set(current)):
                r=active.pop(pair);e=dict(r);e.update(type='C',closure_date=datex,status='Cerrada',observed_date=datex,observation_id=oid);new_events.append(e)
            # open new memberships
            for pair in sorted(set(current)-set(active)):
                raw=current[pair];src=sources[pair[1]]
                if src.get('terminal'):
                    if pair in terminal_seen:continue
                    terminal_seen.add(pair);inst=str(uuid.uuid4());base=dict(raw,instance=inst,opening_date=datex,stage_name=src['name'],kind=src['kind'],target=None,calendar=cfg['calendar'])
                    new_events.append(dict(base,type='A',closure_date=None,status='Abierta',observed_date=datex,observation_id=oid))
                    new_events.append(dict(base,type='C',closure_date=datex,status='Cerrada',observed_date=datex,observation_id=oid))
                else:
                    inst=str(uuid.uuid4());r=dict(raw,instance=inst,opening_date=datex,stage_name=src['name'],kind=src['kind'],target=src.get('target'),calendar=cfg['calendar'],status='Abierta');active[pair]=r
                    new_events.append(dict(r,type='A',closure_date=None,observed_date=datex,observation_id=oid))
            events.extend(new_events);states.append((obs,new_events,[dict(r,observed_currently=(p in current)) for p,r in active.items()],records))
        return {'events':events,'states':states}
    def _write_derived(self,d,version):
        self.db.execute('delete from events')
        for e in d['events']:
            self.db.execute('insert into events(id,observation_id,machine,stage,instance,type,payload) values(?,?,?,?,?,?,?)',(str(uuid.uuid4()),e['observation_id'],e['machine'],e['stage'],e['instance'],e['type'],json.dumps(e,ensure_ascii=False)))
        for obs,ev,effective,records in d['states']:
            summary=json.loads(obs['summary_json']);summary.update({'Aperturas':sum(x['type']=='A' for x in ev),'Cierres':sum(x['type']=='C' for x in ev),'Sin nuevos eventos':len({r['machine'] for r in records}-{x['machine'] for x in ev}),'Resultado':'Reconstruida con reglas v'+str(version)})
            self.db.execute('update observations set effective_json=?,summary_json=?,rules_version=? where id=?',(json.dumps(effective,ensure_ascii=False),json.dumps(summary,ensure_ascii=False),version,obs['id']))
    def instances(self, events=None):
        latest=self.db.execute('select observed_date from observations order by observed_date desc,seq desc limit 1').fetchone()
        asof=latest['observed_date'] if latest else date.today().isoformat();by={}
        for event in (self.events() if events is None else events):
            by[event['instance']]=dict(event)
        # Solo el último evento de cada instancia se presenta, como en el original.
        for r in by.values():
            r['elapsed']=workdays(r['opening_date'],r.get('closure_date') or asof,r['calendar'])
            r['consumption']=r['elapsed']/r['target']*100 if r.get('target') else None
        return list(by.values())
    def matrix(self):
        obs=self.db.execute('select observed_date,records_json from observations order by observed_date,seq').fetchall()
        dates=[o['observed_date'] for o in obs];presence=set();machines=set();cells={}
        for o in obs:
            for r in json.loads(o['records_json']):presence.add((r['machine'],o['observed_date']));machines.add(r['machine'])
        for e in self.events():cells.setdefault((e['machine'],e['observed_date']),[]).append(e['stage']+e['type'])
        return [{'Documento de ventas':m,**{d:' · '.join(cells[(m,d)]) if (m,d) in cells else ('—' if (m,d) in presence else 'Sin observación') for d in dates}} for m in sorted(machines)]

def public(rows):
    names={'machine':'Documento de ventas','stage':'ID etapa','stage_name':'Etapa PROOF','type':'Evento','opening_date':'Apertura observada','closure_date':'Cierre observado','status':'Estado','observed_date':'Fecha observación','elapsed':'Días laborables','consumption':'Consumo objetivo (%)'};vals={'A':'Apertura','C':'Cierre'}
    return [{names[k]:vals.get(v,v) for k,v in r.items() if k in names} for r in rows]
def export_excel(e):
    w=openpyxl.Workbook();w.remove(w.active);sets={'Observaciones':[json.loads(o['summary_json']) for o in e.observations()],'Eventos':public(e.events()),'Instancias':public(e.instances()),'Matriz histórica':e.matrix()}
    for name,rows in sets.items():
        s=w.create_sheet(name)
        if not rows:s.append(['Sin datos']);continue
        h=list(dict.fromkeys(k for r in rows for k in r));s.append(h)
        for r in rows:s.append([r.get(k) for k in h])
        s.freeze_panes='A2';s.auto_filter.ref=s.dimensions
    out=io.BytesIO();w.save(out);return out.getvalue()
