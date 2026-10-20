"""v7.3 development evidence for the S5 writer (deterministic, no model call).

Input split fixed before S5 is written (see STATUS.md):
  S5 INPUT CADs (mining, notes, offline rule gate): 05902, 06146, 03012, 01613, 02402, plus the v6 final traces
  (05954, 06444, 03114).
  VALIDATION CADs (held out from S5 writing): 05459, 02406, 07375, 03674.
On top of the v7.2 all-query bundle (mine.py) this adds world-vector statistics: which world family (up / lateral /
down, from direction_vectors_world) removes parts per assembly, how often labels are remapped, whether the family of the
first accepted removal predicts later accepted removals, the wall-time cost of each check outcome, and how many checks
were spent before the first accepted removal. The four v7.2 same-assembly notes are attached as episodic examples.
"""
from __future__ import annotations
import collections
import glob
import statistics
from pathlib import Path

from .common import ROOT, WORKSPACE, V7, V72, read, write, utc
from .mine import mine

S5_INPUT_CADS = ('asap_05902', 'asap_06146', 'asap_03012', 'asap_01613', 'asap_02402')
VALIDATION_CADS = ('asap_05459', 'asap_02406', 'asap_07375', 'asap_03674')
UP = 0.7


def family(vec):
    return 'unknown' if not vec else ('up' if vec[2] > UP else ('down' if vec[2] < -UP else 'lateral'))


def input_results():
    paths = []
    for pat in ('outputs/collection/*/*/result.json', 'outputs/validation/*/*/result.json', 'outputs/retry/*/*/result.json'):
        paths += glob.glob(str(V72 / pat))
    paths += glob.glob(str(V7 / 'outputs/pilot/trials/*/*/result.json'))
    paths = [p for p in paths if any('/' + c + '/' in p for c in S5_INPUT_CADS)]
    paths += glob.glob(str(WORKSPACE / 'disassembly_final_v6/outputs/evaluation/trials/*/*/result.json'))
    for p in paths:
        assert not any('/' + c + '/' in p for c in VALIDATION_CADS), ('validation CAD leaked into S5 input', p)
    return sorted(paths)


def world_stats(paths):
    per_cad = collections.defaultdict(lambda: dict(accepted=collections.Counter(), tried=collections.Counter(), remapped=None))
    persistence = [0, 0]          # later accepted removals in the same world family as the episode's first accepted removal
    after_first = collections.defaultdict(lambda: [0, 0])   # 'same_family'/'other_family' -> [accepted, tried] after first accept
    seconds = collections.defaultdict(list)
    before_first = []
    for p in paths:
        r = read(p)
        vec = (r.get('initial_observation') or {}).get('direction_vectors_world') or {}
        cad = Path(p).parts[-3]
        row = per_cad[cad]
        row['remapped'] = bool(vec) and vec.get('+z') != [0.0, 0.0, 1.0]
        first = None
        for i, t in enumerate(r.get('trace', [])):
            fam = family(vec.get(t.get('direction')))
            row['tried'][fam] += 1
            seconds[t.get('reason')].append(t.get('elapsed_seconds') or 0.)
            if first is not None:
                key = 'same_family' if fam == first else 'other_family'
                after_first[key][1] += 1
                after_first[key][0] += bool(t.get('valid'))
            if t.get('committed'):
                row['accepted'][fam] += 1
                if first is None:
                    first = fam
                    before_first.append(i)
                else:
                    persistence[1] += 1
                    persistence[0] += fam == first
    return dict(
        per_cad_world_families={c: dict(accepted=dict(v['accepted']), tried=dict(v['tried']), labels_remapped=v['remapped'])
                                for c, v in sorted(per_cad.items())},
        later_accepts_in_first_accept_family=dict(rate=round(persistence[0] / max(1, persistence[1]), 3), n=persistence[1]),
        accept_rate_after_first_accept={k: dict(rate=round(a / max(1, n), 3), tried=n) for k, (a, n) in after_first.items()},
        check_seconds_by_outcome={k: dict(median=round(statistics.median(v), 2), mean=round(statistics.mean(v), 2), n=len(v))
                                  for k, v in seconds.items() if k and v},
        checks_before_first_accept=dict(median=statistics.median(before_first) if before_first else None,
                                        max=max(before_first) if before_first else None, episodes=len(before_first)),
        meaning='Families are WORLD directions from direction_vectors_world (+z world is up). Labels are only names.')


def notes():
    out = []
    for p in sorted(glob.glob(str(V72 / 'memory/notes/asap_*/*/SKILL.md'))):
        out.append(dict(assembly=Path(p).parts[-3], base_bank=('S4b' if Path(p).parts[-3].endswith('_S4b') else 'S3'),
                        text=Path(p).read_text()))
    return out


def build(out_path=ROOT / 'outputs/mining/bundle_s5.json'):
    paths = input_results()
    bundle = mine([Path(p) for p in paths])
    bundle['world'] = world_stats(paths)
    bundle['same_assembly_notes_v72'] = notes()
    bundle['v72_outcomes_of_previous_documents'] = dict(
        S4b='Up>lateral>down prior + reuse latest successful label: on an up-axis development CAD C needed 16 checks (A 46-177); '
            'on 05902 (all removals lateral, labels remapped) B and C applied it to LABEL names and ran out of 900 s.',
        S3='Retry other directions of the same part: B swept all six directions evenly (6.6 % lateral accept rate on 05902).',
        notes='Exact-assembly notes reduced the second attempt to the minimum checks in 9 of 10 successes; one B program ignored '
              'the note and reused a generic loop from a general document.')
    bundle['input_paths'] = [str(Path(p).relative_to(WORKSPACE)) for p in paths]
    bundle['input_split'] = dict(s5_input_cads=S5_INPUT_CADS, validation_cads_held_out=VALIDATION_CADS)
    bundle['utc'] = utc()
    write(out_path, bundle)
    return bundle


if __name__ == '__main__':
    b = build()
    print(len(b['input_paths']), 'episodes;', b['world']['later_accepts_in_first_accept_family'], b['world']['accept_rate_after_first_accept'])
    for c, v in b['world']['per_cad_world_families'].items():
        print(c, v)
    print(b['world']['check_seconds_by_outcome'], b['world']['checks_before_first_accept'])
