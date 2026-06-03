HARMONIA_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>갈등 조정 시스템 — HARMONIA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Noto Sans KR','Segoe UI',sans-serif;background:#f5f7fa;color:#1f2937;font-size:15px}
.hd{background:#1e3a5f;color:#fff;padding:28px;text-align:center}
.hd h1{font-size:1.65rem;font-weight:800;margin-bottom:6px}
.hd p{font-size:.92rem;opacity:.8}
.wrap{max-width:860px;margin:24px auto;padding:0 16px 80px}
.card{background:#fff;border-radius:14px;padding:24px;margin-bottom:16px;box-shadow:0 2px 10px rgba(0,0,0,.07)}
.ch{display:flex;align-items:center;gap:10px;margin-bottom:18px}
.cn{background:#1e3a5f;color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:800;flex-shrink:0}
.ct{font-size:1rem;font-weight:700;color:#1e3a5f}
.tcg{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
.tc{border:2px solid #e5e7eb;border-radius:12px;padding:16px 10px;text-align:center;cursor:pointer;transition:all .15s}
.tc:hover{border-color:#3b82f6;background:#eff6ff;transform:translateY(-2px)}
.tc.on{border-color:#1e3a5f;background:#dbeafe}
.tc .ti{font-size:1.9rem;margin-bottom:6px}
.tc .tn{font-size:.85rem;font-weight:700;color:#374151}
.tc .td{font-size:.72rem;color:#9ca3af;margin-top:3px}
.field{margin-bottom:15px}
.fl{display:block;font-size:.82rem;font-weight:700;color:#374151;margin-bottom:6px}
.fd{font-size:.73rem;color:#9ca3af;margin-top:4px}
/* ═══ 캐스케이드 드롭다운 ═══ */
.csel{position:relative}
.csel-btn{display:flex;align-items:center;justify-content:space-between;padding:11px 14px;border:2px solid #e5e7eb;border-radius:9px;background:#fff;cursor:pointer;transition:border-color .15s;font-size:.93rem;color:#1f2937;user-select:none;min-height:44px}
.csel-btn:hover{border-color:#93c5fd}
.csel-btn.open{border-color:#1e3a5f;border-bottom-left-radius:0;border-bottom-right-radius:0;background:#f8faff}
.csel-txt{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.csel-arr{font-size:.72rem;color:#9ca3af;margin-left:8px;flex-shrink:0;transition:transform .2s}
.csel-btn.open .csel-arr{transform:rotate(180deg)}
.csel-panel{display:none;position:absolute;top:calc(100% - 2px);left:0;right:0;z-index:9999;background:#fff;border:2px solid #1e3a5f;border-top:1px solid #dbeafe;border-radius:0 0 10px 10px;box-shadow:0 8px 24px rgba(0,0,0,.13)}
.csel-panel.show{display:block}
.csel-search{width:100%;border:none;border-bottom:1px solid #e5e7eb;padding:10px 14px;font-size:.88rem;outline:none;background:#f8fafc;color:#374151}
.csel-list{max-height:230px;overflow-y:auto}
.csel-item{padding:10px 14px;cursor:pointer;font-size:.9rem;color:#374151;line-height:1.4;transition:background .1s}
.csel-item:hover{background:#eff6ff;color:#1d4ed8}
.csel-item.on{background:#dbeafe;color:#1d4ed8;font-weight:700}
.csel-coef{font-size:.75rem;color:#9ca3af;float:right;margin-left:8px;font-family:monospace}
.csel-empty{padding:12px 14px;font-size:.85rem;color:#9ca3af;font-style:italic}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:600px){.two{grid-template-columns:1fr}}
.inst{border:2px solid #e5e7eb;border-radius:12px;padding:18px}
.inst.ia{border-color:#3b82f6}.inst.ib{border-color:#ef4444}
.inst h3{font-size:.92rem;font-weight:800;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid #f3f4f6}
.ia h3{color:#2563eb}.ib h3{color:#dc2626}
details{background:#fff;border-radius:14px;margin-bottom:16px;box-shadow:0 2px 10px rgba(0,0,0,.07);overflow:hidden}
details summary{padding:16px 22px;cursor:pointer;font-size:.92rem;font-weight:700;color:#1e3a5f;list-style:none;display:flex;align-items:center;gap:8px}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"▶";font-size:.7rem;transition:transform .2s;flex-shrink:0}
details[open] summary::before{transform:rotate(90deg)}
.adv-body{padding:4px 22px 22px;border-top:1px solid #f3f4f6}
.adv-note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:11px 15px;font-size:.8rem;color:#92400e;margin:14px 0}
.bcols{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:600px){.bcols{grid-template-columns:1fr}}
.bcol h4{font-size:.85rem;font-weight:800;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid}
.bca h4{color:#2563eb;border-color:#3b82f6}.bcb h4{color:#dc2626;border-color:#ef4444}
.run-wrap{text-align:center;margin:6px 0 20px}
.run-btn{background:#1e3a5f;color:#fff;border:none;border-radius:12px;padding:16px 50px;font-size:1.1rem;font-weight:800;cursor:pointer;box-shadow:0 4px 16px rgba(30,58,95,.3);transition:all .2s}
.run-btn:hover{background:#2d5a8e;transform:translateY(-2px)}
.run-btn:disabled{background:#9ca3af;transform:none;box-shadow:none;cursor:not-allowed}
#results{display:none}
.rst{display:flex;align-items:flex-start;gap:10px;padding:14px 18px;border-radius:10px;margin-bottom:20px;font-size:.93rem;font-weight:600}
.rs-ok{background:#d1fae5;color:#065f46;border:1px solid #a7f3d0}
.rs-no{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}
.rs-wn{background:#fef3c7;color:#92400e;border:1px solid #fde68a}
.sec-lbl{font-size:.74rem;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
.alloc-bar{height:52px;border-radius:10px;display:flex;overflow:hidden;margin-bottom:12px}
.aa{background:#2563eb;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.88rem;transition:width .8s ease;overflow:hidden;padding:0 8px;white-space:nowrap}
.ab{background:#ef4444;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:.88rem;transition:width .8s ease;overflow:hidden;padding:0 8px;white-space:nowrap}
.alloc-g{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.ac{border-radius:10px;padding:14px 16px}
.aca{background:#eff6ff;border:1px solid #bfdbfe}.acb{background:#fef2f2;border:1px solid #fecaca}
.ac .aon{font-size:.78rem;color:#6b7280;margin-bottom:4px}
.ac .anum{font-size:1.4rem;font-weight:800;margin-bottom:2px}
.aca .anum{color:#2563eb}.acb .anum{color:#dc2626}
.ac .apct{font-size:.78rem;color:#6b7280}
.util-g{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.uc{border-radius:10px;padding:14px;text-align:center}
.uca{background:#eff6ff;border:1px solid #bfdbfe}.ucb{background:#fef2f2;border:1px solid #fecaca}
.ul{font-size:.76rem;color:#6b7280;margin-bottom:6px}
.us{font-size:1.35rem;font-weight:800;margin-bottom:4px}
.uca .us{color:#2563eb}.ucb .us{color:#dc2626}
.ui{font-size:.78rem;color:#374151}
.note-box{background:#f8fafc;border-left:4px solid #1e3a5f;border-radius:0 10px 10px 0;padding:14px 16px;margin-bottom:16px}
.nt{font-size:.73rem;font-weight:700;color:#1e3a5f;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.nc{font-size:.9rem;line-height:1.75;color:#374151}
/* ═══ 산출 근거 패널 ═══ */
.calc-details{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:16px;overflow:hidden}
.calc-details summary{padding:14px 20px;cursor:pointer;font-size:.88rem;font-weight:700;color:#374151;background:#f1f5f9;list-style:none;display:flex;align-items:center;gap:8px}
.calc-details summary::-webkit-details-marker{display:none}
.calc-details summary::before{content:"▶";font-size:.68rem;transition:transform .2s;flex-shrink:0;color:#64748b}
.calc-details[open] summary::before{transform:rotate(90deg)}
.calc-body{padding:20px}
.calc-sec{margin-bottom:24px}
.calc-sec:last-child{margin-bottom:0}
.calc-sec-title{font-size:.82rem;font-weight:800;color:#1e3a5f;margin-bottom:12px;display:flex;align-items:center;gap:6px}
/* 공식 박스 */
.formula-box{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px 20px;font-family:'Courier New',monospace;font-size:.88rem;line-height:2;color:#1f2937;overflow-x:auto}
.formula-box .f-main{font-size:.95rem;font-weight:700;color:#1e3a5f;border-bottom:1px solid #e2e8f0;padding-bottom:10px;margin-bottom:10px}
.formula-box .f-row{display:flex;gap:16px;padding:3px 0}
.formula-box .f-eq{flex-shrink:0;color:#374151}
.formula-box .f-note{font-size:.75rem;color:#6b7280;font-family:-apple-system,sans-serif;font-style:italic;flex:1}
.formula-box .f-constraint{color:#7c3aed;font-size:.85rem;margin-top:8px;padding-top:8px;border-top:1px solid #f0e6ff}
/* 파라미터 테이블 */
.param-table{width:100%;border-collapse:collapse;font-size:.85rem}
.param-table th{background:#f1f5f9;padding:8px 12px;text-align:left;font-size:.78rem;font-weight:700;color:#475569;border-bottom:2px solid #e2e8f0}
.param-table td{padding:8px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
.param-table tr:hover td{background:#f8fafc}
.param-table .sym{font-family:'Courier New',monospace;font-weight:700;color:#7c3aed;font-size:.88rem}
.param-table .val-a{color:#2563eb;font-weight:700;font-family:monospace}
.param-table .val-b{color:#dc2626;font-weight:700;font-family:monospace}
.param-table .result-row td{background:#f0fdf4;font-weight:700;border-top:2px solid #86efac}
/* 최적화 요약 */
.optim-box{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:560px){.optim-box{grid-template-columns:1fr}}
.optim-card{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px}
.optim-card .ok{font-size:.74rem;color:#6b7280;margin-bottom:4px}
.optim-card .ov{font-size:.95rem;font-weight:700;color:#1e3a5f;font-family:monospace}
</style>
</head>
<body>

<div class="hd">
  <h1>🤝 부처·기관 간 갈등 조정 시스템</h1>
  <p>내시 바게닝 × 심리적 편향 7종 — 선택만으로 최적 합의안을 도출합니다</p>
</div>

<div class="wrap">

<!-- 1. 갈등 유형 -->
<div class="card">
  <div class="ch"><div class="cn">1</div><span class="ct">어떤 문제를 해결하려 하시나요?</span></div>
  <div class="tcg">
    <div class="tc on" data-type="예산 배분" data-mode="budget" onclick="pickType(this)"><div class="ti">💰</div><div class="tn">예산 배분</div><div class="td">예산을 나누는 문제</div></div>
    <div class="tc" data-type="사업 관할권" data-mode="point" onclick="pickType(this)"><div class="ti">🗺️</div><div class="tn">사업 관할권</div><div class="td">담당 영역 분쟁</div></div>
    <div class="tc" data-type="인력 배분" data-mode="person" onclick="pickType(this)"><div class="ti">👥</div><div class="tn">인력 배분</div><div class="td">정원·조직 분쟁</div></div>
    <div class="tc" data-type="규제 권한" data-mode="point" onclick="pickType(this)"><div class="ti">⚖️</div><div class="tn">규제 권한</div><div class="td">규제·심의 분쟁</div></div>
    <div class="tc" data-type="정책 우선순위" data-mode="point" onclick="pickType(this)"><div class="ti">📋</div><div class="tn">정책 우선순위</div><div class="td">정책 비중 분쟁</div></div>
  </div>
</div>

<!-- 2. 총 자원 -->
<div class="card">
  <div class="ch"><div class="cn">2</div><span class="ct" id="trTitle">두 기관이 나눌 총 예산은 얼마인가요?</span></div>
  <div class="field"><div id="trSel" class="csel"></div><div class="fd" id="trDesc">나눌 총 예산 금액을 선택하세요</div></div>
</div>

<!-- 3. 두 기관 -->
<div class="card">
  <div class="ch"><div class="cn">3</div><span class="ct">두 기관의 현황을 선택해 주세요</span></div>
  <div class="two">
    <div class="inst ia">
      <h3>🔵 A 기관</h3>
      <div class="field"><label class="fl">기관 이름</label><div id="anSel" class="csel"></div></div>
      <div class="field"><label class="fl" id="ax0L">현재 배분액 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(준거점 x₀)</span></label><div id="ax0Sel" class="csel"></div><div class="fd">손실회피·앵커링 계산의 기준점</div></div>
      <div class="field"><label class="fl">최소한 받아야 할 양 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(체면 마지노선 M)</span></label><div id="aMSel" class="csel"></div><div class="fd">이보다 적으면 ∞ 페널티 부과</div></div>
      <div class="field"><label class="fl">협상 영향력 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(권한 가중치 w)</span></label><div id="awSel" class="csel"></div></div>
      <div class="field"><label class="fl">결렬 시 피해 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(결렬점 d)</span></label><div id="adSel" class="csel"></div></div>
    </div>
    <div class="inst ib">
      <h3>🔴 B 기관</h3>
      <div class="field"><label class="fl">기관 이름</label><div id="bnSel" class="csel"></div></div>
      <div class="field"><label class="fl" id="bx0L">현재 배분액 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(준거점 x₀)</span></label><div id="bx0Sel" class="csel"></div><div class="fd">손실회피·앵커링 계산의 기준점</div></div>
      <div class="field"><label class="fl">최소한 받아야 할 양 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(체면 마지노선 M)</span></label><div id="bMSel" class="csel"></div><div class="fd">이보다 적으면 ∞ 페널티 부과</div></div>
      <div class="field"><label class="fl">협상 영향력 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(권한 가중치 w)</span></label><div id="bwSel" class="csel"></div></div>
      <div class="field"><label class="fl">결렬 시 피해 <span style="font-size:.72rem;color:#9ca3af;font-weight:400">(결렬점 d)</span></label><div id="bdSel" class="csel"></div></div>
    </div>
  </div>
</div>

<!-- 4. 관계 -->
<div class="card">
  <div class="ch"><div class="cn">4</div><span class="ct">두 기관의 평소 관계 <span style="font-size:.82rem;color:#9ca3af;font-weight:400">(반응적 가치하락 지수 H)</span></span></div>
  <div class="field"><div id="hostSel" class="csel"></div><div class="fd">높을수록 상대방 제안의 객관적 가치를 낮게 평가하는 경향이 강해집니다</div></div>
</div>

<!-- 5. 협상 성향 -->
<details>
  <summary>심리적 편향 7종 세부 설정 <span style="font-size:.8rem;color:#9ca3af;font-weight:400">(선택사항 — 기본값으로도 충분합니다)</span></summary>
  <div class="adv-body">
    <div class="adv-note">💡 각 항목 옆의 기호(λ, α 등)는 수학 모델에서 쓰이는 계수입니다. 괄호 안 숫자가 실제 적용값입니다.</div>
    <div class="bcols">
      <div class="bcol bca">
        <h4>🔵 A 기관의 심리적 편향</h4>
        <div class="field"><label class="fl">② 손실회피·부존효과 (λ)</label><div id="aLambdaSel" class="csel"></div><div class="fd">λ × max(0, x₀ − x) 로 손실 페널티 계산</div></div>
        <div class="field"><label class="fl">① 자기고양 편향 (α)</label><div id="aAlphaSel" class="csel"></div><div class="fd">기본 효용 = x × (2 − α)</div></div>
        <div class="field"><label class="fl">③ 제로섬 사고 (γ)</label><div id="aGammaSel" class="csel"></div><div class="fd">γ × x_상대방 를 내 손실로 환산</div></div>
        <div class="field"><label class="fl">④ 앵커링 집착 (δ)</label><div id="aDeltaSel" class="csel"></div><div class="fd">δ × max(0, 첫요구안 − x) 로 저항 계산</div></div>
        <div class="field"><label class="fl">⑤ 후회 회피 (ρ)</label><div id="aRhoSel" class="csel"></div><div class="fd">ρ × max(0, x − x₀) 로 과다 이득 불안 반영</div></div>
        <div class="field"><label class="fl">⑥ 시기심·불평등혐오 (β)</label><div id="aBetaSel" class="csel"></div><div class="fd">β × (1+H) × max(0, x_상대방 − x)</div></div>
      </div>
      <div class="bcol bcb">
        <h4>🔴 B 기관의 심리적 편향</h4>
        <div class="field"><label class="fl">② 손실회피·부존효과 (λ)</label><div id="bLambdaSel" class="csel"></div><div class="fd">λ × max(0, x₀ − x) 로 손실 페널티 계산</div></div>
        <div class="field"><label class="fl">① 자기고양 편향 (α)</label><div id="bAlphaSel" class="csel"></div><div class="fd">기본 효용 = x × (2 − α)</div></div>
        <div class="field"><label class="fl">③ 제로섬 사고 (γ)</label><div id="bGammaSel" class="csel"></div><div class="fd">γ × x_상대방 를 내 손실로 환산</div></div>
        <div class="field"><label class="fl">④ 앵커링 집착 (δ)</label><div id="bDeltaSel" class="csel"></div><div class="fd">δ × max(0, 첫요구안 − x) 로 저항 계산</div></div>
        <div class="field"><label class="fl">⑤ 후회 회피 (ρ)</label><div id="bRhoSel" class="csel"></div><div class="fd">ρ × max(0, x − x₀) 로 과다 이득 불안 반영</div></div>
        <div class="field"><label class="fl">⑥ 시기심·불평등혐오 (β)</label><div id="bBetaSel" class="csel"></div><div class="fd">β × (1+H) × max(0, x_상대방 − x)</div></div>
      </div>
    </div>
  </div>
</details>

<!-- 실행 -->
<div class="run-wrap"><button class="run-btn" id="runBtn" onclick="run()">🔍 합의안 찾기</button></div>

<!-- 결과 -->
<div class="card" id="results">
  <div class="ch"><div class="cn">✓</div><span class="ct">분석 결과</span></div>
  <div id="statusMsg"></div>
  <div class="sec-lbl">최적 배분안</div>
  <div class="alloc-bar"><div class="aa" id="aa"></div><div class="ab" id="ab"></div></div>
  <div class="alloc-g">
    <div class="ac aca"><div class="aon" id="aon">A 기관</div><div class="anum" id="anum">—</div><div class="apct" id="apct"></div></div>
    <div class="ac acb"><div class="aon" id="bon">B 기관</div><div class="anum" id="bnum">—</div><div class="apct" id="bpct"></div></div>
  </div>
  <div class="util-g">
    <div class="uc uca"><div class="ul" id="uaLbl">A 기관 수용 가능성</div><div class="us" id="uaScore">—</div><div class="ui" id="uaInterp"></div></div>
    <div class="uc ucb"><div class="ul" id="ubLbl">B 기관 수용 가능성</div><div class="us" id="ubScore">—</div><div class="ui" id="ubInterp"></div></div>
  </div>
  <div class="note-box"><div class="nt">분석 해설</div><div class="nc" id="nc"></div></div>

  <!-- 산출 근거 패널 -->
  <details class="calc-details" id="calcDetails">
    <summary>📐 산출 근거 및 계산 과정 보기</summary>
    <div class="calc-body" id="calcBody"></div>
  </details>
</div>

</div>
<script>
// ── 데이터 ──────────────────────────────────────────────────────────
const AGENCIES=['기획재정부','과학기술정보통신부','교육부','외교부','통일부','법무부','국방부','행정안전부','문화체육관광부','농림축산식품부','산업통상자원부','보건복지부','환경부','고용노동부','여성가족부','국토교통부','해양수산부','중소벤처기업부','국가보훈부','국무조정실','감사원','공정거래위원회','금융위원회','방송통신위원회','국민권익위원회','개인정보보호위원회','원자력안전위원회','식품의약품안전처','질병관리청','기상청','통계청','조달청','국세청','관세청','경찰청','소방청','산림청','농촌진흥청','특허청','방위사업청'].map(a=>({l:a,v:a}));
const BUDGET_OPTS=[10,20,30,50,80,100,150,200,300,500,1000].map(v=>({l:v.toLocaleString()+'억 원',v}));
const PERSON_OPTS=[30,50,80,100,150,200,300,500].map(v=>({l:v+'명',v}));
const POINT_OPTS=[{l:'100점',v:100}];

// 계수값을 레이블에 표시
const POWER_OPTS=[{l:'매우 약함',v:0.5,c:'w = 0.5'},{l:'약한 편',v:0.8,c:'w = 0.8'},{l:'보통',v:1.0,c:'w = 1.0'},{l:'강한 편',v:1.3,c:'w = 1.3'},{l:'강함',v:1.7,c:'w = 1.7'},{l:'매우 강함',v:2.5,c:'w = 2.5'}];
const DAMAGE_OPTS=[{l:'거의 없음',v:2,c:'d = 2'},{l:'약간 있음',v:5,c:'d = 5'},{l:'보통',v:10,c:'d = 10'},{l:'큰 편',v:20,c:'d = 20'},{l:'매우 큼',v:35,c:'d = 35'},{l:'치명적',v:50,c:'d = 50'}];
const HOST_OPTS=[{l:'😊 매우 우호적',v:0,c:'H = 0'},{l:'🙂 우호적',v:0.2,c:'H = 0.2'},{l:'😐 중립',v:0.5,c:'H = 0.5'},{l:'😒 약간 갈등',v:0.8,c:'H = 0.8'},{l:'😠 갈등',v:1.0,c:'H = 1.0'},{l:'😡 심각한 갈등',v:1.5,c:'H = 1.5'},{l:'🤬 극도의 적대',v:2.0,c:'H = 2.0'}];
const LOSS_OPTS=[{l:'거의 개의치 않음',v:0.5,c:'λ = 0.5'},{l:'약간 민감',v:1.0,c:'λ = 1.0'},{l:'보통',v:1.5,c:'λ = 1.5'},{l:'많이 민감',v:2.2,c:'λ = 2.2'},{l:'매우 민감',v:3.5,c:'λ = 3.5'},{l:'극단적',v:5.0,c:'λ = 5.0'}];
const ALPHA_OPTS=[{l:'매우 객관적',v:1.0,c:'α = 1.0'},{l:'약간 과대평가',v:1.1,c:'α = 1.1'},{l:'보통',v:1.3,c:'α = 1.3'},{l:'많이 과대평가',v:1.6,c:'α = 1.6'},{l:'매우 과대평가',v:2.0,c:'α = 2.0'}];
const GAMMA_OPTS=[{l:'협력 지향',v:0.1,c:'γ = 0.1'},{l:'약간 경쟁적',v:0.3,c:'γ = 0.3'},{l:'보통',v:0.5,c:'γ = 0.5'},{l:'경쟁적',v:0.7,c:'γ = 0.7'},{l:'강한 제로섬',v:1.0,c:'γ = 1.0'}];
const DELTA_OPTS=[{l:'매우 유연함',v:0.2,c:'δ = 0.2'},{l:'유연한 편',v:0.5,c:'δ = 0.5'},{l:'보통',v:0.8,c:'δ = 0.8'},{l:'집착하는 편',v:1.2,c:'δ = 1.2'},{l:'강한 집착',v:2.0,c:'δ = 2.0'}];
const RHO_OPTS=[{l:'거의 없음',v:0.1,c:'ρ = 0.1'},{l:'약간',v:0.3,c:'ρ = 0.3'},{l:'보통',v:0.5,c:'ρ = 0.5'},{l:'높음',v:0.7,c:'ρ = 0.7'},{l:'매우 높음',v:1.0,c:'ρ = 1.0'}];
const BETA_OPTS=[{l:'개의치 않음',v:0.1,c:'β = 0.1'},{l:'약간 불편',v:0.3,c:'β = 0.3'},{l:'보통',v:0.5,c:'β = 0.5'},{l:'많이 불편',v:0.8,c:'β = 0.8'},{l:'매우 불쾌함',v:1.2,c:'β = 1.2'},{l:'극단적',v:2.0,c:'β = 2.0'}];

function shareOpts(total,unit){
  return [5,10,15,20,25,30,35,40,45,50,55,60,65,70].map(p=>{
    const v=Math.round(total*p/100);
    return {l:(unit==='억 원'?v.toLocaleString():v)+' '+unit+' ('+p+'%)',v};
  });
}

// ── CSelect 클래스 ────────────────────────────────────────────────
const SELS={};
class CSelect{
  constructor(id,opts,defV,cfg={}){
    this.id=id; this.opts=opts; this.cfg=cfg;
    this.cur=opts.find(o=>String(o.v)===String(defV))||opts[0];
    this.el=document.getElementById(id); SELS[id]=this; this._build();
    document.addEventListener('click',()=>this._close());
  }
  _build(){
    this.el.innerHTML='';
    const btn=document.createElement('div'); btn.className='csel-btn';
    btn.innerHTML='<span class="csel-txt">'+this._label(this.cur)+'</span><span class="csel-arr">▾</span>';
    btn.addEventListener('click',e=>{e.stopPropagation();this._toggle();});
    this.btn=btn;
    const panel=document.createElement('div'); panel.className='csel-panel';
    if(this.cfg.search){
      const si=document.createElement('input'); si.className='csel-search'; si.placeholder='기관명 검색...';
      si.addEventListener('input',e=>{e.stopPropagation();this._renderList(this.opts.filter(o=>o.l.includes(e.target.value)));});
      si.addEventListener('click',e=>e.stopPropagation());
      panel.appendChild(si);
    }
    const list=document.createElement('div'); list.className='csel-list';
    panel.appendChild(list); this.panel=panel; this.list=list;
    this._renderList(this.opts); this.el.appendChild(btn); this.el.appendChild(panel);
  }
  _label(o){
    if(!o.c) return o.l;
    return o.l+'<span class="csel-coef">'+o.c+'</span>';
  }
  _renderList(opts){
    this.list.innerHTML='';
    if(!opts.length){const d=document.createElement('div');d.className='csel-empty';d.textContent='검색 결과 없음';this.list.appendChild(d);return;}
    opts.forEach(o=>{
      const d=document.createElement('div');
      d.className='csel-item'+(String(o.v)===String(this.cur.v)?' on':'');
      d.innerHTML=o.l+(o.c?'<span class="csel-coef">'+o.c+'</span>':'');
      d.addEventListener('click',e=>{e.stopPropagation();this._select(o);});
      this.list.appendChild(d);
    });
  }
  _select(o){
    this.cur=o; this.btn.querySelector('.csel-txt').innerHTML=this._label(o);
    this._renderList(this.opts); this._close();
    if(this.cfg.onChange) this.cfg.onChange(o.v);
  }
  _toggle(){if(this.panel.classList.contains('show')){this._close();return;}Object.values(SELS).forEach(s=>s._close());this.panel.classList.add('show');this.btn.classList.add('open');}
  _close(){this.panel.classList.remove('show');this.btn.classList.remove('open');}
  getValue(){return this.cur.v;}
  setOpts(opts,defV){this.opts=opts;this.cur=opts.find(o=>String(o.v)===String(defV))||opts[0];this.btn.querySelector('.csel-txt').innerHTML=this._label(this.cur);this._renderList(opts);}
}

// ── 상태 & 캐스케이드 ─────────────────────────────────────────────
let cType='예산 배분', cMode='budget';
function getUnit(m){return m==='budget'?'억 원':m==='person'?'명':'점';}
function getTotalOpts(m){return m==='budget'?BUDGET_OPTS:m==='person'?PERSON_OPTS:POINT_OPTS;}

function updateShareOpts(){
  const total=SELS['trSel'].getValue(), unit=getUnit(cMode);
  const opts=shareOpts(total,unit);
  const mid=opts[Math.floor(opts.length/2)].v, lo=opts[Math.max(0,Math.floor(opts.length/2)-1)].v;
  SELS['ax0Sel'].setOpts(opts,mid); SELS['bx0Sel'].setOpts(opts,mid);
  SELS['aMSel'].setOpts(opts,lo);  SELS['bMSel'].setOpts(opts,lo);
  const lbl='현재 '+unit+' 배분량';
  document.getElementById('ax0L').childNodes[0].textContent=lbl+' ';
  document.getElementById('bx0L').childNodes[0].textContent=lbl+' ';
}

function pickType(el){
  document.querySelectorAll('.tc').forEach(c=>c.classList.remove('on')); el.classList.add('on');
  cType=el.dataset.type; cMode=el.dataset.mode;
  const topts=getTotalOpts(cMode);
  SELS['trSel'].setOpts(topts,topts[Math.min(5,topts.length-1)].v);
  const titles={budget:'두 기관이 나눌 총 예산은 얼마인가요?',person:'두 기관이 나눌 총 인원 수는 얼마인가요?',point:'두 기관이 나눌 총 점수는 얼마인가요?'};
  const descs={budget:'나눌 총 예산 금액을 선택하세요',person:'총 인원 수를 선택하세요',point:'총 100점 기준으로 선택하세요'};
  document.getElementById('trTitle').textContent=titles[cMode];
  document.getElementById('trDesc').textContent=descs[cMode];
  updateShareOpts();
}

// ── 초기화 ────────────────────────────────────────────────────────
function init(){
  new CSelect('trSel',BUDGET_OPTS,100,{onChange:updateShareOpts});
  const sO=shareOpts(100,'억 원'), mid=sO[Math.floor(sO.length/2)].v, lo=sO[Math.max(0,Math.floor(sO.length/2)-1)].v;
  new CSelect('ax0Sel',sO,mid); new CSelect('aMSel',sO,lo);
  new CSelect('bx0Sel',sO,mid); new CSelect('bMSel',sO,lo);
  new CSelect('anSel',AGENCIES,'기획재정부',{search:true});
  new CSelect('bnSel',AGENCIES,'과학기술정보통신부',{search:true});
  new CSelect('awSel',POWER_OPTS,1.0); new CSelect('adSel',DAMAGE_OPTS,10);
  new CSelect('bwSel',POWER_OPTS,1.0); new CSelect('bdSel',DAMAGE_OPTS,10);
  new CSelect('hostSel',HOST_OPTS,0.2);
  new CSelect('aLambdaSel',LOSS_OPTS,2.2); new CSelect('aAlphaSel',ALPHA_OPTS,1.1);
  new CSelect('aGammaSel',GAMMA_OPTS,0.3); new CSelect('aDeltaSel',DELTA_OPTS,0.5);
  new CSelect('aRhoSel',RHO_OPTS,0.3);    new CSelect('aBetaSel',BETA_OPTS,0.5);
  new CSelect('bLambdaSel',LOSS_OPTS,2.2); new CSelect('bAlphaSel',ALPHA_OPTS,1.1);
  new CSelect('bGammaSel',GAMMA_OPTS,0.3); new CSelect('bDeltaSel',DELTA_OPTS,0.6);
  new CSelect('bRhoSel',RHO_OPTS,0.2);    new CSelect('bBetaSel',BETA_OPTS,0.6);
}
document.addEventListener('DOMContentLoaded',init);

// ── 실행 ─────────────────────────────────────────────────────────
function gv(id){return parseFloat(SELS[id].getValue());}
function gs(id){return SELS[id].getValue();}
function interp(s){return s>5?'✅ 적극 수용 가능':s>0?'🟡 조건부 수용 가능':'🔴 수용 어려움';}

async function run(){
  const btn=document.getElementById('runBtn'); btn.disabled=true; btn.textContent='🔄 분석 중...';
  const p={conflict_type:cType,total_resource:gv('trSel'),hostility_AB:gv('hostSel'),
    actor_A:{name:gs('anSel'),weight_w:gv('awSel'),disagreement_d:gv('adSel'),historical_x0:gv('ax0Sel'),min_reputation_M:gv('aMSel'),bias_lambda:gv('aLambdaSel'),bias_alpha:gv('aAlphaSel'),bias_gamma:gv('aGammaSel'),bias_delta:gv('aDeltaSel'),bias_rho:gv('aRhoSel'),bias_beta:gv('aBetaSel')},
    actor_B:{name:gs('bnSel'),weight_w:gv('bwSel'),disagreement_d:gv('bdSel'),historical_x0:gv('bx0Sel'),min_reputation_M:gv('bMSel'),bias_lambda:gv('bLambdaSel'),bias_alpha:gv('bAlphaSel'),bias_gamma:gv('bGammaSel'),bias_delta:gv('bDeltaSel'),bias_rho:gv('bRhoSel'),bias_beta:gv('bBetaSel')}};
  try{
    const r=await fetch('/api/v1/coordination/solve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
    show(await r.json(),p);
  }catch(e){alert('서버 오류: '+e.message);}
  finally{btn.disabled=false; btn.textContent='🔍 합의안 찾기';}
}

// ── 결과 표시 ────────────────────────────────────────────────────
function show(d,p){
  const el=document.getElementById('results'); el.style.display='block'; el.scrollIntoView({behavior:'smooth',block:'start'});
  const sc={success:{cls:'rs-ok',msg:'✅  양측이 받아들일 수 있는 합의안을 찾았습니다.'},infeasible:{cls:'rs-no',msg:'❌  최솟값 합이 총 자원을 초과합니다. 마지노선을 낮추거나 총 자원을 늘려보세요.'},no_equilibrium:{cls:'rs-wn',msg:'⚠️  이 자원만으로는 합의점을 찾기 어렵습니다. 다른 조건을 함께 묶어 협상하는 것을 권장합니다.'}};
  const s=sc[d.status]||sc.success;
  document.getElementById('statusMsg').innerHTML='<div class="rst '+s.cls+'">'+s.msg+'</div>';
  const tot=p.total_resource, aS=d.optimized_allocation.actor_A_share, bS=d.optimized_allocation.actor_B_share;
  const aN=p.actor_A.name, bN=p.actor_B.name, u=getUnit(cMode);
  const aP=(aS/tot*100).toFixed(1), bP=(bS/tot*100).toFixed(1);
  document.getElementById('aa').style.width=aP+'%'; document.getElementById('aa').textContent=aP>12?aN:'';
  document.getElementById('ab').style.width=bP+'%'; document.getElementById('ab').textContent=bP>12?bN:'';
  document.getElementById('aon').textContent=aN; document.getElementById('anum').textContent=aS+' '+u; document.getElementById('apct').textContent='전체의 '+aP+'%';
  document.getElementById('bon').textContent=bN; document.getElementById('bnum').textContent=bS+' '+u; document.getElementById('bpct').textContent='전체의 '+bP+'%';
  const uA=d.psychological_satisfaction.actor_A_utility, uB=d.psychological_satisfaction.actor_B_utility;
  document.getElementById('uaLbl').textContent=aN+' 수용 가능성'; document.getElementById('uaScore').textContent=uA; document.getElementById('uaInterp').textContent=interp(uA);
  document.getElementById('ubLbl').textContent=bN+' 수용 가능성'; document.getElementById('ubScore').textContent=uB; document.getElementById('ubInterp').textContent=interp(uB);
  document.getElementById('nc').textContent=d.coordination_note;
  buildCalcPanel(d,p,aN,bN,u,aS,bS);
}

// ── 산출 근거 패널 ───────────────────────────────────────────────
function buildCalcPanel(d,p,aN,bN,u,aS,bS){
  const A=p.actor_A, B=p.actor_B, H=p.hostility_AB, tot=p.total_resource;
  const uA=d.psychological_satisfaction.actor_A_utility;
  const uB=d.psychological_satisfaction.actor_B_utility;
  const aAnchor=(A.anchor_demand!=null?A.anchor_demand:+(A.historical_x0*1.5).toFixed(1));
  const bAnchor=(B.anchor_demand!=null?B.anchor_demand:+(B.historical_x0*1.5).toFixed(1));

  document.getElementById('calcBody').innerHTML=`
  <div class="calc-sec">
    <div class="calc-sec-title">📊 적용된 심리 편향 파라미터 (7종)</div>
    <table class="param-table">
      <thead><tr><th>#</th><th>편향</th><th>기호</th><th>의미</th><th style="color:#2563eb">${aN}</th><th style="color:#dc2626">${bN}</th></tr></thead>
      <tbody>
        <tr><td>①</td><td>자기고양</td><td class="sym">α</td><td>기본 효용 = x×(2−α)</td><td class="val-a">${A.bias_alpha}</td><td class="val-b">${B.bias_alpha}</td></tr>
        <tr><td>②</td><td>손실회피</td><td class="sym">λ</td><td>λ×max(0, x₀−x)</td><td class="val-a">${A.bias_lambda}</td><td class="val-b">${B.bias_lambda}</td></tr>
        <tr><td>③</td><td>제로섬 사고</td><td class="sym">γ</td><td>γ×x<sub>상대</sub></td><td class="val-a">${A.bias_gamma}</td><td class="val-b">${B.bias_gamma}</td></tr>
        <tr><td>④</td><td>앵커링</td><td class="sym">δ</td><td>δ×max(0, a−x)</td><td class="val-a">${A.bias_delta}</td><td class="val-b">${B.bias_delta}</td></tr>
        <tr><td>⑤</td><td>후회 회피</td><td class="sym">ρ</td><td>ρ×max(0, x−x₀)</td><td class="val-a">${A.bias_rho}</td><td class="val-b">${B.bias_rho}</td></tr>
        <tr><td>⑥</td><td>시기심</td><td class="sym">β</td><td>β×(1+H)×max(0, x<sub>상대</sub>−x)</td><td class="val-a">${A.bias_beta}</td><td class="val-b">${B.bias_beta}</td></tr>
        <tr><td>⑦</td><td>반응적 가치하락</td><td class="sym">H</td><td>대립도 (시기심 증폭)</td><td class="val-a" colspan="2" style="text-align:center">${H} (공유)</td></tr>
      </tbody>
    </table>
  </div>

  <div class="calc-sec">
    <div class="calc-sec-title">📐 심리적 수정 효용 함수 V<sub>i</sub>(x<sub>i</sub>, x<sub>j</sub>)</div>
    <div class="formula-box">
      <div class="f-main">V<sub>i</sub> = [기본효용] − [손실페널티] − [제로섬페널티] − [앵커링페널티] − [후회페널티] − [시기심페널티] − [체면페널티]</div>
      <div class="f-row"><span class="f-eq">= x<sub>i</sub> × (2 − α<sub>i</sub>)</span><span class="f-note">① 자기고양 보정 — 자기 기여를 과대평가할수록 실질 효용 감소</span></div>
      <div class="f-row"><span class="f-eq">− λ<sub>i</sub> × max(0, x₀ − x<sub>i</sub>)</span><span class="f-note">② 손실회피·부존효과 — 준거점 이하 하락 시 손실 민감도 반영</span></div>
      <div class="f-row"><span class="f-eq">− γ<sub>i</sub> × x<sub>j</sub></span><span class="f-note">③ 제로섬 사고 — 상대방 몫 자체를 내 손실로 인식</span></div>
      <div class="f-row"><span class="f-eq">− δ<sub>i</sub> × max(0, a<sub>i</sub> − x<sub>i</sub>)</span><span class="f-note">④ 앵커링 — 첫 요구안(a) 아래로 떨어질 때의 심리적 저항</span></div>
      <div class="f-row"><span class="f-eq">− ρ<sub>i</sub> × max(0, x<sub>i</sub> − x₀)</span><span class="f-note">⑤ 후회 회피 — 준거점 이상 이득에서 오는 승자의 저주</span></div>
      <div class="f-row"><span class="f-eq">− β<sub>i</sub> × (1+H) × max(0, x<sub>j</sub> − x<sub>i</sub>)</span><span class="f-note">⑥⑦ 시기심 + 반응적 가치하락 — 상대 우위 시 불쾌감, H로 증폭</span></div>
      <div class="f-row"><span class="f-eq">− [∞ if x<sub>i</sub> &lt; M<sub>i</sub>]</span><span class="f-note">⑦ 체면 마지노선 — 이 수치 이하는 사실상 거부 불능</span></div>
    </div>
  </div>

  <div class="calc-sec">
    <div class="calc-sec-title">⚖️ 내시 바게닝 목적함수 (최적화 문제)</div>
    <div class="formula-box">
      <div class="f-main">max &nbsp; w<sub>A</sub> × ln(V<sub>A</sub> − d<sub>A</sub>) + w<sub>B</sub> × ln(V<sub>B</sub> − d<sub>B</sub>)</div>
      <div class="f-constraint">s.t. &nbsp; x<sub>A</sub> + x<sub>B</sub> = ${tot} &nbsp;&nbsp;(총 자원 제약)<br>
      x<sub>A</sub> ∈ [${A.min_reputation_M}, ${tot - B.min_reputation_M}] &nbsp;&nbsp;(양측 체면 마지노선 보장)<br>
      V<sub>i</sub> − d<sub>i</sub> &gt; 0 &nbsp;&nbsp;(결렬점보다 나아야 합의 성립)</div>
      <div style="margin-top:10px;font-size:.8rem;color:#6b7280;font-family:-apple-system,sans-serif">
        x<sub>A</sub>에 대한 단변수 최적화로 환원 (x<sub>B</sub> = ${tot} − x<sub>A</sub>) → SciPy minimize_scalar (bounded method) 사용
      </div>
    </div>
  </div>

  <div class="calc-sec">
    <div class="calc-sec-title">🔢 실제 적용된 수치 및 최적화 결과</div>
    <table class="param-table">
      <thead><tr><th>항목</th><th>기호</th><th style="color:#2563eb">${aN}</th><th style="color:#dc2626">${bN}</th></tr></thead>
      <tbody>
        <tr><td>협상 권한 가중치</td><td class="sym">w</td><td class="val-a">${A.weight_w}</td><td class="val-b">${B.weight_w}</td></tr>
        <tr><td>결렬점 (협상 실패 시 피해)</td><td class="sym">d</td><td class="val-a">${A.disagreement_d}</td><td class="val-b">${B.disagreement_d}</td></tr>
        <tr><td>준거점 (현재 배분량)</td><td class="sym">x₀</td><td class="val-a">${A.historical_x0} ${u}</td><td class="val-b">${B.historical_x0} ${u}</td></tr>
        <tr><td>앵커 요구안</td><td class="sym">a</td><td class="val-a">${aAnchor} ${u}${A.anchor_demand==null?' (자동)':''}</td><td class="val-b">${bAnchor} ${u}${B.anchor_demand==null?' (자동)':''}</td></tr>
        <tr><td>체면 마지노선</td><td class="sym">M</td><td class="val-a">${A.min_reputation_M} ${u}</td><td class="val-b">${B.min_reputation_M} ${u}</td></tr>
        <tr class="result-row"><td><strong>최적 배분 (x*)</strong></td><td class="sym">x*</td><td class="val-a"><strong>${aS} ${u}</strong></td><td class="val-b"><strong>${bS} ${u}</strong></td></tr>
        <tr class="result-row"><td><strong>심리적 효용 (V)</strong></td><td class="sym">V</td><td class="val-a"><strong>${uA}</strong></td><td class="val-b"><strong>${uB}</strong></td></tr>
        <tr class="result-row"><td><strong>결렬점 초과 잉여 (V−d)</strong></td><td class="sym">V−d</td><td class="val-a"><strong>${(uA-A.disagreement_d).toFixed(2)}</strong></td><td class="val-b"><strong>${(uB-B.disagreement_d).toFixed(2)}</strong></td></tr>
      </tbody>
    </table>
  </div>`;
}
</script>
</body>
</html>"""
