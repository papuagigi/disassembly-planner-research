# Failure-driven disassembly planner

## 최신 결과: disassembly_repair_v7_3 (새 CAD 4개 고정 평가, 완료)

용어: SKILL.md는 LLM이 읽는 절차 파일입니다. 범용 SKILL.md는 처음 보는 조립체용(이전 버전 S3, 최신 버전 S5)이고, 조립체별 SKILL.md는 한 조립체의 1차 시도 기록으로 만든 그 조립체 전용 파일입니다(파일 이름 `assembly-note-*`). 이전 기록 문서의 "노트"는 조립체별 SKILL.md, "일반 문서"는 범용 SKILL.md를 뜻합니다.

진행 순서는 개선 사이클 → 고정 평가였습니다. 개선 사이클에서는 엔진 속도(판정 동일), 형식 위반 재요청, 조립체별 SKILL.md 우선·실제 방향 벡터 계약, 조립체별 SKILL.md 작성기 v2, 범용 SKILL.md S5와 모델 없는 규칙 검사를 넣었습니다. 고정 평가는 이전에 한 번도 쓰지 않은 ASAP CAD 4개(후보 92개 중 선정)로 했습니다. [STATUS](disassembly_repair_v7_3/STATUS.md), [평가 결과](results/repair_v7_3/EVALUATION_RESULTS.md), [개발 검증](results/repair_v7_3/VALIDATION_RESULTS.md), [전체 표](results/repair_v7_3/RESULT_TABLES.md), [발표 구성](results/repair_v7_3/PPT_OUTLINE.md)

- **같은 조립체 2차 시도:** 조립체별 SKILL.md를 쓴 B·C는 **24/24 성공**이었고, 23번은 검사 수가 필요한 제거 수와 같았습니다(실패 검사 0). SKILL.md 없는 A와 조립체별 SKILL.md 없는 B·C는 9/12였습니다.
- **처음 보는 조립체 1차 시도:**
  - C는 범용 SKILL.md S3·S5 각각에서 4/4(합 8/8) 성공했고, A는 3/4, B는 S3·S5 각각 3/4(합 6/8)였습니다.
  - A와 B·S5는 느린 CAD 02260에서 시간 초과로 실패했고, B·S3는 02991에서 생성 코드가 런타임에 거부되어 검사 0회로 끝났습니다.
- **개발 검증:** A 8/8, B(S5) 6/8, C(S5) 8/8로, 사전 규칙에 따라 S5는 불승인됐습니다. 원인은 "발견한 축에 집중" 규칙이 다른 축으로 먼저 빠져야 하는 부품을 가둔 것입니다. 그래서 평가의 주 bank는 S3이고, S5는 탐색 분기로 따로 보고합니다.
- **엔진 검증:** 물리 계산 가속(E1)은 기존 61개 에피소드를 재생해 판정이 하나도 바뀌지 않음을 확인했습니다. 재요청(R7) 8번은 모두 회복했습니다.
- **한계:** 표본이 작습니다(CAD 4개, 조건당 1~2회). 6방향 직선 이동만 다루며, 실패 기록만으로 쓴 노트는 시험되지 않았습니다.

## 이전 결과: disassembly_repair_v7_2 (학습 사이클 + 같은 조립체 재시도, 완료)

엔진 보강 → 개발 CAD 실패 수집 → SKILL.md(S4b) 생성 → 고정 검증 → 고정 재시도 평가 순서로 진행했습니다. 모델은 gpt-6-luna/low로 같고, 예산은 호출 8 / 검사 240 / 900초입니다. [STATUS](disassembly_repair_v7_2/STATUS.md), [재시도 결과](results/repair_v7_2/RETRY_RESULTS.md), [검증 결과](results/repair_v7_2/VALIDATION_RESULTS.md), [전체 표](results/repair_v7_2/RESULT_TABLES.md)

- **같은 조립체 2차 시도:** 1차 시도 기록으로 모델이 쓴 조립체 노트(SKILL.md)를 사용한 B(S3+노트)는 4/4, C(S3+노트)는 3/4 성공했고, 검사 수는 11~14회(=필요 제거 수, 실패 검사 0)였습니다. 기억 없는 A는 48~101회, 노트 없는 B·C는 40~108회였습니다. 05902에서는 1차의 900초 실패가 2차에서 약 130초 성공으로 바뀌었습니다.
- **처음 보는 조립체(일반 SKILL.md):** 06146에서는 B·C가 A보다 검사를 2.7~5.9배 적게 썼고, 05902에서는 A만 성공했습니다. 일반 문서는 그 가정(분해 축)이 맞을 때만 도움이 됐습니다.
- **검증:** 개발 CAD 05459·02402에서 A 4/4, B(S4b) 2/4, C(S4b) 4/4였습니다. 사전 규칙에 따라 S4b는 불승인됐고, 재시도에서는 탐색 분기로만 보고합니다. B의 실패 2건은 provider 도구 거부와 캐시 반복 루프였고, 이후 H5(web_search 차단)와 H6(루프 턴 중단)으로 수정했습니다.
- **인프라·계약 실패:** 모두 실패로 집계했고 재실행하지 않았습니다. 독립 재생 검증 40/40 PASS. 표본이 작아(CAD 2개, 조건당 1~2회) 일반화는 주장하지 않습니다.

## 이전 작업: disassembly_repair_v7 (완료)

v6 완료 결과는 보존하고, 별도 버전 `disassembly_repair_v7/`에서 문제를 수정·검증합니다. 진행 상황은 [STATUS](disassembly_repair_v7/STATUS.md), 변경 이유는 [CHANGELOG](disassembly_repair_v7/CHANGELOG.md)를 먼저 읽으세요.

- 소프트웨어 수정(A/B/C 공통): 정확한 상태별 탐색 기록, 막다른 자식 재진입 차단(무비용), 상태 자동 checkpoint, A/B 무진행 2회 종료, C 상태별 순위·예산 분산 호출, 프롬프트 요약. 학습된 분해 절차가 아닙니다. [회귀 검증](results/repair_v7/REGRESSION.md)
- 물리: v6 거부의 절반(494/1,003)이 이동 전 위치에서 발생. 0.2 mm 초과 CAD 겹침 규칙을 같은 모델의 1 mm 기준과 맞춘 P2를 사전 기준으로 채택했지만, 05954·03114는 P2에서도 직선 이동 충돌로 막힙니다. [결정](results/repair_v7/PHYSICS_DECISION.md), [실현 가능성](results/repair_v7/PHYSICS_FEASIBILITY.md)
- 파일럿 결과(v7.1-P2, 사전 등록, 새 CAD 3개 × A/B/C 1회): 완전 분해 **A 3/3, B 2/3, C 1/3**, 토큰 A 90k·B 159k·C 826k, MuJoCo 다시보기 9/9 검증. C의 06146 실패는 4 GiB 메모리 상한 때문이며 같은 결정을 상한 없이 재생하면 14/14 성공합니다. B의 05902 실패는 시간 예산 소진입니다. 표본이 작고 조건 차이가 여러 개라 SKILL.md 효과는 주장하지 않습니다. [해석](results/repair_v7/PILOT_INTERPRETATION.md), [표](results/repair_v7/PILOT_RESULTS.md)
- v6 0/9의 주된 원인: 05954·03114는 이 물리 모델에서 최대 3·2개만 분해 가능(직선 이동으로 빠지지 않는 둘러싸인 형상), 06444는 19/20까지 가능하나 마지막 부품이 3 µm 차이로 막힘.
- 05954·06444·03114는 v7에서 개발/회귀용입니다. 새 제품 첫 실행으로 세지 않습니다. 모델 가중치 학습 없음, 새 SKILL.md 없음(B/C는 v6 S3 문서 2개를 그대로 사용), PPT 없음.

공개본은 코드·요약 근거만 포함합니다. 원본 CAD, 원시 실행 기록, provider 프롬프트/응답 로그는 올리지 않으며 로컬 절대경로는 `<workspace>`로 치환했습니다.

## 새 문제 수정 작업의 인계

v6 예비 실험은 완료됐습니다. 현재 사용자는 Claude Code에 별도 버전의 문제 수정을 맡기려 합니다. [새 인계 안내](claude_repair_handoff/README.md),[실제 로그 진단](claude_repair_handoff/FAILURE_DIAGNOSIS.md),[입력할 프롬프트](claude_repair_handoff/TASK_PROMPT.md)를 먼저 읽으세요. 인계 문서 작성만 완료했으며 새 planner 수정·평가는 아직 실행하지 않았습니다. 아래 v6 결과는 보존한 기준 실험이며, 그 pipeline을 다시 시작하지 않습니다. 기존 중단 복구 프롬프트는 새 문제 해결 작업의 지시가 아닙니다.

ASAP CAD/OBJ를 입력으로 받고, MuJoCo로 제거 후 안정성을 확인하는 연구 prototype입니다. 실패 경험을 LLM이 읽을 수 있는 `SKILL.md`로 만들고, 처음 보는 CAD에서 도움이 되는지 비교합니다. 모델 가중치는 학습하지 않습니다.

## 완료한 최종 예비 실험

사용자가 A/B/C공통4GiB상한과 메모리 중단 개발 CAD2개의 추가 경험 수집을 승인했습니다. 새 최종 비교는 모두4GiB이며,이전1GiB결과를 최종 성공률에 섞지 않습니다. 목표 시각은 2026-10-20 13:40:49 KST입니다. 입력 준비/물리 재검증 지연에 따른 초과 가능성을 기록합니다. 기존90개 국소 경험에 v4의 새1개와 v5의 새3개를 더해 고유 개발 CAD94개를 목표로 합니다. 전체 분해 성공94개라는 뜻은 아닙니다. 새 비교는 소규모 pilot이며 결과에 따라 표본을 고르거나 추가하지 않습니다.

- 개발: 기존90개 국소 경험과 8개 긴 CAD의 완료 기록을 보존합니다. 메모리로 중단된05459/01613에서 각각4GiB로 추가 학습을 완료했습니다. 같은 초기 상태·S2문서·600검사·15분·8호출을 유지합니다. 10개 실행은8개 고유 CAD이며,고유 학습 CAD는94개입니다. 전체 분해 성공94개라는 뜻은 아닙니다.
- 독립 검증: 새로운 training CAD 3개. 이전 부분 검증 CAD는 재사용하지 않습니다. 새 문서 한 개를 생성·검증했으나 MuJoCo 자원 경고로 기각했습니다. 기존 SKILL.md 2개의 본문을 유지했습니다.
- 고정 후 테스트: 새 official test CAD 3개 × A/B/C. 각 조건은 같은 gpt-6-luna/low,8논리 호출,240물리 검사,900초,4GiB 상한을 사용합니다. Planner는 하나씩 실행합니다.
- A: LLM 코드 생성,문서 없음. B: 같은 코드 생성,고정 SKILL.md. C: Graph·LLM 순위·DFS,동일한 SKILL.md.
- 결과가 좋게 나올 때까지 개선을 반복하지 않습니다. 최종 PPT는 결과 검토 후 만듭니다.

현재 상태는 [docs/status.json](docs/status.json), 세부 실행·복구 지침은 [AGENT_HANDOFF](docs/AGENT_HANDOFF.md), 실험 조건은 [PLAN](docs/PLAN.md)을 읽으세요. 아직 생성되지 않은 결과 파일은 완료를 의미하지 않습니다. 현재 공개본은 완료한 예비 실험의 코드·집계·다시보기 snapshot입니다. 정확한 재개에는 기존 로컬 CAD와 실행 환경이 필요합니다.

최종 표본은 **3 CAD × A/B/C = 9회 첫 실행**입니다. 후보75개 중3개만 입력 검증을 통과해,평가 결과를 보기 전에 표본 수를 줄였고 사용자가 이를 확인했습니다. 원래4개 목표는 미달했습니다. [표본 변경](docs/provenance/cohort_amendment.json),[사용자 확인 기록](docs/provenance/cohort_amendment_confirmation.json)을 보세요. 모델·예산·물리 기준·actor·skill은 유지합니다.

Claude Code로 재개할 때는 [복사용 프롬프트](docs/CLAUDE_CONTINUATION_PROMPT.md)와 [재개 안내](docs/CLAUDE.md)를 읽으세요. 현재 로컬 실행이 살아 있으면 중복 실행하지 않습니다.

## 입력과 판단 흐름

부품별 OBJ와 조립 위치 → 원본 형상 충돌 검사/초기 물리 검증 → LLM의 코드 또는 후보 순위 → 검증된 제거·checkpoint 복원 → MuJoCo 잔여 조립체 안정성 → 로그와 다시보기.

목표는 고정된 원래 부품 하나를 제외한 n−1개 부품의 안정적인 제거입니다. 한 부품은 영구 고정되며 중력으로 떨어지지 않습니다. 현재 이동은 회전 없는 여섯 축 방향 직선 추출입니다. 가상 checkpoint 복원은 실제 재조립 동작이 아닙니다. 원본 ASAP 동역학·로봇 실험을 그대로 재현한 것은 아닙니다.

## 폴더

- `disassembly_final_v6/`: 현재4GiB 실험의 supervisor,추가 학습·검증·고정·평가,문서 bank,설정.
- `disassembly_final_v5/`: 보존한1GiB 실험 코드. 기존 실행 결과는 별도로 유지합니다.
- `disassembly_final_v4/`: 새 학습 범위 승인 전의 구현. 로컬 완료 기록과 부분 검증은 보존하고 새 최종 비교와 구분합니다.
- `docs/`: 협업·복구 지침과 앞선 실험의 출처 요약.
- `results/final_v6/`: 최종 집계가 생성되면 갱신됩니다.
- `results/prior_v3/`: 보존한180초 기준 결과입니다. 다시보기 검증 상태는 별도JSON에 표시합니다. 새15분 실험과는 학습·시간 조건이 달라 직접적인 개선 원인 비교에 쓰지 않습니다.
- `viewer/`: MuJoCo 기록을 재생하는 Three.js viewer. 대용량 OBJ/episode는 이 저장소에 자동 업로드하지 않습니다.
- 나머지 `disassembly_*`: 현재 엔진의 import 의존성을 보존한 이전 구현입니다. 현재 실행 진입점은 v6입니다.

## 환경과 실행

Python 환경을 만들고 `pip install -r requirements.txt`로 의존성을 설치합니다. 실제 사용 환경의 버전이며 다른 OS에서의 설치는 별도 확인이 필요합니다. LLM 실행에는 로컬 Codex CLI와 본인 로그인 상태가 필요합니다. 인증 파일이나 API 키를 저장소에 올리지 마세요. 모델 호출은 사용자의 계정 한도를 사용합니다.

```sh
python -B -m disassembly_final_v6.bootstrap --download
PYTHONDONTWRITEBYTECODE=1 python -B -m disassembly_final_v6.pipeline
```

약0.75GB의 공식 archive를 SHA256 검증 후 별도로 받습니다. 기존 완료 기록이 있는 실행은 이어서 진행합니다. 이미 시작된 평가 episode는 조용히 다시 실행하지 않습니다. 원본 작업 머신과 공개 snapshot은 로컬 경로가 다를 수 있습니다. `protocol/prior_sources.json`의 상대 경로는 저장소 루트를 기준으로 해석합니다. 상세 검증 reference 일부의 원본 로컬 경로는 증거 식별용이며 다른 머신에 존재하지 않습니다.

최종 native replay 생성 후에는 study 폴더를 HTTP로 서비스하고 `viewer/index.html`을 여세요. 루트 `viewer/`만으로는 아직 업로드하지 않은 geometry/episode를 재생할 수 없습니다.

## 협업

추가 작업은 새 branch 또는 fork에서 진행하세요. `outputs/protocol/freeze.json`이 생긴 뒤에는 그 실험의 actor,physics,bank를 수정하지 않습니다. 테스트 실패를 학습 자료로 쓰면 해당 CAD의 결과를 새 제품 첫 실행 성능으로 재사용할 수 없습니다. 변경 제안은 원인·변경점·검증·비교 조건을 MD로 남겨 주세요. Claude에게 작업을 자동 할당하지 않습니다.

데이터: [ASAP](https://github.com/yunshengtian/ASAP),[논문](https://arxiv.org/abs/2309.16909). 공식 데이터와 외부 라이브러리는 각각의 원래 배포 조건을 따릅니다. 원본 CAD archive,학술 PDF,발표자료,venv,인증 정보는 업로드하지 않습니다. viewer vendor의 라이선스 고지를 유지합니다.

## 내려받아 볼 수 있는 최종 다시보기

[demo/README.md](demo/README.md)를 읽으세요. 선택한 최종 CAD의 정규화된 시각화 형상과 압축된 실제 실행 기록이 포함됩니다. 저장소를 받은 뒤 `cd demo` 및 `python3 -m http.server 8783 --bind 127.0.0.1`로 열 수 있습니다. GitHub Pages 배포나 실시간 MuJoCo 계산은 아닙니다. 원본 전체 CAD archive와 모델 인증/원시 CLI 로그는 포함하지 않습니다.

## 05459의 16개 제거 다시보기

[development_demo/README.md](development_demo/README.md)를 읽으세요. 4GiB추가학습에서 성공한 실제26개 검사와16개 제거를 MuJoCo로 재검증했습니다. 저장소를 받은 뒤 `cd development_demo`에서 `python3 -m http.server 8786 --bind 127.0.0.1`을 실행하고 `/viewer/development.html`을 여세요. 최종 A/B/C평가 결과가 아닌 개발 사례입니다.

## 최종 평가 결과

모든 첫 실행과 다시보기를 검증했습니다. 종료 상태의 제거 수이며,복원으로 되돌린 제거는 이 합계에서 제외합니다.

|조건|완전 분해 성공|최종 제거 수 합계 / 목표 합계|사용 토큰 합계|
|---|---:|---:|---:|
|A|0/3|15/53|70,112|
|B|0/3|4/53|893,286|
|C|0/3|2/53|1,364,693|

[결과와 한계](results/final_v6/RESULTS.md),[실행별 지표](results/final_v6/trials.csv),[토큰 집계](results/final_v6/token_usage.json)를 함께 보세요. 토큰은 provider가 보고한 입력+출력이며,캐시 입력을 중복 가산하지 않습니다. 미확인 사용량은0으로 간주하지 않습니다. 원래4개 목표에 미달한3개 CAD의 작은 예비 실험입니다.

세 조건 모두 완전 분해에 실패했으므로,이 실험에서 library의 성공률 개선을 입증하지 못했습니다. 부분 진행률이나 낮은 비용을 완전 분해 성공으로 해석하지 않습니다.
