"""Continue experience accumulation without modifying frozen evaluation banks.

Example, after the retained evaluation completes:
python -B -m disassembly_learning_v1.coordinator update --development NEW_DEV.json --validation NEW_VAL.json
The command generates and validates repairs; reading instructions alone never
starts learning. New problems must be separate from the frozen test cases.
"""
import argparse
import hashlib
from datetime import datetime,timezone
import json
from pathlib import Path

from .discovery import ROOT,bootstrap,learn_round
from .memory import SkillBank,write

def case_fingerprint(path):
    """Compare physical input content independently of case IDs and filenames."""
    p=Path(path).resolve();case=json.loads(p.read_text());parts=[]
    for part in case['parts']:
        record={k:v for k,v in part.items()if k not in {'id','color','visual_mesh','collision_meshes'}}
        record['is_target']=part['id']==case['target_id']
        record['visual_sha256']=hashlib.sha256((p.parent/part['visual_mesh']).read_bytes()).hexdigest()
        record['collision_sha256']=sorted(hashlib.sha256((p.parent/q).read_bytes()).hexdigest()for q in part['collision_meshes'])
        parts.append(record)
    normalized={'physics':case.get('physics',{}),'parts':sorted(parts,key=lambda x:json.dumps(x,sort_keys=True))}
    return hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def current_path():
    pointer=ROOT/'memory/live.json'
    if pointer.exists():return Path(json.loads(pointer.read_text())['bank_path'])
    learned=ROOT/'memory/banks/S1.json'
    return learned if learned.exists() else bootstrap()

def status():
    p=current_path();bank=SkillBank(p)
    return {'bank_path':str(p),'bank_version':bank.version,'bank_sha256':bank.sha256,
            'learned_skills':len(bank.bank['skills']),'model_weight_updates':False,
            'semantics':'Persistent procedural memory; S0/S1 evaluation snapshots remain immutable.'}

def update(development,validation,max_candidates=3):
    if not 1<=max_candidates<=3:raise ValueError('Use one to three bounded repair proposals')
    manifest_path=ROOT/'outputs/evaluation/manifest.json'
    if manifest_path.exists()and not(ROOT/'outputs/evaluation/complete.json').exists():
        raise RuntimeError('Finish the timed frozen evaluation before accumulating more experience')
    test_paths=set()
    if manifest_path.exists():test_paths={Path(c['case_path']).resolve()for c in json.loads(manifest_path.read_text())['cases']}
    test_fingerprints={case_fingerprint(p)for p in test_paths}
    for p in [*development,*validation]:
        if Path(p).resolve()in test_paths or case_fingerprint(p)in test_fingerprints:
            raise ValueError('Keep the retained test set and renamed physical copies out of this learning stream')
    if {case_fingerprint(p)for p in development}&{case_fingerprint(p)for p in validation}:
        raise ValueError('Development and validation tasks must be distinct')
    folders=list((ROOT/'outputs/learning').glob('round_*'))
    incomplete=[p for p in folders if p.is_dir()and not(p/'admission.json').exists()]
    if incomplete:raise RuntimeError('Audit an interrupted learning round before resuming: '+str(incomplete[0]))
    rounds=[int(p.name.split('_')[-1])for p in folders if p.is_dir()]
    number=max(rounds,default=0)+1;parent=current_path()
    bank_path,admission=learn_round(number,development,validation,parent,max_candidates=max_candidates)
    bank=SkillBank(bank_path)
    pointer={'updated_utc':datetime.now(timezone.utc).isoformat(),'bank_path':str(bank_path),
        'bank_sha256':bank.sha256,'round':number,'admitted':admission['admitted'],
        'previous_bank_path':str(parent)}
    write(ROOT/'memory/updates'/('round_%02d.json'%number),pointer)
    write(ROOT/'memory/live.json',pointer)
    return {**status(),'round':number,'admitted':admission['admitted']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['status','update'])
    p.add_argument('--development',nargs='+');p.add_argument('--validation',nargs='+')
    p.add_argument('--max-candidates',type=int,default=3);a=p.parse_args()
    if a.command=='status':print(json.dumps(status(),ensure_ascii=False,indent=2))
    else:
        if not a.development or not a.validation:p.error('update requires separate --development and --validation cases')
        print(json.dumps(update(a.development,a.validation,a.max_candidates),ensure_ascii=False,indent=2))
