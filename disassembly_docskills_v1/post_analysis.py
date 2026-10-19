"""Post-score evidence tables. Metric definitions remain the frozen metrics.py."""
import csv
import json
import math
import os
from pathlib import Path
from statistics import mean
from .common import ROOT,read,write,sha,utc,progress
from .protocol import verify
from .metrics import summarize

ARMS=['A','B','C','C_S0']

def provider_cost(folder):
    metadata=[read(p) for p in sorted((folder/'llm_calls').glob('call_*/metadata.json'))]
    usage={'input_tokens':0,'output_tokens':0,'cached_input_tokens':0}
    unknown=0
    for item in metadata:
        u=item.get('usage') or {}
        if 'input_tokens' not in u or 'output_tokens' not in u:unknown+=1
        for key in usage:usage[key]+=u.get(key,0)
    return dict(**usage,known_total_tokens=usage['input_tokens']+usage['output_tokens'],
        calls_with_unknown_usage=unknown,logged_calls=len(metadata),
        provider_seconds=sum(m.get('elapsed_seconds',0) for m in metadata),
        rejected_tool_calls=sum(bool(m.get('tool_activity_count')) for m in metadata),
        accounting='Input already includes cached input; cached and reasoning tokens are not added a second time. Missing usage is unknown, not zero.')

def main():
    frozen=verify();manifest=read(ROOT/'outputs/evaluation/manifest.json');complete=read(ROOT/'outputs/evaluation/complete.json')
    assert len(complete['episodes'])==manifest['planned_episodes']
    out=ROOT/'analysis';out.mkdir(exist_ok=True);trials=[];integrity=[]
    for case in manifest['cases']:
        observations=[];banks={}
        for arm in ARMS:
            folder=ROOT/'outputs/evaluation/trials'/case['case_id']/arm
            result=read(folder/'result.json');metrics=summarize(result);cost=provider_cost(folder)
            assert result.get('limits')==manifest['limits']
            assert result['case_sha256']==case['case_sha256']
            assert result['state']['trace']==result['trace']
            assert result['learning_updates']==0
            assert result['checker_calls']<=manifest['limits']['max_checks']
            assert result['llm_calls']<=manifest['limits']['max_calls']
            if result['success']:assert result['remaining_part_count']<=1
            observations.append(result['initial_observation_sha256']);banks[arm]=result.get('bank_content_sha256')
            generation_errors=[d['execution_error'] for d in result['decisions'] if d.get('execution_error')]
            invalid_restores=sum(e['operation']=='restore' and e.get('status')!='completed' for e in result['recovery_state']['events'])
            changed_restores=sum(e['operation']=='restore' and e.get('status')=='completed' and e.get('state_key_before')!=e.get('state_key_after') for e in result['recovery_state']['events'])
            row=dict(case_id=case['case_id'],arm=arm,**metrics,**cost,invalid_restores=invalid_restores,changed_state_restores=changed_restores,
                no_op_restores=max(0,metrics['restores']-changed_restores),
                code_or_execution_errors=len(generation_errors),execution_error_types=[e['type'] for e in generation_errors],
                final_error=result.get('error'),bank_version=result['bank_version'],
                result_path=str(folder/'result.json'),result_sha256=sha(folder/'result.json'),
                first_budgeted_episode=True,model=frozen['model'],reasoning_effort=frozen['reasoning_effort'])
            trials.append(row)
        assert len(set(observations))==1,'Different initial public observations'
        assert banks['B']==banks['C'],'Different document bytes or validation references'
        assert banks['A']==banks['C_S0'],'Different empty bank'
        integrity.append(dict(case_id=case['case_id'],initial_observation_identical=True,
            same_B_C_memory_content=True,same_A_C0_empty_memory=True,observation_sha256=observations[0]))
    aggregates=[]
    numeric=['final_progress','checks','failed_checks','duplicate_queries','duplicate_rejected_queries',
        'undone_accepted_removals','restores','llm_calls','elapsed_seconds','provider_seconds','known_total_tokens',
        'document_reads','invalid_restores','code_or_execution_errors','changed_state_restores','no_op_restores']
    for arm in ARMS:
        rows=[r for r in trials if r['arm']==arm]
        aggregates.append(dict(arm=arm,n=len(rows),successes=sum(r['success'] for r in rows),
            success_rate=sum(r['success'] for r in rows)/len(rows) if rows else None,
            **{k+'_mean':mean(r[k] for r in rows) if rows else None for k in numeric},
            calls_with_unknown_usage=sum(r['calls_with_unknown_usage'] for r in rows)))
    deltas=[]
    for case in manifest['cases']:
        byarm={r['arm']:r for r in trials if r['case_id']==case['case_id']}
        for left,right,label in [('A','B','document effect within generated-code architecture'),
                                 ('C_S0','C','document effect within graph/DFS architecture'),
                                 ('B','C','architecture bundle with identical document bank')]:
            deltas.append(dict(case_id=case['case_id'],baseline=left,changed=right,comparison=label,
                success_delta=int(byarm[right]['success'])-int(byarm[left]['success']),
                **{k+'_delta':byarm[right][k]-byarm[left][k] for k in numeric}))
    write(out/'results.json',dict(created_utc=utc(),trials=trials,aggregates=aggregates,paired_deltas=deltas,
        integrity=integrity,protocol_sha256=manifest['protocol_sha256'],
        native_model_inference_seed_control=False,
        interpretation='One stochastic first episode per product/arm in a small conditional cohort. No statistical population or single-component causal claims. Non-completion costs are not silently removed.',
        admitted_skill_scope=read(ROOT/'outputs/development/schema_skill/admission.json')['skill_scope'],
        full_search_skill_admission=False))
    for name,rows in [('trials',trials),('aggregate',aggregates),('paired_deltas',deltas)]:
        if not rows:continue
        columns=list(rows[0])
        with (out/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
            for row in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    header=['# Final document-skill first-episode evidence','',
        'Read raw trials before attributing any difference. A/B share a code actor; C/ C(S0) share graph/DFS. A also serves as B(S0). C(S0) still uses LLM ranking. There is no ranking-OFF arm in this study.',
        '',
        'The admitted memory contains one narrow API-schema repair. Complete-search/nearest-ancestor procedures did not pass development validation and were not admitted. The third candidate passed independent schema-unit verification on two real development CAD states. It does not prove full-disassembly improvement.',
        '',
        '|Arm|Full success|Mean final progress|Mean checks|Mean failed checks|Mean LLM calls|Mean wall seconds|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in aggregates:
        def value(k):return 'NA' if r[k] is None else format(r[k],'.2f')
        header.append('|'+r['arm']+'|'+str(r['successes'])+'/'+str(r['n'])+'|'+value('final_progress_mean')+'|'+value('checks_mean')+'|'+value('failed_checks_mean')+'|'+value('llm_calls_mean')+'|'+value('elapsed_seconds_mean')+'|')
    header+=['','All per-product outcomes, exact duplicate rejected checks, undone removals, restorations, generated-code errors, request/read/declaration logs and provider-token costs are in results.json and CSV.',
        '',
        'Tokens include failed provider responses when metadata is available. Calls with missing token usage are explicitly counted; known_total_tokens is then a lower bound. Cached input and reasoning output are not double-counted.',
        '',
        'The fixed20-source reserve and all input exclusions are in outputs/input_audit/selected_cases.json. Original metadata-parser failures are archived separately and cannot be counted as planner or CAD-physics failures. The infrastructure-only erratum preserved the original frozen planner, memory, physical settings and reserve.',
        '',
        'Reference-based qualification conditions the cohort on locally representable full paths and may favor DFS. Local MuJoCo success is not official ASAP certification or factory feasibility. One permanently fixed original component, assumed scale/materials, sampled fixed-orientation extraction and finite settling remain limitations.',
        '',
        'No hypothesis-specific modification or retry was made on the final products. Equal model/call/check/time/instruction/RSS ceilings do not mean equal realized token or physical cost. The model sampling seed is uncontrolled.',
        '',
        'Source chain: outputs/protocol/freeze.json; outputs/protocol/metadata_parser_erratum.json; memory/S1.json; outputs/development/schema_skill/admission.json; outputs/evaluation/manifest.json; outputs/evaluation/complete.json.']
    (out/'RESULTS.md').write_text('\n'.join(header)+'\n')
    plot(aggregates,trials,out)
    progress('first_episode_analysis_complete',products=len(manifest['cases']),episodes=len(trials))

def plot(aggregates,trials,out):
    if not trials:return
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'outputs/tmp/mpl_analysis'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=['#2C6E9E','#D98A33','#24897E','#93A3AE']
    labels=[r['arm'] for r in aggregates]
    fig,axs=plt.subplots(1,3,figsize=(12.8,3.8))
    for ax,key,title,ylabel in [(axs[0],'success_rate','Full disassembly','Success rate'),
        (axs[1],'checks_mean','Physical checks','Mean count'),
        (axs[2],'llm_calls_mean','LLM calls','Mean count')]:
        values=[r[key] for r in aggregates];ax.bar(labels,values,color=colors,width=.58)
        for i,v in enumerate(values):ax.text(i,v,str(aggregates[i]['successes'])+'/'+str(aggregates[i]['n']) if key=='success_rate' else format(v,'.1f'),ha='center',va='bottom',fontsize=10)
        ax.set_title(title);ax.set_ylabel(ylabel);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        ax.set_ylim(0,1.15 if key=='success_rate' else max(values+[1])*1.25)
    fig.suptitle('First budgeted episode per unseen product | local-model conditional cohort',fontsize=12)
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(12.8,3.6))
    for ax,key,title in [(axs[0],'duplicate_rejected_queries_mean','Repeated rejected exact-state queries'),
        (axs[1],'undone_accepted_removals_mean','Accepted removals later undone'),
        (axs[2],'restores_mean','State restores')]:
        values=[r[key] for r in aggregates];ax.bar(labels,values,color=colors,width=.58)
        for i,v in enumerate(values):ax.text(i,v,format(v,'.1f'),ha='center',va='bottom',fontsize=10)
        ax.set_title(title,fontsize=10);ax.set_ylim(0,max(values+[1])*1.25);ax.spines[['top','right']].set_visible(False)
    fig.tight_layout();fig.savefig(out/'search_costs.png',dpi=180);plt.close(fig)

if __name__=='__main__':main()
