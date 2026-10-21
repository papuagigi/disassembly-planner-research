# v7.3 발표 자료 (슬라이드 원본)

v7.3 결과를 논문식 흐름으로 정리한 최종 발표 자료 15장입니다. 슬라이드별 구성과 S5 기준으로 보여 주는 이유는 [PPT_OUTLINE.md](../PPT_OUTLINE.md)에 있습니다. 숫자는 `EVALUATION_RESULTS.md`, `VALIDATION_RESULTS.md`, `evaluation_runs.csv`에서 확인한 값만 썼습니다.

## 파일
- `deck.json`: 슬라이드 순서, 섹션, 글꼴(IBM Plex Sans KR, JetBrains Mono).
- `slides/<id>.html`: 슬라이드 한 장. 1920×1080 캔버스의 `<section>` 하나이고, 발표자 노트는 마지막 `<aside>`에 있습니다.

## 순서
1. `cover`: 표지
2. `motivation`: 연구 동기
3. `goal`: 연구 목표와 용어
4. `planner`: disassembly planner란
5. `abc_why`: A·B·C 구조와 도입 이유
6. `skillmd`: 범용 SKILL.md(S5) 작성법
7. `skillmd2`: 조립체별 SKILL.md 작성법
8. `setup`: 실험 환경과 평가 설계
9. `result1`: 결과 ①, 같은 조립체
10. `result2`: 결과 ②, 처음 보는 조립체
11. `result3`: 결과 ③, S5 개발 검증
12. `insights`: 시사점
13. `application`: 현장 적용
14. `limits`: 한계
15. `closing`: 결론

## 보는 방법
- 발표용 파일은 [`v7.3_발표자료.pptx`](v7.3_발표자료.pptx)입니다. Slides artifact 페이지에서 편집 가능한 PowerPoint(현재 글꼴)로 내보낸 파일입니다. 15장 모두 발표자 노트가 있고, 글꼴(IBM Plex Sans KR, JetBrains Mono)이 파일에 포함되어 있습니다.
- `deck.json`과 `slides/*.html`은 Claude Slides artifact 형식의 원본입니다. `x-icon`, `x-shape`는 Slides 런타임 전용 요소라서, HTML 파일을 일반 브라우저로 직접 열면 아이콘과 화살표가 보이지 않고 슬라이드 크기도 맞지 않습니다.
