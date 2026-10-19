# Failure-driven disassembly planner

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
