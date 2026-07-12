"use client";

// 마케팅연구소 시스템 구조 가이드 (초보자용)
// 스타일은 .guide-root 로 스코프하여 다른 화면과 충돌하지 않게 함. 앱과 동일한 라이트 테마.

const CSS = `
.guide-root{
  --bg:#eef1f6;--surface:#fff;--surface-2:#f6f8fb;--ink:#0f172a;--text:#33415a;--muted:#6b7a90;--line:#dce3ec;
  --cloud:#2563eb;--cloud-soft:#e8f0ff;--cloud-line:#bcd3ff;--local:#e0680c;--local-soft:#fdeede;--local-line:#f8cfa0;
  --screen:#7c3aed;--screen-soft:#f0e9ff;--ok:#15803d;--ok-soft:#e4f4ea;--warn:#b91c1c;--warn-soft:#fbe9e9;
  --shadow:0 1px 2px rgba(15,23,42,.04),0 8px 24px rgba(15,23,42,.06);--radius:14px;
  --mono:"Cascadia Code","D2Coding",ui-monospace,Consolas,monospace;
  color:var(--text);line-height:1.65;
}
.guide-root *{box-sizing:border-box;}
.guide-root .wrap{max-width:960px;margin:0 auto;}
.guide-root h1,.guide-root h2,.guide-root h3,.guide-root h4{color:var(--ink);text-wrap:balance;line-height:1.25;margin:0;}
.guide-root p{margin:0;}
.guide-root strong,.guide-root b{color:var(--ink);font-weight:700;}
.guide-root code{font-family:var(--mono);font-size:.86em;background:var(--surface-2);border:1px solid var(--line);border-radius:6px;padding:.08em .4em;color:var(--ink);}
.guide-root .eyebrow{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700;}
.guide-root header h1{font-size:clamp(1.7rem,5vw,2.4rem);font-weight:800;letter-spacing:-.02em;margin:.5rem 0 .7rem;}
.guide-root .lead{font-size:clamp(1rem,2.4vw,1.15rem);color:var(--text);max-width:48ch;}
.guide-root .analogy{margin-top:1.3rem;display:flex;gap:.8rem;align-items:flex-start;background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--cloud);border-radius:12px;padding:1rem 1.2rem;box-shadow:var(--shadow);}
.guide-root .analogy .em{font-size:1.4rem;line-height:1;}
.guide-root .analogy b.c{color:var(--cloud);} .guide-root .analogy b.l{color:var(--local);}
.guide-root section{margin-top:clamp(2.2rem,6vw,3.4rem);}
.guide-root .sec-head{display:flex;align-items:baseline;gap:.7rem;margin-bottom:1.2rem;flex-wrap:wrap;}
.guide-root .sec-head .n{font-family:var(--mono);font-size:.82rem;color:var(--muted);font-weight:600;border:1px solid var(--line);border-radius:999px;padding:.1rem .6rem;}
.guide-root .sec-head h2{font-size:clamp(1.3rem,3.4vw,1.6rem);font-weight:800;letter-spacing:-.01em;}
.guide-root .sec-sub{color:var(--muted);font-size:.95rem;margin-top:-.5rem;margin-bottom:1.2rem;}
.guide-root .zone{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:1.1rem 1.2rem;box-shadow:var(--shadow);}
.guide-root .zone .ztag{display:inline-flex;align-items:center;gap:.45rem;font-size:.74rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:.22rem .6rem;border-radius:999px;margin-bottom:.7rem;}
.guide-root .z-screen .ztag{background:var(--screen-soft);color:var(--screen);}
.guide-root .z-cloud{border-color:var(--cloud-line);} .guide-root .z-cloud .ztag{background:var(--cloud-soft);color:var(--cloud);}
.guide-root .z-local{border-color:var(--local-line);} .guide-root .z-local .ztag{background:var(--local-soft);color:var(--local);}
.guide-root .zone h3{font-size:1.05rem;font-weight:800;margin-bottom:.3rem;}
.guide-root .zone p{font-size:.92rem;color:var(--text);}
.guide-root .zone .meta{font-family:var(--mono);font-size:.78rem;color:var(--muted);margin-top:.5rem;word-break:break-all;}
.guide-root .cloud-inner{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-top:.8rem;}
.guide-root .chip{background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:.6rem .7rem;}
.guide-root .chip b{font-size:.9rem;} .guide-root .chip span{display:block;font-size:.8rem;color:var(--muted);margin-top:.15rem;}
.guide-root .connect{display:flex;flex-direction:column;align-items:center;gap:.25rem;padding:.55rem 0;color:var(--muted);}
.guide-root .connect .arrow{font-size:1.1rem;line-height:1;}
.guide-root .connect .lbl{font-size:.78rem;background:var(--surface);border:1px dashed var(--line);border-radius:999px;padding:.12rem .7rem;text-align:center;}
.guide-root .connect.acct .lbl{border-style:solid;border-color:var(--local-line);color:var(--local);background:var(--local-soft);font-weight:700;}
.guide-root .cards{display:grid;grid-template-columns:1fr;gap:1rem;}
.guide-root .card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:1.2rem 1.3rem;box-shadow:var(--shadow);border-top:3px solid var(--line);}
.guide-root .card.c-screen{border-top-color:var(--screen);}
.guide-root .card.c-cloud{border-top-color:var(--cloud);}
.guide-root .card.c-local{border-top-color:var(--local);}
.guide-root .card .role{font-size:.76rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
.guide-root .card h3{font-size:1.12rem;font-weight:800;margin:.35rem 0 .1rem;}
.guide-root .card .where{font-family:var(--mono);font-size:.8rem;color:var(--muted);margin-bottom:.6rem;}
.guide-root .card ul{margin:.5rem 0 0;padding-left:1.1rem;}
.guide-root .card li{font-size:.92rem;margin:.28rem 0;}
.guide-root .card li::marker{color:var(--muted);}
.guide-root .callout{background:var(--local-soft);border:1px solid var(--local-line);border-radius:var(--radius);padding:1.2rem 1.3rem;display:flex;gap:1rem;align-items:flex-start;}
.guide-root .callout .em{font-size:1.6rem;line-height:1;}
.guide-root .callout h3{font-size:1.05rem;color:var(--local);margin-bottom:.3rem;}
.guide-root .callout p{font-size:.94rem;}
.guide-root .flow{display:grid;grid-template-columns:1fr;counter-reset:step;}
.guide-root .step{display:grid;grid-template-columns:auto 1fr;gap:1rem;padding:.9rem 0;border-bottom:1px solid var(--line);}
.guide-root .step:last-child{border-bottom:0;}
.guide-root .step .num{counter-increment:step;width:2rem;height:2rem;flex:0 0 auto;border-radius:999px;display:grid;place-items:center;font-family:var(--mono);font-weight:700;font-size:.9rem;background:var(--surface-2);border:1px solid var(--line);color:var(--ink);}
.guide-root .step .num::before{content:counter(step);}
.guide-root .step.s-cloud .num{background:var(--cloud-soft);border-color:var(--cloud-line);color:var(--cloud);}
.guide-root .step.s-local .num{background:var(--local-soft);border-color:var(--local-line);color:var(--local);}
.guide-root .step .body h4{font-size:.98rem;color:var(--ink);font-weight:700;margin:.15rem 0 .2rem;}
.guide-root .step .body p{font-size:.9rem;color:var(--text);}
.guide-root .step .who{font-size:.72rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;}
.guide-root .who.cloud{color:var(--cloud);} .guide-root .who.local{color:var(--local);} .guide-root .who.screen{color:var(--screen);}
.guide-root .tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);}
.guide-root table{width:100%;border-collapse:collapse;font-size:.92rem;min-width:520px;background:var(--surface);}
.guide-root th,.guide-root td{text-align:left;padding:.8rem 1rem;border-bottom:1px solid var(--line);vertical-align:top;color:var(--text);}
.guide-root thead th{background:var(--surface-2);color:var(--ink);font-size:.8rem;letter-spacing:.04em;text-transform:uppercase;}
.guide-root tbody tr:last-child td{border-bottom:0;}
.guide-root td b.c{color:var(--cloud);} .guide-root td b.l{color:var(--local);}
.guide-root .status{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;}
.guide-root .status .row{display:grid;grid-template-columns:1fr auto;gap:1rem;align-items:center;padding:.85rem 1.2rem;border-bottom:1px solid var(--line);}
.guide-root .status .row:last-child{border-bottom:0;}
.guide-root .status .k{font-size:.92rem;color:var(--ink);} .guide-root .status .k span{display:block;font-family:var(--mono);font-size:.78rem;color:var(--muted);margin-top:.1rem;word-break:break-all;}
.guide-root .pill{font-size:.78rem;font-weight:700;padding:.2rem .6rem;border-radius:999px;white-space:nowrap;}
.guide-root .pill.ok{background:var(--ok-soft);color:var(--ok);}
.guide-root .pill.warn{background:var(--warn-soft);color:var(--warn);}
.guide-root .check{display:grid;grid-template-columns:1fr;gap:.8rem;}
.guide-root .cl{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:1rem 1.15rem;box-shadow:var(--shadow);}
.guide-root .cl h4{font-size:.98rem;color:var(--ink);display:flex;align-items:center;gap:.5rem;margin-bottom:.35rem;}
.guide-root .cl .dot{width:.7rem;height:.7rem;border-radius:50%;flex:0 0 auto;}
.guide-root .cl.always .dot{background:var(--ok);} .guide-root .cl.needagent .dot{background:var(--local);}
.guide-root .cl p{font-size:.9rem;} .guide-root .cl .need{font-size:.82rem;color:var(--muted);margin-top:.4rem;}
.guide-root .cl .need b{color:var(--local);}
.guide-root .g-footer{margin-top:2.6rem;padding-top:1.3rem;border-top:1px solid var(--line);color:var(--muted);font-size:.84rem;}
@media (min-width:720px){
  .guide-root .cards{grid-template-columns:repeat(3,1fr);}
  .guide-root .check{grid-template-columns:1fr 1fr;}
}
`;

const BODY = `
<div class="wrap">
  <header>
    <div class="eyebrow">마케팅 연구소 · 시스템 구조 가이드</div>
    <h1>웹과 내 컴퓨터가 어떻게 나눠서 일하나</h1>
    <p class="lead">프로그램은 크게 <strong>세 조각</strong>으로 되어 있습니다. 대부분은 인터넷(클라우드)에서 알아서 돌고, <strong>네이버 관련 작업만</strong> 내 컴퓨터가 대신 합니다.</p>
    <div class="analogy">
      <div class="em">🏢</div>
      <div><p><b class="c">클라우드(웹)</b>는 <strong>본사 사무실</strong> — 24시간 켜져 있고 화면·AI·데이터를 담당합니다.<br>
      <b class="l">내 PC 에이전트</b>는 <strong>현장 직원</strong> — 네이버에 "진짜 사람"으로 접근해야 하는 일을 집에서 대신 처리합니다.</p></div>
    </div>
  </header>

  <section>
    <div class="sec-head"><span class="n">한눈에</span><h2>전체 그림</h2></div>
    <div class="zone z-screen">
      <span class="ztag">① 보이는 화면</span><h3>웹 브라우저</h3>
      <p>내가 접속해서 버튼을 누르는 곳. 크롬·엣지 어디서나.</p>
      <div class="meta">marketlabs.kr</div>
    </div>
    <div class="connect"><span class="lbl">인터넷 접속</span><span class="arrow">↕</span></div>
    <div class="zone z-cloud">
      <span class="ztag">② 클라우드 (항상 켜짐)</span><h3>본사 = 웹 서버 + 데이터베이스</h3>
      <p>화면을 그려주고, AI로 원고를 만들고, 정부·공공 글감을 모으고, 모든 데이터를 보관합니다.</p>
      <div class="cloud-inner">
        <div class="chip"><b>프론트(화면)</b><span>Vercel · Next.js</span></div>
        <div class="chip"><b>백엔드(두뇌)</b><span>Railway · FastAPI</span></div>
        <div class="chip"><b>데이터베이스</b><span>Railway · Postgres</span></div>
        <div class="chip"><b>AI 엔진</b><span>Claude · Gemini</span></div>
      </div>
    </div>
    <div class="connect acct"><span class="lbl">🔑 같은 계정으로 연결 · 3초마다 "내 일 있어?"</span><span class="arrow">↕</span></div>
    <div class="zone z-local">
      <span class="ztag">③ 내 컴퓨터 (켜져 있어야 함)</span><h3>현장 직원 = 에이전트</h3>
      <p>네이버 플레이스 리뷰 수집, 블로그·카페 발행, 순위 확인처럼 <strong>네이버에 로그인/접속</strong>하는 일을 내 집 인터넷(IP)으로 대신 실행합니다.</p>
      <div class="meta">agent.py · 내 PC에서 실행</div>
    </div>
  </section>

  <section>
    <div class="sec-head"><span class="n">구성</span><h2>세 조각이 하는 일</h2></div>
    <div class="cards">
      <div class="card c-screen">
        <div class="role">① 화면</div><h3>웹 브라우저</h3><div class="where">marketlabs.kr</div>
        <ul><li>로그인, 메뉴, 버튼 클릭</li><li>결과 보기·검토</li><li>설치 필요 없음 — 인터넷만</li></ul>
      </div>
      <div class="card c-cloud">
        <div class="role">② 클라우드 (본사)</div><h3>웹 서버 + DB</h3><div class="where">Railway + Vercel</div>
        <ul><li>AI 원고·이미지 생성</li><li>정부·공공 <strong>글감 수집</strong></li><li>모든 데이터 저장</li><li>일을 내 PC에 나눠주기</li><li><strong>24시간 자동</strong></li></ul>
      </div>
      <div class="card c-local">
        <div class="role">③ 내 PC (현장)</div><h3>에이전트</h3><div class="where">agent.py</div>
        <ul><li><strong>맛집 리뷰</strong> 수집</li><li><strong>블로그·카페 발행</strong></li><li>순위 확인</li><li>내 계정·내 집 IP로 실행</li><li><strong>켜져 있어야 작동</strong></li></ul>
      </div>
    </div>
  </section>

  <section>
    <div class="callout">
      <div class="em">🤔</div>
      <div><h3>왜 네이버 작업만 내 PC가 하나요?</h3>
      <p>네이버는 <strong>클라우드(데이터센터) IP를 수상하게 여겨 차단</strong>합니다. 그래서 본사(클라우드)가 직접 네이버를 긁으면 막혀버립니다. 대신 <strong>진짜 가정집 인터넷인 내 PC</strong>가 접속하면 정상 사용자로 인식됩니다. 그래서 네이버 관련 일만 "현장 직원(에이전트)"에게 맡기는 구조입니다.</p></div>
    </div>
  </section>

  <section>
    <div class="sec-head"><span class="n">예시</span><h2>"맛집 소재 수집"을 누르면</h2></div>
    <p class="sec-sub">버튼 하나가 어떻게 처리되는지 — 어디서 무엇이 일하는지 따라가 보세요.</p>
    <div class="flow">
      <div class="step s-cloud"><div class="num"></div><div class="body"><span class="who screen">화면</span><h4>웹에서 [맛집 소재 수집] 클릭</h4><p>플레이스 주소를 넣고 버튼을 누릅니다.</p></div></div>
      <div class="step s-cloud"><div class="num"></div><div class="body"><span class="who cloud">클라우드</span><h4>"이건 네이버 작업 → 내 PC 담당" 판단, 대기줄에 등록</h4><p>본사가 직접 못 하는 일이라 <strong>내 계정 꼬리표</strong>를 달아 작업을 쌓아둡니다.</p></div></div>
      <div class="step s-local"><div class="num"></div><div class="body"><span class="who local">내 PC</span><h4>에이전트가 "내 일 있어?" 물어보고 받아감</h4><p>내 PC 에이전트는 3초마다 확인합니다. <strong>내 계정 작업</strong>이면 가져옵니다.</p></div></div>
      <div class="step s-local"><div class="num"></div><div class="body"><span class="who local">내 PC</span><h4>집 인터넷으로 네이버 리뷰 수집 → 결과 반환</h4><p>진짜 사용자처럼 접속해 리뷰를 모아 클라우드로 돌려보냅니다.</p></div></div>
      <div class="step s-cloud"><div class="num"></div><div class="body"><span class="who cloud">클라우드 → 화면</span><h4>웹 화면에 글감이 채워짐</h4><p>이후 AI 원고 생성 → 검토 → 발행으로 이어집니다.</p></div></div>
    </div>
    <div class="callout" style="margin-top:1.4rem;background:var(--warn-soft);border-color:var(--warn);">
      <div class="em">⚠️</div>
      <div><h3 style="color:var(--warn)">그래서 에이전트가 꺼져 있으면</h3>
      <p>2번까지는 되지만 3번에서 아무도 일을 가져가지 않아 <strong>대기만 하다 실패</strong>합니다. 또 웹 로그인 계정과 에이전트 계정이 <strong>다르면</strong> 내 일을 못 가져갑니다(계정이 같아야 함).</p></div>
    </div>
  </section>

  <section>
    <div class="sec-head"><span class="n">비교</span><h2>웹 방식 vs 설치형</h2></div>
    <div class="tablewrap">
      <table>
        <thead><tr><th>구분</th><th>웹 방식 (지금)</th><th>설치형 (선택)</th></tr></thead>
        <tbody>
          <tr><td><b>화면·AI·데이터</b></td><td><b class="c">클라우드</b>에 있음<br>브라우저로 접속</td><td>전부 <b class="l">내 PC</b>에 설치<br>(무거움, 라이선스 코드)</td></tr>
          <tr><td><b>네이버 작업</b></td><td>내 PC <b class="l">에이전트만</b> 설치</td><td>설치본 안에 에이전트 포함</td></tr>
          <tr><td><b>설치 부담</b></td><td>가벼움 — 에이전트만</td><td>큼 — 프로그램 전체</td></tr>
          <tr><td><b>추천</b></td><td>대부분의 사용자 ✓</td><td>완전 오프라인/독립 운영 시</td></tr>
        </tbody>
      </table>
    </div>
    <p class="sec-sub" style="margin-top:1rem">👉 <strong>에이전트 전용 설치본</strong>은 "웹은 클라우드로 쓰고, 네이버 작업용 에이전트만 각자 PC에 자동 설치"하는 방식입니다.</p>
  </section>

  <section>
    <div class="sec-head"><span class="n">현재</span><h2>지금 시스템 상태</h2></div>
    <div class="status">
      <div class="row"><div class="k">웹 화면 (프론트)<span>Vercel → marketlabs.kr</span></div><span class="pill ok">클라우드 · 항상 켜짐</span></div>
      <div class="row"><div class="k">웹 서버 + DB (백엔드)<span>Railway · Postgres · EXECUTION_MODE=cloud</span></div><span class="pill ok">클라우드 · 항상 켜짐</span></div>
      <div class="row"><div class="k">내 PC 에이전트<span>웹과 같은 계정으로 내 컴퓨터에서 실행</span></div><span class="pill ok">실행 시 작동</span></div>
      <div class="row"><div class="k">계정 연결<span>웹 로그인 계정 = 에이전트 계정 이어야 함</span></div><span class="pill ok">매칭 필요</span></div>
      <div class="row"><div class="k">부팅 시 자동 실행<span>설치본으로 설치하면 자동 · 아니면 수동 실행</span></div><span class="pill warn">설치본이면 자동</span></div>
    </div>
  </section>

  <section>
    <div class="sec-head"><span class="n">핵심</span><h2>언제 무엇이 되나</h2></div>
    <p class="sec-sub">가장 헷갈리는 부분 — "무엇이 켜져 있어야 무엇이 되는지"입니다.</p>
    <div class="check">
      <div class="cl always"><h4><span class="dot"></span>인터넷만 있으면 항상 되는 것</h4>
        <p>웹 접속·로그인, AI 원고·이미지 생성, <strong>정부·공공 글감 수집</strong>, 저장된 데이터 보기.</p>
        <div class="need">클라우드가 24시간 처리 → 내 PC 꺼져 있어도 됨</div></div>
      <div class="cl needagent"><h4><span class="dot"></span>내 PC 에이전트가 켜져야 되는 것</h4>
        <p><strong>맛집 소재 수집</strong>, 블로그·카페 <strong>발행</strong>, 네이버 순위 확인.</p>
        <div class="need"><b>조건 1</b> 에이전트 실행 중 · <b>조건 2</b> 웹 로그인 계정 = 에이전트 계정</div></div>
    </div>
  </section>

  <div class="g-footer">마케팅 연구소(MBAM) 구조 가이드 · 클라우드=본사, 내 PC 에이전트=현장 직원.<br>네이버가 얽힌 일만 내 PC가, 나머지는 클라우드가 자동으로 처리합니다.</div>
</div>
`;

export default function GuidePage() {
  return (
    <main style={{ padding: "clamp(1rem, 4vw, 2.5rem)" }}>
      <div className="guide-root">
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
        <div dangerouslySetInnerHTML={{ __html: BODY }} />
      </div>
    </main>
  );
}
