"""S4 SKILL.md writer and same-assembly memory writer (evaluated model writes; Claude only prepares evidence).

Writer: gpt-6-luna / low via CodexCLIProvider (same as v6's document proposal step).
Input: the deterministic mining bundle (mine.py) + the retired S3 documents with their
measured yield. Output: LLM-readable SKILL.md documents. Static gates: valid frontmatter,
size, required sections, and no CAD IDs / part numbers / reference sequences.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from .common import ROOT, V6, read, write, utc, sha

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
    # H5: web search disabled (S4a/S4b were written before H5 with planner2d's CodexCLIProvider)
    from .provider import NoWebSearchCodexProvider
    from .contracts import MODEL, EFFORT
    return NoWebSearchCodexProvider(log_dir, model=MODEL, reasoning_effort=EFFORT, timeout=120)


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
Use ONLY the planner's own first-attempt records below (no reference solutions exist in them). Part ids ARE allowed.
The host will append a "## Recorded sequence" block copied verbatim from the records (the most complete committed path:
a full successful path if any attempt succeeded, otherwise the longest partial path). Do not rewrite that block; refer to it.
Write concrete, checkable guidance:
- how to use the recorded sequence first, and what to do if a step is rejected or the sequence is partial;
- which parts were blocked in many directions at the start and which became removable later (and after what);
- which direction labels never worked, stated with their WORLD vectors (labels are names; world +z is up);
- where checks or wall time were wasted (e.g. slow unstable checks, broad six-direction sweeps, repeated loops);
- if NO attempt succeeded: the most promising untested actions at the deepest recorded state and the blockers to clear.
Sections required: "## Triggers", "## Procedure", "## CODE application", "## GRAPH_DFS application", "## Evidence", "## Limits".
Return JSON {"documents":[{"name": "assembly-note-<short-kebab-case>", "description": one sentence,
"markdown_body": markdown}]} with exactly one document. Do not use tools, files or browsing.

FIRST-ATTEMPT RECORDS:
'''
NOTE_PREFIX = 'assembly-note-'


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


def recorded_sequence(attempt_paths):
    """Most complete committed path in the records: fewest-check success, else the longest final path (host-side copy)."""
    runs = []
    for p in attempt_paths:
        r = read(p)
        runs.append(dict(condition=r.get('condition'), success=bool(r.get('success')), checks=len(r.get('trace', [])),
                         actions=[(a['part_id'], a['direction']) for a in r.get('actions', [])], required=r.get('required_removals'),
                         vectors=(r.get('initial_observation') or {}).get('direction_vectors_world') or {}))
    best = min(runs, key=lambda x: (not x['success'], -len(x['actions']), x['checks']))
    head = (f"Source: first-attempt condition {best['condition']}, {'complete success' if best['success'] else 'PARTIAL (no attempt succeeded)'}, "
            f"{len(best['actions'])} of {best['required']} required removals, copied verbatim from that episode's final committed path "
            f"(planner's own record, not a reference solution).")
    lines = [f"{i}. part `{pid}` direction `{d}` (world {[round(x, 3) for x in best['vectors'].get(d, [])]})"
             for i, (pid, d) in enumerate(best['actions'], 1)]
    return '\n\n## Recorded sequence\n\n' + head + '\n\n' + '\n'.join(lines or ['(no committed removal in any attempt)']) + '\n', best


def write_note(case_id, attempt_paths, out_bank, base_bank_path):
    """One assembly memory note + a bank = base documents + the note (B/C retry condition).
    v7.3: name prefix assembly-note-, host-appended verbatim Recorded sequence block, failure-only guidance."""
    from disassembly_final_v6.documents import DocumentBank, materialize, make_bank
    summaries = [attempt_summary(p) for p in attempt_paths]
    block, best = recorded_sequence(attempt_paths)
    prompt = NOTE_PROMPT + json.dumps(summaries, ensure_ascii=False) + '\n\nHOST BLOCK THAT WILL BE APPENDED:' + block
    log = ROOT / 'outputs/note_writer' / case_id
    response, meta, writer_errors = None, {}, []
    for index in (1, 2):   # one retry of the writer call; if both fail the bank holds the base documents only
        try:
            response, meta = provider(log).complete(prompt, SCHEMA, index)
            break
        except Exception as exc:  # ProviderError, timeout or malformed output
            writer_errors.append(f'{type(exc).__name__}: {str(exc)[:300]}')
    folder = ROOT / 'memory/notes' / case_id
    if response is None:   # host-only fallback: the verbatim record block with fixed section text (reported)
        d = dict(name=NOTE_PREFIX + 'recorded-path', description='Recorded committed path of earlier attempts on this exact assembly.',
                 markdown_body=FALLBACK_NOTE_BODY)
        problems = ['note_writer_failed_host_block_only']
    else:
        d = dict(response['documents'][0])
        problems = []
    if not d['name'].startswith(NOTE_PREFIX):
        d['name'] = NOTE_PREFIX + d['name']
        problems.append('name_prefixed_by_host')
    d['markdown_body'] = d['markdown_body'].rstrip() + block
    gate = [p for p in static_gate(d['name'][:63], d['description'], d['markdown_body'], ()) if p != 'mentions a numbered part']
    problems += gate
    note = materialize(folder, d['name'][:63], d['description'], d['markdown_body']) if not gate else None
    base = DocumentBank(base_bank_path)
    docs = [(Path(base_bank_path).parent / row['path']).resolve() for row in base.manifest['skills']]
    if note:
        docs.append(note)
    make_bank(out_bank, docs, version=Path(out_bank).stem,
              evidence=dict(case_id=case_id, first_attempts=[str(p) for p in attempt_paths], note_problems=problems))
    write(ROOT / 'outputs/note_writer' / (case_id + '_report.json'),
          dict(utc=utc(), case_id=case_id, usage=meta.get('usage'), problems=problems, note=str(note) if note else None,
               writer_errors=writer_errors, inputs=[str(p) for p in attempt_paths],
               recorded_sequence_source=dict(condition=best['condition'], success=best['success'], length=len(best['actions']))))
    return note, problems


FALLBACK_NOTE_BODY = '''## Triggers
Use only when this exact assembly (same geometry fingerprint) is seen again.

## Procedure
1. Try the Recorded sequence below in order, checking each step at the current state.
2. If a step is rejected, keep the removals already made and continue with general procedures from that state.

## CODE application
Encode the Recorded sequence as a list and try it before any generic search loop.

## GRAPH_DFS application
At each state rank the next Recorded sequence action first.

## Evidence
Copied from the planner's own first-attempt records by the host because the note writer call failed.

## Limits
A partial sequence (if marked PARTIAL) ends before full disassembly; the remaining parts need search.
'''


S5_PROMPT = '''You are improving the procedural memory (SKILL.md documents) of a CAD disassembly planner. The planner removes
parts one at a time along six straight LABELLED directions; labels are names only, and each episode reports their world
vectors in observation.direction_vectors_world (world +z is up). A trusted checker validates the swept path, then MuJoCo
checks that the remainder is stable. Budgets per episode: 240 charged checks, 900 s, 8 model calls.
Two planners read the same documents:
- CODE: an LLM writes one Python program per turn against the API contract quoted below (restricted Python).
- GRAPH_DFS: an LLM ranks candidate actions; a fixed host DFS executes the ranking and asks again when stuck.

Write 1 or 2 SKILL.md documents that make BOTH planners fully disassemble assemblies they have NEVER seen, with few
wasted checks and little wall time. Base every rule ONLY on the development evidence below; quote the numbers you rely on
in "## Evidence". Required sections in each document, in order: "## Triggers", "## Procedure" (numbered steps),
"## CODE application", "## GRAPH_DFS application", "## Evidence", "## Limits". Exactly one document must also contain
"## Reference implementation" (after "## CODE application") with ONE fenced ```python block: a complete program that
defines def run(api): and ends with the line run(api), valid under the CODE contract below, that performs the whole
procedure by itself (a CODE planner may copy it unchanged). The host tests that program WITHOUT any model on development
assemblies; its results come back to you if it fails.
Requirements from the evidence:
- Reason in WORLD families (up / lateral / down via direction_vectors_world), never in label names.
- Discover the assembly's working family instead of assuming one; then prefer the family of the latest accepted removal.
- Never spend early checks on families the evidence shows to be useless; defer parts that were rejected repeatedly at the
  same exact state; never re-request an action already rejected at the current exact state.
- Account for check cost (unstable_remainder checks are far slower than path collisions).
- Use the search ledger, checkpoints and restore when a state is a known dead end.
- If an exact-assembly note (skill id starting with "assembly-note-") is loaded, its Recorded sequence comes first.
- Distill cross-assembly patterns from the same-assembly notes; never copy their part ids or sequences.
Never mention CAD names, numeric assembly IDs, specific part numbers or a fixed removal sequence.
Return JSON {"documents":[{"name": kebab-case, "description": one sentence, "markdown_body": markdown}]}.
Do not use tools, files or browsing.

CODE CONTRACT (exactly what CODE planners see):
'''
S5_SECTION = '## Reference implementation'
S5_MAX_BYTES = 24000


def reference_code(markdown):
    m = re.search(r'## Reference implementation.*?```python\n(.*?)```', markdown, re.S)
    return m.group(1) if m else None


def s5_gate(documents, forbidden_ids):
    problems, code = [], None
    for d in documents:
        p = [x for x in static_gate(d['name'], d['description'], d['markdown_body'], forbidden_ids) if x != 'size']
        if len((d['name'] + d['description'] + d['markdown_body']).encode()) > S5_MAX_BYTES:
            p.append('size')
        problems += [d['name'] + ': ' + x for x in p]
        if S5_SECTION in d['markdown_body']:
            code = code or reference_code(d['markdown_body'])
    if code is None:
        problems.append('no Reference implementation python block')
    else:
        from .runtime import compile_restricted
        try:
            compile_restricted(code)
        except Exception as exc:
            problems.append(f'reference implementation rejected by the restricted runtime: {type(exc).__name__}: {str(exc)[:400]}')
    return problems, code


def write_s5(bundle_path, forbidden_ids, max_calls=3):
    """S5: writer -> static/compile gate -> model-free rule gate on the S5 input CADs -> feedback (<= max_calls writer calls)."""
    from disassembly_final_v6.documents import DocumentBank, materialize, make_bank
    from .contracts import COMMON, CODE_SPEC
    from .learning73 import gate
    bundle = read(bundle_path)
    evidence = {k: v for k, v in bundle.items() if k not in ('episodes', 'input_paths', 'anonymized_examples')}
    old = DocumentBank(ROOT.parent / 'disassembly_repair_v7_2/memory/S4b.json')
    base = (S5_PROMPT + COMMON + CODE_SPEC + '\n\nDEVELOPMENT EVIDENCE (all recorded queries; same-assembly notes as examples):\n'
            + json.dumps(evidence, ensure_ascii=False) + '\n\nPREVIOUS GENERAL DOCUMENTS (S4b; correct them where the evidence disagrees):\n'
            + json.dumps(old.documents, ensure_ascii=False))
    log = ROOT / 'outputs/skill_writer/S5'
    history, chosen = [], None
    for call in range(1, max_calls + 1):
        prompt = base
        if history:
            prompt += '\n\nYOUR PREVIOUS ATTEMPTS AND THEIR TEST RESULTS (fix the causes):\n' + json.dumps(
                [dict(documents=h['documents'], static_and_compile_problems=h['problems'], rule_gate=h.get('gate')) for h in history],
                ensure_ascii=False)
        try:
            response, meta = provider(log).complete(prompt, SCHEMA, call)
        except Exception as exc:
            history.append(dict(call=call, documents=[], problems=[f'writer error {type(exc).__name__}: {str(exc)[:300]}']))
            continue
        docs = response['documents']
        problems, code = s5_gate(docs, forbidden_ids)
        row = dict(call=call, documents=docs, problems=problems, usage=meta.get('usage'))
        if not problems:
            row['gate'] = gate(code)
        history.append(row)
        write(ROOT / 'outputs/skill_writer/S5_report.json', dict(utc=utc(), bundle_sha256=sha(bundle_path), attempts=history))
        if not problems and row['gate']['passed']:
            chosen = row
            break
    if chosen is None:   # pre-registered fallback: the attempt with most gate successes (then fewest total checks)
        scored = [h for h in history if h.get('gate')]
        if scored:
            chosen = max(scored, key=lambda h: (h['gate']['successes'], -sum(r['checks'] for r in h['gate']['rows'])))
    if chosen:
        folder = ROOT / 'memory/S5'
        paths = [materialize(folder, d['name'], d['description'], d['markdown_body']) for d in chosen['documents']]
        make_bank(ROOT / 'memory/S5.json', paths, version='S5',
                  evidence=dict(bundle=str(bundle_path), bundle_sha256=sha(bundle_path), writer_call=chosen['call'],
                                rule_gate_passed=chosen['gate']['passed'], rule_gate_successes=chosen['gate']['successes'],
                                status='candidate_pending_validation'))
    write(ROOT / 'outputs/skill_writer/S5_report.json', dict(utc=utc(), bundle_sha256=sha(bundle_path), attempts=history,
                                                               chosen_call=chosen['call'] if chosen else None,
                                                               writer='gpt-6-luna/low via NoWebSearchCodexProvider'))
    return chosen, history


S5_REFINE_NOTE = '''
REFINEMENT REQUEST: your best document so far passed the model-free test on most development assemblies but its
Reference implementation did not finish every one (rows below; "ended" says how each run stopped, and the end-state
facts are what a CODE planner would see next). Revise the document(s) so the program also completes the failing
assemblies without making the others worse. Keep every rule tied to the evidence; keep the required sections.
'''


def refine_s5(bundle_path, forbidden_ids, extra_calls=2):
    """Development-only refinement (added after the first S5 gate result, before any validation): up to extra_calls more
    writer calls with gate feedback; a revision replaces the current S5 only if its gate has more full disassemblies, or
    the same number with fewer total checks. The adopted version is written as memory/S5r.json (S5.json stays)."""
    from disassembly_final_v6.documents import DocumentBank, materialize, make_bank
    from .contracts import COMMON, CODE_SPEC
    from .learning73 import gate
    report = read(ROOT / 'outputs/skill_writer/S5_report.json')
    history = report['attempts']
    best = [h for h in history if h.get('call') == report['chosen_call']][0]
    bundle = read(bundle_path)
    evidence = {k: v for k, v in bundle.items() if k not in ('episodes', 'input_paths', 'anonymized_examples')}
    old = DocumentBank(ROOT.parent / 'disassembly_repair_v7_2/memory/S4b.json')
    base = (S5_PROMPT + COMMON + CODE_SPEC + '\n\nDEVELOPMENT EVIDENCE (all recorded queries; same-assembly notes as examples):\n'
            + json.dumps(evidence, ensure_ascii=False) + '\n\nPREVIOUS GENERAL DOCUMENTS (S4b; correct them where the evidence disagrees):\n'
            + json.dumps(old.documents, ensure_ascii=False))
    score = lambda h: (h['gate']['successes'], -sum(r['checks'] for r in h['gate']['rows']))  # noqa: E731
    log = ROOT / 'outputs/skill_writer/S5'
    refinements = []
    start = max(h['call'] for h in history) + 1
    for call in range(start, start + extra_calls):
        prompt = base + S5_REFINE_NOTE + json.dumps(dict(best_documents=best['documents'], best_rule_gate=best['gate'],
                                                         other_attempts=[dict(problems=h['problems'], rule_gate=h.get('gate'))
                                                                         for h in history + refinements if h is not best]),
                                                    ensure_ascii=False)
        try:
            response, meta = provider(log).complete(prompt, SCHEMA, call)
        except Exception as exc:
            refinements.append(dict(call=call, documents=[], problems=[f'writer error {type(exc).__name__}: {str(exc)[:300]}']))
            continue
        docs = response['documents']
        problems, code = s5_gate(docs, forbidden_ids)
        row = dict(call=call, documents=docs, problems=problems, usage=meta.get('usage'))
        if not problems:
            row['gate'] = gate(code)
        refinements.append(row)
        write(ROOT / 'outputs/skill_writer/S5_refine_report.json', dict(utc=utc(), base_call=report['chosen_call'], refinements=refinements))
        if not problems and row['gate']['passed'] and score(row) > score(best):
            best = row
            if row['gate']['successes'] == len(row['gate']['rows']):
                break
    adopted = best['call'] != report['chosen_call']
    if adopted:
        folder = ROOT / 'memory/S5r'
        paths = [materialize(folder, d['name'], d['description'], d['markdown_body']) for d in best['documents']]
        make_bank(ROOT / 'memory/S5r.json', paths, version='S5r',
                  evidence=dict(bundle=str(bundle_path), bundle_sha256=sha(bundle_path), writer_call=best['call'],
                                rule_gate_successes=best['gate']['successes'], refined_from_call=report['chosen_call'],
                                status='candidate_pending_validation'))
    write(ROOT / 'outputs/skill_writer/S5_refine_report.json', dict(utc=utc(), base_call=report['chosen_call'], refinements=refinements,
                                                                     adopted_call=best['call'], adopted=adopted,
                                                                     rule='replace only if more gate successes, or equal and fewer total checks'))
    return best, refinements
