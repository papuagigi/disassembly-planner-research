"""S4 SKILL.md writer and same-assembly memory writer (evaluated model writes; Claude only prepares evidence).

Writer: gpt-6-luna / low via CodexCLIProvider (same as v6's document proposal step).
Input: the deterministic mining bundle (mine.py) + the retired S3 documents with their
measured yield. Output: LLM-readable SKILL.md documents. Static gates: valid frontmatter,
size, required sections, and no CAD IDs / part numbers / reference sequences.
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

from .common import ROOT, WORKSPACE, V6, read, write, utc, sha

CODEX_DIR = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS'
SCHEMA = {'type': 'object', 'properties': {
    'documents': {'type': 'array', 'minItems': 1, 'maxItems': 2, 'items': {'type': 'object', 'properties': {
        'name': {'type': 'string'}, 'description': {'type': 'string'}, 'markdown_body': {'type': 'string'}},
        'required': ['name', 'description', 'markdown_body'], 'additionalProperties': False}}},
    'required': ['documents'], 'additionalProperties': False}
REQUIRED_SECTIONS = ('## Triggers', '## Procedure', '## CODE application', '## GRAPH_DFS application', '## Evidence', '## Limits')

S4_PROMPT = '''You are improving the procedural memory of a CAD disassembly planner. The planner removes parts one at a
time along six straight labelled directions; a trusted checker validates the swept path (source-mesh collision) and
then MuJoCo checks that the remainder is stable. Budgets per episode: 240 checks, 900 s, 8 model calls. Planners:
CODE (an LLM writes a Python search program using an API with an exact-state search ledger, checkpoints, restores,
a cache that answers exact repeats of rejected checks for free) and GRAPH_DFS (an LLM ranks candidate actions; a
fixed host DFS executes them, asking for a new ranking when it is stuck at a state).

Write 1 or 2 SKILL.md procedures that make BOTH planners reach full disassembly with fewer wasted checks.
Base every rule ONLY on the measured statistics below (all recorded queries of development episodes, not a
cherry-picked subset). Quote the numbers you rely on in an "## Evidence" section. Prefer a few concrete, checkable
rules with an explicit ordering over general advice. Rules must be general: never mention CAD names, numeric
assembly IDs, specific part numbers or a fixed removal sequence.

The previous documents (shown below) were measured as low-yield: after a collision, another direction of the SAME
part was accepted only 4% (v6 traces) to 23% (v7 traces) of the time, while most blocked parts were blocked in every
tested direction. Replace or correct their advice where the data disagree.

Each document body must contain these sections, in order: "## Triggers", "## Procedure" (numbered steps),
"## CODE application" (how a generated program should order/skip/resume, may include a short pseudo-code loop),
"## GRAPH_DFS application" (how to rank candidate actions), "## Evidence", "## Limits".
Return JSON {"documents":[{"name": kebab-case, "description": one sentence, "markdown_body": markdown}]}.
Do not use tools, files or browsing.

MEASURED STATISTICS (development only):
'''


def provider(log_dir):
    os.environ['PATH'] = CODEX_DIR + os.pathsep + os.environ.get('PATH', '')
    sys.path.insert(0, str(WORKSPACE / 'disassembly_planner_2d'))
    from planner2d.llm import CodexCLIProvider
    from .contracts import MODEL, EFFORT
    return CodexCLIProvider(log_dir, model=MODEL, reasoning_effort=EFFORT, timeout=120)


def static_gate(name, description, body, forbidden_ids):
    problems = []
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,63}', name):
        problems.append('bad name')
    for s in REQUIRED_SECTIONS:
        if s not in body:
            problems.append('missing section ' + s)
    text = name + description + body
    for cid in forbidden_ids:
        if cid in text:
            problems.append('mentions CAD id ' + cid)
    if re.search(r'\bpart(?:s)?\s+#?\d+\b', text, re.I):
        problems.append('mentions a numbered part')
    if len(text.encode()) > 19000 or len(body) < 400:
        problems.append('size')
    return problems


def write_bank(bundle_path, version='S4', candidate_dir=None, forbidden_ids=()):
    from disassembly_final_v6.documents import DocumentBank, materialize, make_bank
    bundle = read(bundle_path)
    old = DocumentBank(V6 / 'memory/S3.json')
    prompt = S4_PROMPT + json.dumps({k: v for k, v in bundle.items() if k != 'episodes'}, ensure_ascii=False) + \
        '\n\nEPISODE OUTCOMES:\n' + json.dumps(bundle['episodes'], ensure_ascii=False) + \
        '\n\nPREVIOUS DOCUMENTS (retire or correct):\n' + json.dumps(old.documents, ensure_ascii=False)
    log = ROOT / 'outputs/skill_writer' / version
    p = provider(log)
    response, meta = p.complete(prompt, SCHEMA, len(list(log.glob('call_*'))) + 1 if log.exists() else 1)
    docs, report = [], []
    folder = Path(candidate_dir or (ROOT / 'memory' / version))
    for d in response['documents']:
        problems = static_gate(d['name'], d['description'], d['markdown_body'], forbidden_ids)
        report.append(dict(name=d['name'], problems=problems))
        if not problems:
            docs.append(materialize(folder, d['name'], d['description'], d['markdown_body']))
    result = dict(utc=utc(), version=version, usage=meta.get('usage'), gate=report, admitted_to_candidate_bank=[str(x) for x in docs],
                  bundle_sha256=sha(bundle_path), writer='gpt-6-luna/low via CodexCLIProvider')
    if docs:
        make_bank(ROOT / 'memory' / (version + '.json'), docs, version=version,
                  evidence=dict(bundle=str(bundle_path), bundle_sha256=sha(bundle_path), status='candidate_pending_validation'))
    write(ROOT / 'outputs/skill_writer' / (version + '_report.json'), result)
    return result


NOTE_PROMPT = '''You are writing an assembly-specific memory note for a CAD disassembly planner that will meet THIS SAME
assembly again (same geometry fingerprint). The note is shown only when that exact assembly is seen again.
Use ONLY the planner's own first-attempt records below (no reference solutions exist in them). Summarize, as concrete
checkable guidance: which removals (part id + direction label) were accepted and in which order, which parts were
blocked in many directions at the start, which directions never worked, where checks or time were wasted, and the
best order to try next time. Part ids ARE allowed here because the note is specific to this assembly.
Sections required: "## Triggers", "## Procedure", "## CODE application", "## GRAPH_DFS application", "## Evidence", "## Limits".
Return JSON {"documents":[{"name": kebab-case, "description": one sentence, "markdown_body": markdown}]} with exactly one document.
Do not use tools, files or browsing.

FIRST-ATTEMPT RECORDS:
'''


def attempt_summary(result_path):
    r = read(result_path)
    tr = r.get('trace', [])
    acc = [dict(part_id=t['part_id'], direction=t['direction'], check=t['checker_call']) for t in tr if t.get('committed')]
    rej = {}
    for t in tr:
        if not t.get('valid'):
            rej.setdefault(t['part_id'], set()).add(t['direction'])
    return dict(condition=r.get('condition'), success=bool(r.get('success')), termination=r.get('termination'),
                checks=len(tr), removed=len(r.get('actions', [])), required=r.get('required_removals'),
                final_removal_sequence=[dict(part_id=a['part_id'], direction=a['direction']) for a in r.get('actions', [])],
                accepted_removals_in_time_order=acc,
                rejected_directions_by_part={k: sorted(v) for k, v in rej.items()},
                elapsed_seconds=round(r.get('elapsed_seconds', 0)),
                direction_vectors_world=(r.get('initial_observation') or {}).get('direction_vectors_world'))


def write_note(case_id, attempt_paths, out_bank, base_bank_path):
    """One assembly memory note + a bank = base documents + the note (B/C retry condition)."""
    from disassembly_final_v6.documents import DocumentBank, materialize, make_bank
    summaries = [attempt_summary(p) for p in attempt_paths]
    prompt = NOTE_PROMPT + json.dumps(summaries, ensure_ascii=False)
    log = ROOT / 'outputs/note_writer' / case_id
    response, meta = provider(log).complete(prompt, SCHEMA, 1)
    d = response['documents'][0]
    problems = [p for p in static_gate(d['name'], d['description'], d['markdown_body'], ()) if p != 'mentions a numbered part']
    folder = ROOT / 'memory/notes' / case_id
    note = materialize(folder, d['name'], d['description'], d['markdown_body']) if not problems else None
    base = DocumentBank(base_bank_path)
    docs = [(Path(base_bank_path).parent / row['path']).resolve() for row in base.manifest['skills']]
    if note:
        docs.append(note)
    make_bank(out_bank, docs, version=Path(out_bank).stem,
              evidence=dict(case_id=case_id, first_attempts=[str(p) for p in attempt_paths], note_problems=problems))
    write(ROOT / 'outputs/note_writer' / (case_id + '_report.json'),
          dict(utc=utc(), case_id=case_id, usage=meta.get('usage'), problems=problems, note=str(note) if note else None,
               inputs=[str(p) for p in attempt_paths]))
    return note, problems
