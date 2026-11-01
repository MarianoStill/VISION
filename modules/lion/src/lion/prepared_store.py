"""Resultado LION persistente en JSON comprimido, sin pickle ni ejecución de código.

Caché derivada externa. Fallos de lectura/escritura nunca sustituyen el cálculo LION.
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
import hashlib
import json
import math
import os
import platform
import tempfile
import zlib
import numpy as np
import pandas as pd
import openpyxl

FORMAT = 1
MAX_BYTES = 512 * 1024 * 1024
_DTYPES = {'object','bool','int8','int16','int32','int64','uint8','uint16','uint32','uint64',
           'float32','float64','datetime64[ns]','datetime64[us]','datetime64[ms]','datetime64[s]',
           'timedelta64[ns]','timedelta64[us]','timedelta64[ms]','timedelta64[s]'}


def _pack(value):
    if value is None or isinstance(value,(str,bool,int)):
        return value
    if value is pd.NaT:return {'t':'nat'}
    if value is pd.NA:return {'t':'na'}
    if isinstance(value,pd.Timestamp):return {'t':'timestamp','v':value.isoformat()}
    if isinstance(value,pd.Timedelta):return {'t':'timedelta','v':value.value}
    if isinstance(value,datetime):return {'t':'datetime','v':value.isoformat()}
    if isinstance(value,date):return {'t':'date','v':value.isoformat()}
    if isinstance(value,np.generic):return _pack(value.item())
    if isinstance(value,float):
        if math.isnan(value):return {'t':'float','v':'nan'}
        if math.isinf(value):return {'t':'float','v':'inf' if value>0 else '-inf'}
        return value
    if isinstance(value,pd.DataFrame):
        dtypes=[str(dtype) for dtype in value.dtypes]
        if any(dtype not in _DTYPES for dtype in dtypes):raise TypeError('dtype no soportado')
        return {'t':'frame','columns':_pack(list(value.columns)),'column_name':_pack(value.columns.name),
                'index':_pack(value.index),'dtypes':dtypes,
                'data':[_pack(value.iloc[:,i].tolist()) for i in range(len(value.columns))],
                'attrs':_pack(value.attrs)}
    if isinstance(value,pd.RangeIndex):
        return {'t':'range','start':value.start,'stop':value.stop,'step':value.step,'name':_pack(value.name)}
    if isinstance(value,pd.Index):
        dtype=str(value.dtype)
        if dtype not in _DTYPES:raise TypeError('indice no soportado')
        return {'t':'index','values':_pack(value.tolist()),'dtype':dtype,'name':_pack(value.name)}
    if isinstance(value,tuple):return {'t':'tuple','v':[_pack(v) for v in value]}
    if isinstance(value,list):return [_pack(v) for v in value]
    if isinstance(value,dict):
        frames=list(value.values())
        if frames and all(isinstance(frame,pd.DataFrame) for frame in frames):
            first=frames[0]
            if all(frame.columns.equals(first.columns) and frame.dtypes.equals(first.dtypes) for frame in frames):
                combined=pd.concat(frames,ignore_index=True)
                return {'t':'frame_dict','keys':_pack(list(value)), 'frame':_pack(combined),
                        'indices':[_pack(frame.index) for frame in frames],
                        'attrs':[_pack(frame.attrs) for frame in frames]}
        return {'t':'dict','v':[[_pack(k),_pack(v)] for k,v in value.items()]}
    raise TypeError('Tipo no soportado en resultado preparado')


def _unpack(value):
    if isinstance(value,list):return [_unpack(v) for v in value]
    if not isinstance(value,dict):return value
    tag=value.get('t')
    if tag=='nat':return pd.NaT
    if tag=='na':return pd.NA
    if tag=='float':return {'nan':float('nan'),'inf':float('inf'),'-inf':float('-inf')}[value['v']]
    if tag=='timestamp':return pd.Timestamp(value['v'])
    if tag=='timedelta':return pd.Timedelta(value['v'],unit='ns')
    if tag=='datetime':return datetime.fromisoformat(value['v'])
    if tag=='date':return date.fromisoformat(value['v'])
    if tag=='tuple':return tuple(_unpack(v) for v in value['v'])
    if tag=='dict':return {_unpack(k):_unpack(v) for k,v in value['v']}
    if tag=='frame_dict':
        keys=_unpack(value['keys']);combined=_unpack(value['frame']);result={};offset=0
        if len(keys)!=len(value['indices']) or len(keys)!=len(value['attrs']):raise ValueError('detalles incompletos')
        for key,encoded_index,attrs in zip(keys,value['indices'],value['attrs']):
            index=_unpack(encoded_index);stop=offset+len(index)
            if stop>len(combined):raise ValueError('detalles incompatibles')
            frame=combined.iloc[offset:stop].copy();frame.index=index;frame.attrs=_unpack(attrs)
            result[key]=frame;offset=stop
        if offset!=len(combined):raise ValueError('detalles sobrantes')
        return result
    if tag=='range':return pd.RangeIndex(value['start'],value['stop'],value['step'],name=_unpack(value['name']))
    if tag=='index':
        if value['dtype'] not in _DTYPES:raise ValueError('dtype no admitido')
        return pd.Index(_unpack(value['values']),dtype=value['dtype'],name=_unpack(value['name']))
    if tag=='frame':
        columns=_unpack(value['columns']);index=_unpack(value['index'])
        if len(columns)!=len(value['dtypes']) or len(columns)!=len(value['data']):raise ValueError('frame incompleto')
        data={}
        casts={}
        for position,(dtype,encoded) in enumerate(zip(value['dtypes'],value['data'])):
            if dtype not in _DTYPES:raise ValueError('dtype no admitido')
            values=_unpack(encoded)
            if len(values)!=len(index):raise ValueError('filas incompatibles')
            data[position]=values
            if dtype!='object':casts[position]=dtype
        frame=pd.DataFrame(data,dtype=object) if data else pd.DataFrame(index=range(len(index)))
        if casts:frame=frame.astype(casts)
        frame.columns=pd.Index(columns,name=_unpack(value['column_name']))
        frame.index=index;frame.attrs=_unpack(value['attrs'])
        return frame
    raise ValueError('Tipo de cache no admitido')


def cache_directory():
    if os.environ.get('CO_VISION_LION_CACHE','1').strip()=='0':return None
    root=Path(os.environ.get('CO_VISION_DATA_ROOT') or Path.home()/'CO-VISION-data').expanduser().resolve()
    if any((parent/'.git').exists() for parent in (root,*root.parents)):
        return None  # No guardar datos derivados dentro de un repositorio.
    return root/'lion'/'prepared'


def cache_identity(content,reference_date,source,engine_path):
    engine=Path(engine_path)
    return dict(format=FORMAT,source_sha256=hashlib.sha256(content).hexdigest(),
                reference_date=pd.Timestamp(reference_date).date().isoformat(),source=str(source),
                engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                codec_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                pandas=pd.__version__,numpy=np.__version__,openpyxl=openpyxl.__version__,
                python=platform.python_version())


def cache_path(identity):
    directory=cache_directory()
    if directory is None:return None
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return directory/(key+'.lionjson.z')


def load_prepared(identity):
    try:
        path=cache_path(identity)
        if path is None or not path.is_file() or path.stat().st_size>MAX_BYTES:return None
        compressed=path.read_bytes()
        decoder=zlib.decompressobj()
        raw=decoder.decompress(compressed,MAX_BYTES+1)
        if len(raw)>MAX_BYTES or not decoder.eof or decoder.unused_data:return None
        envelope=json.loads(raw)
        if envelope.get('identity')!=identity:return None
        payload=envelope['payload']
        encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        if hashlib.sha256(encoded).hexdigest()!=envelope['payload_sha256']:return None
        result=_unpack(payload)
        if not isinstance(result,tuple) or len(result)!=5:return None
        model,details,issues,mtime,sheet=result
        if not isinstance(model,pd.DataFrame) or not isinstance(details,dict) or not isinstance(issues,pd.DataFrame):return None
        if not all(isinstance(frame,pd.DataFrame) for frame in details.values()):return None
        if model.attrs.get('source_sha256')!=identity['source_sha256']:return None
        if model.attrs.get('urgency_reference')!=identity['reference_date']:return None
        return result
    except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,zlib.error,RecursionError):
        return None


def save_prepared(identity,result):
    temporary=None
    try:
        path=cache_path(identity)
        if path is None:return False
        payload=_pack(result)
        encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        if len(encoded)>MAX_BYTES:return False
        envelope=dict(identity=identity,payload_sha256=hashlib.sha256(encoded).hexdigest(),payload=payload)
        raw=json.dumps(envelope,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        if len(raw)>MAX_BYTES:return False
        compressed=zlib.compress(raw,level=1)
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as handle:
            temporary=Path(handle.name);handle.write(compressed);handle.flush();os.fsync(handle.fileno())
        try:temporary.chmod(0o600)
        except OSError:pass
        os.replace(temporary,path)
        return True
    except (OSError,ValueError,TypeError,KeyError,OverflowError,RecursionError):
        return False
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
