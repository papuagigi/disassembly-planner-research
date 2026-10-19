import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
r=lambda p:json.loads(Path(p).read_text())
summary=r(ROOT/'analysis/summary.json')
rows=[]
for g in summary['groups']:
 rows.append({'track':g['track'],'condition':g['method_label'],'success':g['successes'],'runs':g['n'],
  'checks_mean':round(g['mean_physics_checks_total'],2),'failures_mean':round(g['mean_failed_checks_after_preparation'],2),
  'restore_changed_mean':round(g['mean_restore_state_changes'],2),'llm_calls_mean':round(g['mean_llm_calls'],2)})
primary={'id':'primary-study','title':'새 3D 사례에서 동일 모델과 예산으로 비교한 결과','queries':[{'id':'fifty-four-runs',
 'source':{'label':'54회 실제 MuJoCo 평가 로그','files':[{'label':'summary.json'},{'label':'manifest.json'},{'label':'physics_replay_audit.json'}],
 'metricDefinitions':[{'label':'회수 성공','definition':'회수 성공은 허용된 제거마다 경로 충돌과 잔류 안정성 검사를 통과해 목표 부품을 제거한 실행입니다.'},
 {'label':'실패 시도','definition':'실패 시도는 공통 준비 검사 6회 또는 7회를 제외한 거부된 물리 검사입니다.'},
 {'label':'복원','definition':'상태 변경 복원은 저장점 복원 전후의 부품 목록·위치·자세·속도가 달라진 사건입니다. 같은 상태 복원 호출은 별도 집계합니다.'}],
 'filters':['gpt-6-luna, reasoning low','조건·시작 유형별 9회','상한: 검사120회, LLM8회, 480초'],
 'caveats':['평가 자료는 한 가지 자체 설계 구조의 3D 형상 변형 3개이며 실제 제품 3종이 아닙니다.',
 'seeded는 실험자가 같은 잘못된 지지대 제거 상태를 제공한 복구 시험입니다. 모델의 자연 발생 오류로 집계하지 않습니다.',
 '예산 상한은 동일하지만 실제 토큰·호출·실행 시간은 다릅니다.',
 '공통 정보와 API는 같으며 역할별 프롬프트 표현과 스스로 생성한 체크포인트 메타데이터는 다릅니다.']},
 'columns':['track','condition','success','runs','checks_mean','failures_mean','restore_changed_mean','llm_calls_mean'],
 'rows':rows,'preview':{'kind':'aggregate','note':'54개 전체 실행을 시작 유형과 조건별로 집계했습니다.','totalRows':54}}]}
old={'id':'prior-failure-diagnosis','title':'기존 실패의 원인과 검사 예산만 늘린 재생','queries':[{'id':'stored-response-replay',
 'source':{'label':'기존 C의 저장 응답 재생과 코드 계측','files':[{'label':'diagnosis.json'},{'label':'opcode_profile.json'}],
 'metricDefinitions':[{'label':'조건부 재생','definition':'조건부 재생은 기존 모델 응답을 그대로 반환하며 검사 상한만 변경한 실행입니다.'}],
 'caveats':['새 LLM 호출은 0회입니다. 증가한 예산을 본 모델이 새로 판단한 실험은 아닙니다.',
 'opcode 비중은 제한 대상인 탐색 코드 내부의 계수이며 전체 실행 시간 비중이 아닙니다.']},
 'columns':['check_cap','successes','runs','actual_checks_mean','termination'],
 'rows':[{'check_cap':24,'successes':0,'runs':9,'actual_checks_mean':24,'termination':'검사 상한'},
 {'check_cap':120,'successes':0,'runs':9,'actual_checks_mean':63.33,'termination':'100만 opcode 상한'}]},
 {'id':'asap-structure','source':{'label':'공식 ASAP 소스','links':[{'label':'ASAP planner','url':'https://github.com/yunshengtian/ASAP/blob/3727e716b57e0b508c4e9ecd9fefa6953e8f72da/plan_sequence/planner/base.py'}],
 'caveats':['ASAP 전체를 실행해 재현한 결과가 아닙니다. 후보 생성·탐색·검증 분리와 전이 기록 재사용을 참고했습니다.']},
 'summary':'ASAP의 전역 상태 그래프와 후보 생성·물리 검증 분리는 C의 구조 개선에 참고했습니다. 지지용 고정 기능은 현재 문제에 무료로 추가하지 않았습니다.'}]}
models=[]
for p in sorted((ROOT/'outputs/development/model_probe').rglob('result.json')):
 v=r(p);models.append({k:v[k]for k in ['model','track','success','checker_calls','llm_calls']})
pilot={'id':'model-development-pilot','title':'개발 사례에서 기존 모델과 더 큰 모델을 비교한 보조 시험','queries':[{'id':'paired-development-calls',
 'source':{'label':'A의 모델별 개발 시험','files':[{'label':'model_probe result.json'}],
 'filters':['개발용 조립체 1개','모델·시작 유형별 1회','동일 입력과 예산'],
 'caveats':['개발 시험이며 새 평가 54회와 합산하지 않습니다.',
 '모델별 1회씩의 소규모 결과로 일반적인 모델 우열을 결론 내릴 수 없습니다.',
 '최종 평가 전 사용법 안내가 보강되었으므로 이 개발 결과는 최종 A의 성능과 직접 비교하지 않습니다.']},
 'columns':['model','track','success','checker_calls','llm_calls'],'rows':models}]}
payload={'schemaVersion':1,'items':[primary,old,pilot]}
path=ROOT/'analysis/inline_sources.json';path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
print(path)
