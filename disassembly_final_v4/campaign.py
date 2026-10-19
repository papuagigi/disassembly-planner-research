"""One matched first episode per qualified new official test product and arm."""
from pathlib import Path
from .common import ROOT,read,write,sha,utc,progress
from .contracts import ARMS
from .protocol import verify
from .driver import run

def bind():
    frozen=verify();path=ROOT/'outputs/evaluation/manifest.json'
    if path.exists():return read(path)
    selected=read(ROOT/'outputs/input_audit/selected_evaluation.json');assert selected['status']=='FINITE_COHORT_COMPLETE'
    prior=read(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json')
    known={r['fingerprint'] for r in prior['records']}
    excluded=[c for c in selected['cases'] if c['geometry_fingerprint'] in known]
    cases=[c for c in selected['cases'] if c['geometry_fingerprint'] not in known];assets={}
    assert len(cases)>=frozen['minimum_CAD_requirements']['evaluation'],'Minimum unseen test CAD count not reached;no claim of completion'
    for case in cases:
        assert case['required_removals']>=10 and case['source_split']=='test_assembly'
        cp=Path(case['case_path']);paths=[cp,Path(case['shared_path'])]
        for part in read(cp)['parts']:
            paths.append((cp.parent/part['visual_mesh']).resolve())
            paths.extend((cp.parent/p).resolve() for p in part['collision_meshes'])
        assets.update({str(p):sha(p) for p in paths})
    result=dict(created_utc=utc(),status='FINAL_INPUTS_BOUND',protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'),
        cases=cases,excluded_prior_exact_geometry_duplicates=excluded,
        initial_physics_qualified_before_prior_shape_screen=len(selected['cases']),
        prior_geometry_ledger_sha256=sha(ROOT/'outputs/input_audit/previous_geometry_fingerprints.json'),
        asset_sha256=assets,limits=frozen['limits'],arms=ARMS,planned_episodes=len(cases)*3,
        model=frozen['model'],reasoning_effort=frozen['reasoning_effort'],library_updated_on_final_products=False,
        reference_search_used_for_selection=False,initial_observation_equal_per_case=True,
        source_split='official ASAP test_assembly',fresh_to_project=True)
    write(path,result,exclusive=True);return result

def main():
    done=ROOT/'outputs/evaluation/complete.json'
    if done.exists():return read(done)
    manifest=bind();arms=list(ARMS);completed=[]
    for i,case in enumerate(manifest['cases']):
        for arm in arms[i%3:]+arms[:i%3]:
            verify()
            for p in [case['case_path'],case['shared_path']]:assert sha(p)==manifest['asset_sha256'][p]
            conf=ARMS[arm];folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm
            progress('first_episode',case=case['case_id'],arm=arm,completed=len(completed),planned=manifest['planned_episodes'])
            run(dict(folder=str(folder),case_path=case['case_path'],shared_path=case['shared_path'],
                architecture=conf['architecture'],bank_path=str(ROOT/'memory'/(conf['bank']+'.json')),
                limits=manifest['limits'],phase='evaluation',arm=arm,protocol_sha256=manifest['protocol_sha256']))
            completed.append(dict(case_id=case['case_id'],arm=arm,result_path=str(folder/'result.json'),sha256=sha(folder/'result.json')))
    write(done,dict(status='COMPLETE',created_utc=utc(),episodes=completed,expected=manifest['planned_episodes'],
        protocol_sha256=manifest['protocol_sha256'],no_test_memory_updates=True),exclusive=True)
    progress('first_episode_campaign_complete',episodes=len(completed),cases=len(manifest['cases']))

if __name__=='__main__':main()
