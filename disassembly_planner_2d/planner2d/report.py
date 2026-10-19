"""Dependency-free, offline viewer for recorded 2D planner executions.

The viewer never runs a planner and never infers a state by replaying a search
trace. Each frame uses that trace's explicitly recorded before/after state.
"""

from __future__ import annotations

import json
from pathlib import Path


def write_report(scene: dict, runs: list[dict], output_path: str | Path) -> Path:
    """Write a self-contained HTML report, preserving the supplied evidence.

    Coordinates use Cartesian axes: positive y is ``up``. Unknown provenance is
    labelled as a saved record, never as proof of an LLM API execution. The
    optional ``provenance``/``candidate_source``/``scripted`` fields can make the
    source of candidate proposals explicit.
    """
    if not isinstance(scene, dict) or not isinstance(runs, list):
        raise TypeError("scene must be a dict and runs must be a list")
    payload = json.dumps(
        {"scene": scene, "runs": runs}, ensure_ascii=False, allow_nan=False
    )
    # An application/json script element still terminates at an HTML end tag.
    # Escape HTML delimiters, including those supplied inside labels or traces.
    for literal, escaped in (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        payload = payload.replace(literal, escaped)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_HTML.replace("__REPORT_DATA__", payload), encoding="utf-8")
    return destination


_HTML = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Disassembly Lab · 실행 기록</title>
<style>
:root{--ink:#162a43;--muted:#66778a;--teal:#087f80;--teal-soft:#e4f4f0;--orange:#dd7b21;--orange-soft:#fff2df;--red:#cf5d51;--line:#dce5e9;--bg:#f3f6f6;--card:#fff;--shadow:0 8px 32px #16334b07}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",Arial,sans-serif}button,select{font:inherit}button,select{color:var(--ink)}button{cursor:pointer}button:disabled{cursor:default;opacity:.4}button:focus-visible,select:focus-visible{outline:3px solid #73c2c6;outline-offset:3px}button{touch-action:manipulation}header{background:#fff;border-bottom:1px solid var(--line)}.wrap{max-width:1480px;margin:auto;padding:0 38px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding-top:22px;padding-bottom:22px}.brand{display:flex;gap:11px;align-items:center;font-weight:750;letter-spacing:-.35px;font-size:19px}.brand-mark{height:35px;width:35px;background:var(--teal);color:white;display:grid;place-items:center;border-radius:9px;font-size:14px;letter-spacing:0}.topnote{font-size:12px;color:var(--muted)}.intro{padding-top:32px;padding-bottom:25px;display:flex;justify-content:space-between;align-items:flex-start;gap:24px}.eyebrow{text-transform:uppercase;font-size:10px;letter-spacing:1.8px;font-weight:750;color:var(--teal);margin:0 0 9px}h1{font-size:clamp(25px,2.4vw,34px);line-height:1.35;letter-spacing:-1.2px;margin:0 0 9px}p{margin:0}.description{color:var(--muted);max-width:780px;word-break:keep-all}.scope{border:1px solid #c6dedb;background:#edf8f5;color:#376f6e;white-space:nowrap;border-radius:30px;padding:6px 12px;font-size:11px;margin-top:11px}.toolbar{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:18px}.method-group{display:flex;align-items:center;gap:12px}.caption{font-size:12px;color:var(--muted)}select{background:white;border:1px solid #cedce1;border-radius:9px;padding:10px 38px 10px 13px;min-width:240px;max-width:430px;font-weight:650}.provenance{font-size:11px;color:var(--muted);text-align:right}.provenance strong{display:block;color:var(--ink);font-weight:600}.metrics{display:grid;grid-template-columns:1.12fr 1fr 1fr 1fr;gap:12px;margin-bottom:22px}.metric{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 21px;box-shadow:var(--shadow)}.metric-label{font-size:11px;color:var(--muted);margin-bottom:4px}.metric-value{font-size:25px;letter-spacing:-.7px;font-weight:750;line-height:1.4;font-variant-numeric:tabular-nums}.metric-value small{font-size:12px;margin-left:5px;font-weight:500;color:var(--muted)}.metric-foot{font-size:10px;color:var(--muted);margin-top:3px}.success{color:var(--teal)}.failure{color:var(--orange)}.layout{display:grid;grid-template-columns:minmax(0,1fr) 345px;gap:20px;align-items:start}.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);overflow:hidden}.panel-head{display:flex;align-items:center;justify-content:space-between;padding:18px 23px;border-bottom:1px solid #e9eff1;gap:12px}h2{font-size:14px;margin:0;font-weight:700;letter-spacing:-.2px}.scene-id{font-size:11px;color:var(--muted);overflow-wrap:anywhere}.visual-head{align-items:flex-start}.target-chip{white-space:nowrap;color:var(--teal);background:var(--teal-soft);padding:4px 10px;font-size:11px;border-radius:20px}.canvas-wrap{position:relative;padding:8px 18px 0;min-height:350px;background:linear-gradient(180deg,#fcfdfd,#f7faf9)}#scene-svg{display:block;width:100%;height:auto;min-height:320px;max-height:540px}.canvas-hint{position:absolute;left:27px;top:17px;display:flex;gap:6px;align-items:center;color:#789090;font-size:10px}.hint-dot{width:5px;height:5px;border-radius:100%;background:#89b8b1}.legend{display:flex;gap:18px;flex-wrap:wrap;padding:8px 24px 16px;font-size:10px;color:var(--muted);background:#f7faf9}.legend span{display:flex;align-items:center;gap:6px}.swatch{height:8px;width:8px;border-radius:2px;background:#92a9bf}.swatch.target{background:#0c8e8d}.swatch.blocker{background:#df8178}.swatch.fixed{background:#344c62}.swatch.sweep{background:#f6cc91;border:1px dashed #dd9239}.controls{display:flex;align-items:center;justify-content:space-between;padding:15px 21px;gap:12px;border-top:1px solid var(--line)}.transport{display:flex;gap:7px;align-items:center}.control{background:white;border:1px solid var(--line);border-radius:7px;min-width:34px;height:33px;padding:0 9px;font-size:12px}.control.primary{background:var(--ink);border-color:var(--ink);color:white;min-width:66px}.frame-counter{font-size:11px;color:var(--muted);margin-left:7px;white-space:nowrap;font-variant-numeric:tabular-nums}.segmented{display:flex;border:1px solid var(--line);border-radius:7px;padding:2px;gap:2px}.segmented button{border:0;background:transparent;font-size:10px;padding:5px 10px;border-radius:4px;color:var(--muted)}.segmented button.active{background:#eaf2f2;color:var(--teal);font-weight:650}.detail{padding:18px 23px 19px;border-top:1px solid #e8eef0}.detail-top{display:flex;justify-content:space-between;gap:15px;align-items:center;margin-bottom:7px}.detail-title{font-size:13px;font-weight:700}.status{padding:3px 8px;border-radius:5px;background:#edf3f5;font-size:10px;white-space:nowrap;color:#62778b}.status.ok{background:var(--teal-soft);color:var(--teal)}.status.fail{background:var(--orange-soft);color:#a76420}.detail-reason{font-size:12px;color:var(--muted);word-break:keep-all;overflow-wrap:anywhere}.state-line{margin-top:10px;font-size:10px;color:#778899;word-break:break-all}.trace-header-extra{font-size:10px;color:var(--muted)}.trace-list{padding:7px 10px;max-height:535px;overflow:auto;scrollbar-width:thin}.trace-item{display:flex;align-items:flex-start;text-align:left;gap:10px;width:100%;background:white;border:1px solid transparent;padding:11px 10px;border-radius:8px;margin:3px 0;transition:background .12s}.trace-item:hover{background:#f6f9fa}.trace-item.selected{background:#edf7f5;border-color:#c8e5df}.trace-index{flex-shrink:0;width:24px;height:24px;border-radius:6px;display:grid;place-items:center;background:#eff3f6;color:#6a8093;font-size:10px;font-weight:650;line-height:1}.trace-item.selected .trace-index{background:#d4ebe6;color:var(--teal)}.trace-content{min-width:0;flex:1}.trace-title{font-size:12px;font-weight:650;display:flex;justify-content:space-between;gap:8px}.trace-sub{font-size:10px;color:var(--muted);line-height:1.5;margin-top:3px;overflow-wrap:anywhere}.mini-state{font-size:9px;letter-spacing:0;color:var(--teal);font-weight:600;white-space:nowrap}.mini-state.fail{color:#bb732f}.trace-note{font-size:10px;color:var(--muted);background:#fafcfc;border-top:1px solid #e8eef0;padding:13px 20px;word-break:keep-all}.aside-card{margin-top:16px;padding:19px 21px}.aside-card h3{margin:0 0 8px;font-size:12px}.aside-card p{font-size:11px;color:var(--muted);word-break:keep-all}.metadata{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #e9eff1;padding-top:10px;margin-top:12px;font-size:10px;color:var(--muted)}.metadata strong{color:var(--ink);font-weight:550;overflow-wrap:anywhere;text-align:right}.footer{display:flex;justify-content:space-between;gap:15px;padding-top:24px;padding-bottom:27px;color:#84909c;font-size:10px}.empty{padding:35px 18px;text-align:center;color:var(--muted);font-size:12px}.hidden{display:none!important}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(min-width:1300px){.canvas-wrap{padding-top:16px}.intro{padding-top:37px;padding-bottom:29px}}
@media(max-width:1000px){.wrap{padding-left:24px;padding-right:24px}.layout{grid-template-columns:minmax(0,1fr) 295px}.controls{flex-wrap:wrap}.provenance{max-width:280px}.metrics{gap:9px}.metric{padding:15px}.canvas-wrap{padding-left:7px;padding-right:7px}}
@media(max-width:760px){.wrap{padding-left:18px;padding-right:18px}.topbar{padding-top:16px;padding-bottom:16px}.brand{font-size:16px}.topnote{display:none}.intro{padding-top:24px;display:block}.scope{display:inline-block;margin-top:13px}.toolbar{align-items:flex-start;flex-direction:column;gap:9px}.method-group{width:100%}.method-group select{min-width:0;flex:1;max-width:none}.provenance{text-align:left;max-width:none}.provenance strong{display:inline;margin-right:6px}.metrics{grid-template-columns:1fr 1fr;gap:8px;margin-bottom:15px}.metric-value{font-size:23px}.metric{padding:13px 15px}.layout{grid-template-columns:1fr;gap:15px}.canvas-wrap{min-height:290px}#scene-svg{min-height:270px}.panel-head{padding:15px 18px}.trace-list{max-height:310px}.aside-card{margin-top:12px}.controls{padding:13px 15px}.frame-counter{font-size:10px;margin-left:2px}.control{min-width:30px;padding:0 7px}.legend{gap:12px;padding-left:19px}.footer{flex-direction:column;gap:3px}.description{font-size:12px}.detail{padding:16px 18px}.trace-note{padding:12px 17px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<header><div class="wrap topbar"><div class="brand"><span class="brand-mark">2D</span>Disassembly Lab</div><div class="topnote">계획 제안 · 고정된 geometry 검사 · 실행 근거</div></div></header>
<main class="wrap">
  <section class="intro"><div><p class="eyebrow">Disassembly planning / evidence viewer</p><h1>분해 계획, 근거까지 한눈에.</h1><p class="description" id="scene-description"></p></div><span class="scope">2D geometry 기반 시연</span></section>
  <div class="toolbar"><div class="method-group"><label for="method-select" class="caption">실행 방법</label><select id="method-select" aria-label="표시할 실행 방법"></select></div><div class="provenance"><strong id="evidence-label"></strong><span id="evidence-description">브라우저는 저장된 기록을 표시합니다.</span></div></div>
  <section class="metrics" aria-label="실행 측정값">
    <div class="metric"><div class="metric-label">목표 부품 회수</div><div class="metric-value" id="metric-success">—</div><div class="metric-foot" id="metric-termination"></div></div>
    <div class="metric"><div class="metric-label">Checker 호출</div><div class="metric-value" id="metric-calls">—</div><div class="metric-foot">후보 행동을 검증한 횟수</div></div>
    <div class="metric"><div class="metric-label">제거한 부품</div><div class="metric-value" id="metric-removed">—</div><div class="metric-foot">기록된 최종 경로 기준</div></div>
    <div class="metric"><div class="metric-label">계획 실행 시간</div><div class="metric-value" id="metric-elapsed">—</div><div class="metric-foot">저장된 wall-clock 측정값</div></div>
  </section>
  <div class="layout">
    <section class="panel" aria-label="Geometry와 실행 상태">
      <div class="panel-head visual-head"><div><h2 id="scene-name"></h2><div class="scene-id" id="scene-id"></div></div><span class="target-chip" id="target-chip"></span></div>
      <div class="canvas-wrap"><div class="canvas-hint"><span class="hint-dot"></span><span id="canvas-hint">초기 배치 · +y는 위쪽</span></div><svg id="scene-svg" viewBox="0 0 900 550" role="img" aria-label="부품 배치와 검사한 이동 경로"></svg></div>
      <div class="legend"><span><i class="swatch target"></i>목표 부품</span><span><i class="swatch fixed"></i>고정 부품</span><span><i class="swatch blocker"></i>충돌 상대</span><span><i class="swatch sweep"></i>검사한 이동 영역</span></div>
      <div class="controls"><div class="transport"><button class="control" id="reset" title="초기 상태로" aria-label="초기 상태로">↺</button><button class="control" id="previous" title="이전 검사" aria-label="이전 검사">‹</button><button class="control primary" id="play">▶ 재생</button><button class="control" id="next" title="다음 검사" aria-label="다음 검사">›</button><span class="frame-counter" id="frame-counter"></span></div><div class="segmented" aria-label="표시할 상태"><button id="before" type="button" class="active" aria-pressed="true">검사 직전</button><button id="after" type="button" aria-pressed="false">검사 직후</button></div></div>
      <div class="detail" aria-live="polite"><div class="detail-top"><div class="detail-title" id="detail-title"></div><span class="status" id="detail-status"></span></div><p class="detail-reason" id="detail-reason"></p><p class="state-line" id="state-line"></p></div>
    </section>
    <aside>
      <section class="panel"><div class="panel-head"><h2>검사 기록</h2><span class="trace-header-extra" id="trace-count"></span></div><div class="trace-list" id="trace-list"></div><div class="trace-note">각 항목의 실제 저장 상태를 표시합니다. 탐색 중 다른 분기로 이동하면 부품 배치도 해당 상태로 바뀝니다.</div></section>
      <section class="panel aside-card"><h3>이 시연이 확인하는 범위</h3><p>직사각형 부품의 직선 이동과 충돌만 검사합니다. 3D 물리, 로봇 동작, 실제 분해 시간은 검증하지 않습니다.</p><div class="metadata"><span>데이터 구분</span><strong id="split-label"></strong></div><div class="metadata"><span>LLM 호출</span><strong id="llm-label"></strong></div><div class="metadata hidden" id="token-row"><span>Token 사용량</span><strong id="token-label"></strong></div></section>
    </aside>
  </div>
  <footer class="footer"><span>모든 수치는 입력된 실행 기록에서 표시합니다.</span><span>OFFLINE REPORT · 외부 연결 없이 열람 가능</span></footer>
</main>
<script id="report-data" type="application/json">__REPORT_DATA__</script>
<script>
"use strict";
(() => {
  const data = JSON.parse(document.getElementById("report-data").textContent);
  const scene = data.scene || {};
  const runs = data.runs || [];
  const parts = Array.isArray(scene.parts) ? scene.parts : [];
  const partMap = new Map(parts.map(p => [String(p.id), p]));
  const $ = id => document.getElementById(id);
  const put = (id, value) => { $(id).textContent = value == null ? "—" : String(value); };
  const NS = "http://www.w3.org/2000/svg";
  const svg = $("scene-svg");
  const direction = {up:[0,1,"↑ 위쪽"],down:[0,-1,"↓ 아래쪽"],left:[-1,0,"← 왼쪽"],right:[1,0,"→ 오른쪽"]};
  const methodNames = {exact:"Exact search",exact_search:"Exact search",exact_bfs:"Exact BFS · 최소 제거",bfs:"BFS search",dijkstra:"Dijkstra search",heuristic:"Geometry heuristic",heuristic_dfs:"Geometry heuristic · DFS",greedy:"Greedy heuristic",llm:"LLM planner",llm_feedback:"LLM · checker feedback",no_library:"LLM · library 없음",with_library:"LLM · library 사용",llm_no_memory:"LLM · memory 없음",llm_with_memory:"LLM · memory 사용",scripted:"Scripted planner",scripted_repair:"Scripted repair"};
  const reasonNames = {collision:"이동 영역에서 다른 부품과 충돌합니다.",clear:"이동 경로에 충돌이 없습니다.",valid:"이동 경로에 충돌이 없습니다.",ok:"이동 경로에 충돌이 없습니다.",fixed:"고정 부품은 제거할 수 없습니다.",fixed_part:"고정 부품은 제거할 수 없습니다.",direction_not_allowed:"이 부품에 허용되지 않은 이동 방향입니다.",invalid_direction:"지원하지 않는 이동 방향입니다.",invalid_action:"행동 형식이 올바르지 않습니다.",already_removed:"이미 제거한 부품입니다.",part_not_present:"현재 상태에 없는 부품입니다.",unknown_part:"등록되지 않은 부품입니다."};
  const terminationNames = {success:"목표 달성",goal_reached:"목표 달성",target_removed:"목표 달성",no_solution:"실행 가능한 계획을 찾지 못함",exhausted:"탐색 종료",search_exhausted:"탐색 종료",budget_exhausted:"검증 예산 소진",check_budget_exhausted:"검증 예산 소진",call_budget_exhausted:"LLM 호출 예산 소진",repeated_proposal:"동일한 제안 반복으로 종료",provider_error:"LLM provider 오류",max_steps:"단계 제한 도달",api_unavailable:"API 사용 불가",error:"실행 오류"};
  let runIndex = 0, frame = -1, phase = "before", timer = null;
  const run = () => runs[runIndex] || {};
  const traces = () => Array.isArray(run().trace) ? run().trace : [];
  const current = () => traces()[frame] || null;
  const ids = value => Array.isArray(value) ? value.map(String) : null;
  const remaining = () => {
    const t = current();
    if (!t) return parts.map(p => String(p.id));
    return ids(phase === "after" ? t.remaining_after : t.remaining_before);
  };
  const partLabel = id => {
    if (id == null) return "미지정 부품";
    const p = partMap.get(String(id));
    return p && p.label && String(p.label) !== String(id) ? `${id} · ${p.label}` : String(id);
  };
  function node(tag, attrs = {}, text = null) {
    const el = document.createElementNS(NS,tag);
    Object.entries(attrs).forEach(([key,val]) => el.setAttribute(key,String(val)));
    if (text !== null) el.textContent = String(text);
    return el;
  }
  function add(tag, attrs, text, parent=svg) { const el=node(tag,attrs,text);parent.appendChild(el);return el; }
  function metric(id,value,unit="") {
    $(id).replaceChildren();
    $(id).append(document.createTextNode(value == null ? "—" : String(value)));
    if (value != null && unit) { const s=document.createElement("small");s.textContent=unit;$(id).append(s); }
  }
  function describeProvenance(r) {
    const raw = [r.method,r.provenance,r.candidate_source,r.provider,r.backend,r.llm_backend].map(v=> typeof v === "string" ? v : JSON.stringify(v || "")).join(" ").toLowerCase();
    if (Number(r.llm_calls) > 0 && /live_llm_with_scripted|recovery_exercise/.test(raw+" "+r.evaluation_kind)) return ["스크립트 입력 + LLM 호출 기록","초기 실패를 주입한 복구 실험입니다. 일반 성능 평가와 구분합니다."];
    if (r.scripted || r.is_scripted || r.is_mock || /script|mock|fixture|replay/.test(raw)) return ["스크립트 후보 · 저장된 checker 기록","실제 LLM API 호출 결과로 해석하지 않습니다."];
    if (Number(r.llm_calls) > 0) return ["LLM 호출이 기록된 실행","호출 횟수는 해당 실행의 저장값입니다."];
    if (/llm|language_model/.test(raw)) return ["LLM 실행 여부 미확인","방법 이름만으로 API 실행을 판단하지 않습니다."];
    return ["저장된 실행 기록","브라우저는 저장된 기록을 표시합니다."];
  }
  function renderSummary() {
    const r=run();
    put("metric-success",r.success === true ? "회수 성공" : r.success === false ? "미달성" : "기록 없음");
    $("metric-success").className="metric-value " + (r.success === true ? "success" : "failure");
    put("metric-termination",terminationNames[r.termination] || r.termination || "종료 정보 없음");
    metric("metric-calls",r.checker_calls,"회");metric("metric-removed",r.removed_count,"개");
    const elapsed=r.elapsed_seconds;
    metric("metric-elapsed",typeof elapsed === "number" && Number.isFinite(elapsed) ? (elapsed < .001 ? elapsed.toFixed(6) : elapsed.toFixed(3)) : null,"초");
    const evidence=describeProvenance(r);put("evidence-label",evidence[0]);put("evidence-description",evidence[1]);
    put("llm-label",r.llm_calls == null ? "기록 없음" : `${r.llm_calls}회`);
    const usage=r.token_usage;
    $("token-row").classList.toggle("hidden",usage == null);
    if(usage != null) put("token-label",typeof usage === "object" ? Object.entries(usage).map(([k,v])=>`${k}: ${v}`).join(" / ") : usage);
    put("trace-count",`${traces().length}개 항목`);
  }
  function renderList() {
    const container=$("trace-list");container.replaceChildren();
    if (!traces().length) { const empty=document.createElement("div");empty.className="empty";empty.textContent="저장된 검사 기록이 없습니다.";container.append(empty);return; }
    traces().forEach((t,i)=>{
      const a=t.action || {}, c=t.check || {};
      const button=document.createElement("button");button.className="trace-item";button.type="button";button.dataset.index=String(i);
      const index=document.createElement("span");index.className="trace-index";index.textContent=String(t.step == null ? i+1 : t.step);
      const content=document.createElement("span");content.className="trace-content";
      const title=document.createElement("span");title.className="trace-title";
      const label=document.createElement("span");label.textContent=`${a.part_id == null ? "?" : a.part_id}  ${direction[a.direction]?.[2] || a.direction || "방향 없음"}`;
      const status=document.createElement("span");status.className="mini-state"+(c.valid === false?" fail":"");status.textContent=c.valid===true?"통과":c.valid===false?"거부":"미확인";
      title.append(label,status);
      const sub=document.createElement("span");sub.className="trace-sub";sub.style.display="block";
      const source=t.proposal_source && /script|mock/.test(t.proposal_source) ? "[스크립트 입력] " : t.proposal_source && t.llm_call ? `[LLM 제안 ${t.llm_call}] ` : "";
      sub.textContent=source+(reasonNames[c.reason] || c.reason || "진단 정보 없음");
      content.append(title,sub);button.append(index,content);button.addEventListener("click",()=>{stop();frame=i;renderFrame();});container.append(button);
    });
  }
  function renderGeometry() {
    svg.replaceChildren();
    const w=Array.isArray(scene.workspace) && scene.workspace.length===4 ? scene.workspace.map(Number) : [0,0,10,10];
    const validBounds=w.every(Number.isFinite) && w[2]>w[0] && w[3]>w[1];
    if(!validBounds){add("text",{x:450,y:270,"text-anchor":"middle",fill:"#66778a","font-size":16},"유효한 workspace 좌표가 없습니다.");return;}
    const [xmin,ymin,xmax,ymax]=w, ww=xmax-xmin, wh=ymax-ymin;
    const scale=Math.min(690/ww,390/wh), ox=(900-ww*scale)/2, oy=(550-wh*scale)/2+4;
    const X=x=>ox+(x-xmin)*scale,Y=y=>oy+(ymax-y)*scale;
    const rectangle=rect=>{
      if(!Array.isArray(rect)||rect.length!==4)return null;
      const [x,y,rw,rh]=rect.map(Number);
      if(![x,y,rw,rh].every(Number.isFinite)||rw<=0||rh<=0)return null;
      return {x:X(x),y:Y(y+rh),width:rw*scale,height:rh*scale};
    };
    const defs=add("defs",{});
    const grid=add("pattern",{id:"grid",width:Math.max(8,scale),height:Math.max(8,scale),patternUnits:"userSpaceOnUse",x:ox,y:oy},null,defs);
    add("path",{d:`M ${Math.max(8,scale)} 0 L 0 0 0 ${Math.max(8,scale)}`,fill:"none",stroke:"#e4eeec","stroke-width":1},null,grid);
    const marker=add("marker",{id:"arrow",viewBox:"0 0 10 10",refX:8,refY:5,markerWidth:6,markerHeight:6,orient:"auto-start-reverse"},null,defs);
    add("path",{d:"M 0 0 L 10 5 L 0 10 z",fill:"#ce7a27"},null,marker);
    add("rect",{x:ox,y:oy,width:ww*scale,height:wh*scale,rx:3,fill:"#fbfdfc",stroke:"#b9ceca","stroke-width":1.3});
    add("rect",{x:ox,y:oy,width:ww*scale,height:wh*scale,fill:"url(#grid)"});
    add("text",{x:ox+2,y:oy+wh*scale+21,fill:"#99aaa9","font-size":10},`${xmin}, ${ymin}`);
    add("text",{x:ox+ww*scale-2,y:oy-11,fill:"#99aaa9","font-size":10,"text-anchor":"end"},`${xmax}, ${ymax}`);
    const t=current(), c=t?.check||{}, a=t?.action||{}, activeId=a.part_id == null ? null:String(a.part_id);
    const state=remaining();
    if(state===null){add("text",{x:450,y:270,"text-anchor":"middle",fill:"#66778a","font-size":15},"해당 검사 상태가 기록되지 않았습니다.");return;}
    const present=new Set(state);
    const blockers=new Set((Array.isArray(c.blockers)?c.blockers:[]).map(b=>String(b && typeof b==="object" ? b.part_id??b.id : b)));
    const sweepGroup=add("g",{"aria-label":"검사한 이동 영역"});
    for(const r of c.swept_rects||[]){const rect=rectangle(r);if(rect)add("rect",{...rect,fill:"#f6c977","fill-opacity":.28,stroke:"#d9943b","stroke-width":1.4,"stroke-dasharray":"5 4"},null,sweepGroup);}
    for(const p of parts){
      const id=String(p.id),exists=present.has(id),active=id===activeId,isTarget=id===String(scene.target_id),blocked=blockers.has(id);
      if(!exists&&!active)continue;
      const group=add("g",{"aria-label":`${partLabel(id)}${exists?"":" · 제거됨"}`});
      add("title",{},`${partLabel(id)}${p.fixed?" · 고정": ""}${exists?"":" · 제거됨"}`,group);
      let fill=p.fixed?"#344c62":isTarget?"#0c8e8d":blocked?"#d98177":"#8fa9c1";
      let stroke=blocked?"#bd564c":active?"#c97b26":isTarget?"#066f72":"#718da7";
      const rects=(p.rects||[]).map(rectangle).filter(Boolean);
      for(const rect of rects)add("rect",{...rect,rx:Math.min(4,rect.width*.08,rect.height*.08),fill:exists?fill:"none","fill-opacity":exists?1:0,stroke,"stroke-width":active?3:1.4,"stroke-dasharray":exists?"none":"5 4",opacity:exists?1:.55},null,group);
      if(rects.length){
        const biggest=rects.reduce((best,r)=>r.width*r.height>best.width*best.height?r:best,rects[0]);
        const vertical=biggest.height>biggest.width*2 && id.length>5;
        const availableWidth=vertical?biggest.height:biggest.width,availableHeight=vertical?biggest.width:biggest.height;
        const fs=Math.max(8,Math.min(17,availableHeight*.4,(availableWidth-10)/Math.max(2,id.length)*1.6));
        const tx=biggest.x+biggest.width/2,ty=biggest.y+biggest.height/2;
        add("text",{x:tx,y:ty+fs*.34,"text-anchor":"middle",fill:exists?"#fff":"#b37939","font-size":fs,"font-weight":700,...(vertical?{transform:`rotate(-90 ${tx} ${ty})`}:{})},id,group);
        if(!vertical && exists && biggest.height>48 && biggest.width>65 && (isTarget||p.fixed))add("text",{x:tx,y:ty+fs*.34+17,"text-anchor":"middle",fill:"#ffffffc7","font-size":9,"letter-spacing":1},isTarget?"TARGET":"FIXED",group);
      }
    }
    const active=partMap.get(activeId),dir=direction[a.direction];
    if(active&&dir&&(active.rects||[]).length){
      const first=active.rects[0].map(Number),cx=X(first[0]+first[2]/2),cy=Y(first[1]+first[3]/2);
      const distance=typeof c.distance==="number"&&c.distance>0?Math.min(c.distance*scale,110):65;
      const dx=dir[0],dy=-dir[1],start=Math.min(first[2]*scale/2,first[3]*scale/2)+9;
      const length=Math.max(start+25,distance);
      add("line",{x1:cx+dx*start,y1:cy+dy*start,x2:cx+dx*length,y2:cy+dy*length,stroke:"#ce7a27","stroke-width":3,"stroke-linecap":"round","marker-end":"url(#arrow)"});
    }
  }
  function renderFrame() {
    const t=current(), ts=traces(), r=run();
    put("frame-counter",frame<0?`초기 상태 / ${ts.length}회 검사`:`${frame+1} / ${ts.length}회 검사`);
    put("canvas-hint",frame<0?"초기 배치 · +y는 위쪽":`${phase==="before"?"검사 직전":"검사 직후"} · 저장된 상태`);
    $("previous").disabled=frame<0;$("next").disabled=!ts.length||frame>=ts.length-1;$("play").disabled=!ts.length;
    $("before").classList.toggle("active",phase==="before");$("after").classList.toggle("active",phase==="after");
    $("before").setAttribute("aria-pressed",String(phase==="before"));$("after").setAttribute("aria-pressed",String(phase==="after"));
    document.querySelectorAll(".trace-item").forEach(el=>{const selected=Number(el.dataset.index)===frame;el.classList.toggle("selected",selected);el.setAttribute("aria-current",String(selected));});
    if(!t){
      put("detail-title","시작 상태");put("detail-status","초기 배치");$("detail-status").className="status";
      put("detail-reason",ts.length?"검사 기록을 선택하거나 재생 버튼을 누르면, 후보 행동과 검증 결과를 확인할 수 있습니다.":"이 실행에는 검사 trace가 없습니다. 초기 배치와 저장된 요약 정보만 표시합니다.");
    }else{
      const a=t.action||{},c=t.check||{};
      put("detail-title",`${partLabel(a.part_id)} · ${direction[a.direction]?.[2]||a.direction||"방향 미지정"}`);
      put("detail-status",c.valid===true?"이동 가능":c.valid===false?"이동 거부":"결과 미확인");
      $("detail-status").className="status "+(c.valid===true?"ok":c.valid===false?"fail":"");
      let reason=reasonNames[c.reason]||c.reason||"진단 정보가 기록되지 않았습니다.";
      if(Array.isArray(c.blockers)&&c.blockers.length)reason+=` 충돌 상대: ${c.blockers.map(b=>b && typeof b==="object" ? b.part_id??b.id : b).join(", ")}.`;
      if(t.proposal_source && /script|mock/.test(t.proposal_source))reason+=" 이 후보는 시연용 스크립트에서 입력했습니다.";
      put("detail-reason",reason);
    }
    const state=remaining();put("state-line",state===null?"상태 정보 없음 · 앞선 trace에서 추정하지 않습니다.":`남은 부품 ${state.length}개  ·  ${state.join("  ")||"없음"}`);
    renderGeometry();
    if(timer!==null && frame>=0)document.querySelector(`.trace-item[data-index="${frame}"]`)?.scrollIntoView({block:"nearest"});
  }
  function stop(){if(timer!==null)window.clearInterval(timer);timer=null;put("play","▶ 재생");}
  $("reset").addEventListener("click",()=>{stop();frame=-1;renderFrame();});
  $("previous").addEventListener("click",()=>{stop();frame=Math.max(-1,frame-1);renderFrame();});
  $("next").addEventListener("click",()=>{stop();frame=Math.min(traces().length-1,frame+1);renderFrame();});
  $("before").addEventListener("click",()=>{phase="before";renderFrame();});
  $("after").addEventListener("click",()=>{phase="after";renderFrame();});
  $("play").addEventListener("click",()=>{
    if(timer!==null){stop();return;}
    if(frame>=traces().length-1)frame=-1;
    put("play","Ⅱ 일시정지");
    timer=window.setInterval(()=>{if(frame>=traces().length-1){stop();return;}frame++;renderFrame();},950);
    frame++;renderFrame();
  });
  $("method-select").addEventListener("change",()=>{stop();runIndex=Number($("method-select").value);frame=-1;renderSummary();renderList();renderFrame();});
  put("scene-name",scene.name||"Assembly scene");put("scene-id",scene.id||"식별자 없음");put("target-chip",`목표 ${scene.target_id||"미지정"}`);
  put("scene-description",scene.description||"목표 부품을 꺼내는 과정을 살펴보고, 각 행동의 geometry 검사 결과를 확인하세요.");
  const splitNames={dev:"개발용",development:"개발용",train:"개발용",test:"평가용",heldout:"Held-out 평가용",demo:"시연용"};
  put("split-label",splitNames[scene.split]||scene.split||"미지정");
  if(runs.length){runs.forEach((r,i)=>{const option=document.createElement("option");option.value=String(i);option.textContent=methodNames[r.method]||r.method||`실행 ${i+1}`;$("method-select").append(option);});}
  else{const option=document.createElement("option");option.textContent="실행 기록 없음";$("method-select").append(option);$("method-select").disabled=true;}
  renderSummary();renderList();renderFrame();
})();
</script>
</body>
</html>
'''
