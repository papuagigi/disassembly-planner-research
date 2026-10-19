"""Two bounded experience rounds; resumes only at completed round boundaries."""
import json
from pathlib import Path
from .discovery import ROOT,bootstrap,learn_round
from .memory import SkillBank,create_bank,write

def run():
    selected=json.loads((ROOT/'outputs/input_audit/development_cases_v2.json').read_text())
    cases={c['case_id']:c for c in selected['cases']}
    parent=bootstrap();ledger=[]
    pairs=[('dev_01','val_01_v2'),('dev_02_v2','val_02')]
    for i,(dev,val)in enumerate(pairs,1):
        path=ROOT/'outputs/learning'/('round_%02d'%i)/'admission.json'
        if path.exists():
            admission=json.loads(path.read_text());parent=Path(admission['result_bank_path'])
        else:
            parent,admission=learn_round(i,[cases[dev]['case_path']],[cases[val]['case_path']],parent,max_candidates=3)
        ledger.append(admission)
        write(ROOT/'outputs/learning/ledger.json',{'rounds':ledger,'weight_updates':False,
            'evaluation_learning':False,'status':'learning_in_progress','base_bank':'S0',
            'model':'gpt-6-luna','effort':'low'})
        print(json.dumps({'round':i,'admitted':admission['admitted'],'bank':str(parent),
            'baseline_validation':admission['baseline_validation'],'candidate_validation':admission['candidate_validation']}),flush=True)
    bank=SkillBank(parent);dest=ROOT/'memory/banks/S1.json'
    if not dest.exists():create_bank(dest,'S1',bank.bank['skills'],parent=bank.sha256,
        provenance={'learning_rounds':len(ledger),'admitted_skills':len(bank.bank['skills']),
                    'final_test_data_seen':False,'learning_ledger':'outputs/learning/ledger.json'})
    final=SkillBank(dest)
    write(ROOT/'outputs/learning/ledger.json',{'rounds':ledger,'weight_updates':False,'evaluation_learning':False,
        'status':'complete','base_bank':'S0','learned_bank':'S1','learned_bank_sha256':final.sha256,
        'admitted_skills':len(final.bank['skills']),'model':'gpt-6-luna','effort':'low',
        'semantics':'Round2 loads persisted round1 memory into a fresh SkillBank instance; evaluation later freezes this bank.'})
    print(json.dumps({'learning_complete':True,'skills':len(final.bank['skills']),'S1_sha256':final.sha256}),flush=True)

if __name__=='__main__':run()
