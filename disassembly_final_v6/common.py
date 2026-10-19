from __future__ import annotations
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data=json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.partial',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if exclusive:
            os.link(temporary,path)
        else:os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

def progress(phase, **details):
    row = dict(phase=phase, utc=utc(), **details)
    write(ROOT/'outputs/progress.json', row)
    with (ROOT/'outputs/journal.jsonl').open('a') as f:
        f.write(json.dumps(row, ensure_ascii=False)+'\n')
