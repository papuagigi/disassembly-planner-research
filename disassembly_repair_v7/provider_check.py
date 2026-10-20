"""One minimal availability call to the evaluated provider (no planning content)."""
import json, os, sys, time
from pathlib import Path
CODEX_DIR = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS'
os.environ['PATH'] = CODEX_DIR + os.pathsep + os.environ.get('PATH', '')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'disassembly_planner_2d'))
from planner2d.llm import CodexCLIProvider
from disassembly_repair_v7.common import ROOT, utc, write
log = ROOT / 'outputs/provider_check' / time.strftime('%Y%m%dT%H%M%S')
p = CodexCLIProvider(log, model='gpt-6-luna', reasoning_effort='low', timeout=120)
schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False}
t = time.monotonic()
try:
    response, meta = p.complete('Availability check only. Return {"ok": true}.', schema, 1)
    out = dict(utc=utc(), status='AVAILABLE', response=response, usage=meta.get('usage'), seconds=time.monotonic() - t,
               requested_model=meta.get('requested_model'), executable=p.executable)
except Exception as e:
    out = dict(utc=utc(), status='UNAVAILABLE', error=repr(e)[:2000], seconds=time.monotonic() - t, executable=p.executable)
write(ROOT / 'outputs/provider_check/latest.json', out)
print(json.dumps(out, ensure_ascii=False))
