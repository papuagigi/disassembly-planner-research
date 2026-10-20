"""Copy allowlisted v7 files into the public snapshot clone (no git operations here).

Follows collaboration_tools/publish_snapshot.py conventions: allowlist only, size
limit, secret-pattern hard fail, no raw CAD/meshes, no provider prompt/response
logs, no raw episode result.json, no outputs/ or data/ trees. Local absolute
paths are replaced by "<workspace>" in the public copy.

Groups (one or more commits each):
  code       v7 package source, data_tools, offline tools, tests
  docs       STATUS.md, CHANGELOG.md, analysis/*.md
  evidence   analysis json/csv, physics diagnostics, regression summaries,
             protocol/freeze/candidate/selection records  -> results/repair_v7/
  pilot      pilot metrics/aggregates when they exist      -> results/repair_v7/pilot/
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

from .common import ROOT, WORKSPACE

REPO = WORKSPACE / 'disassembly-planner-research'
SECRET = re.compile(r'\b(?:ghp_|github_pat_|sk-proj-|sk-ant-)[A-Za-z0-9_\-]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----')
MAX_BYTES = 4_000_000


def _public_text(source):
    text = Path(source).read_text(encoding='utf-8')
    assert not SECRET.search(text), source
    return text.replace(str(WORKSPACE), '<workspace>').replace(str(Path.home()), '<home>')


def _put(source, destination, written):
    source, destination = Path(source), Path(destination)
    assert source.is_file() and source.stat().st_size < MAX_BYTES, source
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_public_text(source), encoding='utf-8')
    written.append(str(destination.relative_to(REPO)))


def code(written):
    for p in sorted(ROOT.glob('*.py')):
        _put(p, REPO / 'disassembly_repair_v7' / p.name, written)
    for sub in ('data_tools', 'offline', 'tests'):
        for p in sorted((ROOT / sub).glob('*')):
            if p.suffix in ('.py', '.sh'):
                _put(p, REPO / 'disassembly_repair_v7' / sub / p.name, written)


def docs(written):
    for name in ('STATUS.md', 'CHANGELOG.md'):
        _put(ROOT / name, REPO / 'disassembly_repair_v7' / name, written)
    for p in sorted((ROOT / 'analysis').glob('*.md')):
        _put(p, REPO / 'results/repair_v7' / p.name, written)


def evidence(written):
    out = REPO / 'results/repair_v7'
    for p in sorted((ROOT / 'analysis').glob('*')):
        if p.suffix in ('.json', '.csv'):
            _put(p, out / p.name, written)
    for p in sorted((ROOT / 'analysis/physics').rglob('*')):
        if p.is_file() and p.suffix in ('.json', '.log') and p.stat().st_size < MAX_BYTES:
            _put(p, out / 'physics' / p.relative_to(ROOT / 'analysis/physics'), written)
    for p in sorted((ROOT / 'outputs/regression').glob('*/summary.json')):
        _put(p, out / 'regression' / (p.parent.name + '.json'), written)
    for p in sorted((ROOT / 'outputs/regression').glob('*/real_physics_replay_audit.json')):
        _put(p, out / 'regression' / (p.parent.name + '_real_physics_replay_audit.json'), written)
    for p in sorted((ROOT / 'outputs/protocol').glob('*.json')):
        _put(p, out / 'protocol' / p.name, written)
    for name in ('protection_check_latest.json',):
        if (ROOT / 'outputs' / name).exists():
            _put(ROOT / 'outputs' / name, out / name, written)
    for p in sorted((ROOT / 'outputs/diagnostics').glob('*/*.json')):
        if p.name != 'progress.json':
            _put(p, out / 'diagnostics' / p.parent.name / p.name, written)
    progress = ROOT / 'outputs/pilot_inputs/progress.json'
    if progress.exists():
        _put(progress, out / 'pilot_inputs_progress.json', written)


def pilot(written):
    out = REPO / 'results/repair_v7/pilot'
    for p in sorted((ROOT / 'outputs/pilot/trials').glob('*/*/metrics.json')):
        _put(p, out / 'metrics' / (p.parent.parent.name + '_' + p.parent.name + '.json'), written)
    for name in ('manifest.json', 'complete.json'):
        if (ROOT / 'outputs/pilot' / name).exists():
            _put(ROOT / 'outputs/pilot' / name, out / name, written)
    for name in ('index.json', 'audit.json'):
        if (ROOT / 'replay' / name).exists():
            _put(ROOT / 'replay' / name, out / ('replay_' + name), written)


def v72(written):
    """disassembly_repair_v7_2: code, docs, learned SKILL.md banks, protocol/decision records, summaries (no raw traces)."""
    base = ROOT.parent / 'disassembly_repair_v7_2'
    out = REPO / 'disassembly_repair_v7_2'
    if not base.exists():
        return
    for p in sorted(base.glob('*.py')) + sorted(base.glob('*.md')):
        _put(p, out / p.name, written)
    for sub in ('tests', 'offline'):
        for p in sorted((base / sub).glob('*')):
            if p.suffix in ('.py', '.sh'):
                _put(p, out / sub / p.name, written)
    for p in sorted((base / 'analysis').rglob('*')):
        if p.is_file() and p.suffix in ('.md', '.json', '.csv'):
            _put(p, REPO / 'results/repair_v7_2' / p.relative_to(base / 'analysis'), written)
    mem = base / 'memory'
    if mem.exists():
        for p in sorted(mem.rglob('*')):
            if p.is_file() and p.suffix in ('.md', '.json'):
                _put(p, REPO / 'results/repair_v7_2/memory' / p.relative_to(mem), written)
    o = base / 'outputs'
    for rel in ('protocol', 'validation', 'retry', 'smoke', 'skill_writer', 'note_writer', 'mining', 'collection'):
        d = o / rel
        if not d.exists():
            continue
        for p in sorted(d.rglob('*.json')):
            if (p.name in ('result.json', 'progress.json', 'job.json') or 'llm_calls' in p.parts
                    or any(part.startswith('call_') for part in p.parts) or p.stat().st_size >= MAX_BYTES):
                continue   # no raw traces and no provider prompt/response/metadata logs (writer calls included)
            _put(p, REPO / 'results/repair_v7_2/outputs' / p.relative_to(o), written)


GROUPS = dict(code=code, docs=docs, evidence=evidence, pilot=pilot, v72=v72)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('groups', nargs='+', choices=sorted(GROUPS))
    a = p.parse_args()
    written = []
    for g in a.groups:
        GROUPS[g](written)
    print('\n'.join(written))


if __name__ == '__main__':
    main()
