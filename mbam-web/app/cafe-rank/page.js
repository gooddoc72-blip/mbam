"use client";
import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchWithAuth } from "../utils/api";

function CafeRankInner() {
  const searchParams = useSearchParams();
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);  // 순위 변동 그래프/분석 펼침 대상
  const type = searchParams.get("type") || "";  // "blog" | "cafe" | "" (전체)

  const load = async () => {
    try {
      const res = await fetchWithAuth("/api/cafe-rank/items");
      const data = res.ok ? await res.json() : {};
      setItems(data.items || []);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { load(); }, []);

  const urlType = (u) => ((u || "").includes("blog.naver.com") ? "blog" : (u || "").includes("cafe.naver.com") || (u || "").includes("/cafes/") ? "cafe" : "");
  const shownItems = type ? items.filter(it => urlType(it.target_url) === type) : items;
  const typeLabel = type === "blog" ? "블로그" : type === "cafe" ? "카페" : "블로그·카페";
  const tabLabel = type === "blog" ? "블로그탭" : type === "cafe" ? "카페탭" : "탭 순위";
  const urlPlaceholder = type === "blog" ? "https://blog.naver.com/..." : type === "cafe" ? "https://cafe.naver.com/..." : "https://blog.naver.com/... 또는 https://cafe.naver.com/...";

  const addItem = async () => {
    if (!keyword.trim() || !targetUrl.trim()) { alert("키워드와 카페 글 URL을 입력하세요."); return; }
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/cafe-rank/items", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, target_url: targetUrl, name }),
      });
      if (res.ok) { setKeyword(""); setTargetUrl(""); setName(""); load(); }
      else { const d = await res.json().catch(() => ({})); alert("추가 실패: " + (d.detail || res.status)); }
    } catch (e) { alert("오류: " + e.message); } finally { setLoading(false); }
  };

  const checkNow = async (id) => {
    try {
      const res = await fetchWithAuth(`/api/cafe-rank/items/${id}/check`, { method: "POST" });
      const d = await res.json().catch(() => ({}));
      alert(res.ok ? (d.message || "순위 수집을 시작했습니다. 에이전트 실행 후 '새로고침'으로 확인하세요.") : ("실패: " + (d.detail || res.status)));
    } catch (e) { alert("오류: " + e.message); }
  };

  const removeItem = async (id) => {
    if (!confirm("이 추적 대상을 삭제할까요?")) return;
    try { const res = await fetchWithAuth(`/api/cafe-rank/items/${id}`, { method: "DELETE" }); if (res.ok) load(); } catch (e) {}
  };

  const rankText = (v) => (v == null ? "미노출" : `${v}위`);

  // 검색 누락(저품질 의심) 판정: 최근 2회 이상 검사에서 통검·탭 모두 미노출이면 '누락'.
  //  - unchecked: 아직 수집 전 / warn: 이번 1회만 미노출(관망) / ok: 노출 / missing: 누락 의심
  const missingState = (it) => {
    const h = it.history || [];
    if (h.length === 0) return "unchecked";
    const latestMissing = it.latest_tongsearch_rank == null && it.latest_cafetab_rank == null;
    const recent = h.slice(-3);
    const allRecentMissing = recent.length >= 2 && recent.every(x => x.tongsearch_rank == null && x.cafetab_rank == null);
    if (latestMissing && allRecentMissing) return "missing";
    if (latestMissing) return "warn";
    return "ok";
  };
  const missingCount = shownItems.filter(it => missingState(it) === "missing").length;

  const th = { padding: "0.6rem 0.8rem", textAlign: "left", fontSize: "0.82rem", color: "#64748b", borderBottom: "1px solid #e2e8f0", whiteSpace: "nowrap" };
  const td = { padding: "0.6rem 0.8rem", fontSize: "0.88rem", borderBottom: "1px solid #f1f5f9", verticalAlign: "top" };

  return (
    <div style={{ padding: "2rem", boxSizing: "border-box" }}>
      <h1 style={{ fontSize: "1.6rem", color: "#1e293b", marginBottom: "0.4rem" }}>📈 {typeLabel} 글 순위</h1>
      <p style={{ color: "#64748b", margin: "0 0 1.2rem", fontSize: "0.9rem" }}>
        {typeLabel} 글 URL과 키워드를 등록하면, 로컬 에이전트(집 PC)가 매일(새벽) 네이버 검색을 확인해
        <b> 통합검색 순위</b>와 <b>{tabLabel} 순위</b>를 기록합니다. '지금 수집'으로 즉시 확인도 가능합니다(에이전트 실행 필요).
      </p>

      {/* 등록 폼 */}
      <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "10px", padding: "1.2rem", marginBottom: "1.5rem", display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: "1 1 160px" }}>
          <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "bold", color: "#334155", marginBottom: "0.3rem" }}>키워드</label>
          <input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="예: 전포동 맛집" style={{ width: "100%", padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box" }} />
        </div>
        <div style={{ flex: "2 1 300px" }}>
          <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "bold", color: "#334155", marginBottom: "0.3rem" }}>{typeLabel} 글 URL</label>
          <input value={targetUrl} onChange={e => setTargetUrl(e.target.value)} placeholder={urlPlaceholder} style={{ width: "100%", padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box" }} />
        </div>
        <div style={{ flex: "1 1 120px" }}>
          <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "bold", color: "#334155", marginBottom: "0.3rem" }}>별칭(선택)</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="메모" style={{ width: "100%", padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box" }} />
        </div>
        <button onClick={addItem} disabled={loading} style={{ padding: "0.65rem 1.2rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: loading ? "wait" : "pointer", whiteSpace: "nowrap", flexShrink: 0 }}>＋ 추적 추가</button>
      </div>

      {missingCount > 0 && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", padding: "0.9rem 1.1rem", marginBottom: "1rem", color: "#991b1b", fontSize: "0.9rem", lineHeight: 1.6 }}>
          🔴 <b>검색 누락(저품질 의심) {missingCount}건</b> — 여러 번 확인해도 통합검색·{tabLabel}에 안 나오는 글입니다. 아래 <b>🔴 누락</b> 표시된 글을 확인 후 <b>직접 삭제</b>하세요(‘열어서 삭제’ 버튼으로 이동).
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem", flexWrap: "wrap", gap: "0.6rem" }}>
        <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: 0, whiteSpace: "nowrap" }}>추적 목록 ({shownItems.length})</h2>
        <button onClick={load} style={{ padding: "0.45rem 0.9rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem", whiteSpace: "nowrap" }}>🔄 새로고침</button>
      </div>

      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "10px", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "760px" }}>
          <thead>
            <tr>
              <th style={th}>노출 키워드 / 별칭</th>
              <th style={th}>{typeLabel} 글 URL</th>
              <th style={th}>통합검색</th>
              <th style={th}>{tabLabel}</th>
              <th style={th}>상태</th>
              <th style={th}>최근 수집</th>
              <th style={th}>최근 추이(통검)</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {shownItems.length === 0 ? (
              <tr><td style={td} colSpan={8}><span style={{ color: "#94a3b8" }}>아직 추적 중인 {typeLabel} 글이 없습니다. 위에서 추가하세요.</span></td></tr>
            ) : shownItems.map(it => {
              const st = missingState(it);
              const unchecked = st === "unchecked";
              const stop = (e) => e.stopPropagation();
              const open = expandedId === it.id;
              const toggle = () => setExpandedId(open ? null : it.id);
              return (
              <React.Fragment key={it.id}>
              <tr onClick={toggle} title="클릭하면 순위 변동 그래프와 매일 순위 분석이 아래로 펼쳐집니다" style={{ cursor: "pointer", background: open ? "#f8fafc" : "transparent" }}>
                <td style={td}><span style={{ color: "#94a3b8", marginRight: "0.35rem", fontSize: "0.75rem", display: "inline-block", transform: open ? "rotate(90deg)" : "none", transition: "transform .15s" }}>▶</span><b style={{ color: "#2563eb" }}>{it.keyword}</b>{it.name ? <div style={{ color: "#64748b", fontSize: "0.8rem", marginLeft: "1.1rem" }}>{it.name}</div> : null}</td>
                <td style={{ ...td, maxWidth: "260px" }}><a href={it.target_url} target="_blank" rel="noreferrer" onClick={stop} style={{ color: "#2563eb", wordBreak: "break-all", fontSize: "0.8rem" }}>{it.target_url}</a></td>
                <td style={{ ...td, fontWeight: "bold", color: unchecked ? "#cbd5e1" : it.latest_tongsearch_rank ? "#16a34a" : "#94a3b8" }}>{unchecked ? "-" : rankText(it.latest_tongsearch_rank)}</td>
                <td style={{ ...td, fontWeight: "bold", color: unchecked ? "#cbd5e1" : it.latest_cafetab_rank ? "#16a34a" : "#94a3b8" }}>{unchecked ? "-" : rankText(it.latest_cafetab_rank)}</td>
                <td style={td}>{st === "missing" ? <span style={{ color: "#dc2626", fontWeight: "bold" }}>🔴 누락</span> : st === "warn" ? <span style={{ color: "#d97706" }}>⚠️ 미노출</span> : st === "ok" ? <span style={{ color: "#16a34a", fontWeight: "bold" }}>✅ 노출</span> : <span style={{ color: "#94a3b8" }} title="아직 순위 수집이 한 번도 안 됐습니다. '지금 수집'을 눌러 확인하세요.">⏳ 미검사</span>}</td>
                <td style={{ ...td, color: "#64748b", fontSize: "0.82rem" }}>{it.last_checked_date || "-"}</td>
                <td style={{ ...td, fontSize: "0.78rem", color: "#475569" }}>{(it.history || []).map(h => h.tongsearch_rank ?? "-").join(" → ") || "-"}</td>
                <td style={{ ...td, whiteSpace: "nowrap" }} onClick={stop}>
                  {st === "missing" && (
                    <button onClick={() => window.open(it.target_url, "_blank")} title="블로그 글로 이동해 직접 삭제하세요" style={{ padding: "0.35rem 0.7rem", background: "#dc2626", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: "bold", marginRight: "0.4rem" }}>🗑 열어서 삭제</button>
                  )}
                  <button onClick={toggle} style={{ padding: "0.35rem 0.7rem", background: open ? "#334155" : "#0ea5e9", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: "bold", marginRight: "0.4rem" }}>{open ? "▲ 접기" : "📊 분석"}</button>
                  <button onClick={() => checkNow(it.id)} style={{ padding: "0.35rem 0.7rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: "bold", marginRight: "0.4rem" }}>지금 수집</button>
                  <button onClick={() => removeItem(it.id)} title="순위 추적 목록에서만 제거(블로그 글은 안 지워짐)" style={{ padding: "0.35rem 0.7rem", background: "#ef4444", color: "white", border: "none", borderRadius: "5px", cursor: "pointer" }}>삭제</button>
                </td>
              </tr>
              {open && (
                <tr>
                  <td colSpan={8} style={{ padding: 0, borderBottom: "1px solid #f1f5f9", background: "#f8fafc" }}>
                    <div style={{ padding: "1.2rem 1.4rem" }}>
                      <RankDetail item={it} tabLabel={tabLabel} onCheck={checkNow} />
                    </div>
                  </td>
                </tr>
              )}
              </React.Fragment>
            );})}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────── 순위 변동 그래프 (인버트 축: 1위=맨 위) ───────────────
function RankChart({ history, tabLabel }) {
  const pts = (history || []).map((h, i) => ({ i, date: h.date, t: h.tongsearch_rank, c: h.cafetab_rank }));
  const ranks = [];
  pts.forEach(p => { if (p.t != null) ranks.push(p.t); if (p.c != null) ranks.push(p.c); });
  if (pts.length === 0 || ranks.length === 0) {
    return <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8", fontSize: "0.9rem" }}>아직 그래프로 그릴 순위 데이터가 없습니다.<br />‘지금 수집’을 며칠 반복하면 변동 추이가 쌓입니다.</div>;
  }
  const maxR = Math.max(...ranks, 5);
  const minR = 1;
  const W = 660, H = 260, pl = 40, pr = 78, ptop = 18, pbot = 34;
  const iw = W - pl - pr, ih = H - ptop - pbot;
  const x = (i) => pts.length === 1 ? pl + iw / 2 : pl + iw * (i / (pts.length - 1));
  const y = (r) => ptop + ih * ((r - minR) / ((maxR - minR) || 1));  // r=1 → 위, r=max → 아래
  const md = (d) => (d || "").slice(5).replace("-", "/");

  const path = (key) => {
    let d = "", pen = false;
    pts.forEach(p => { const v = p[key]; if (v == null) { pen = false; return; } d += (pen ? "L" : "M") + x(p.i).toFixed(1) + " " + y(v).toFixed(1) + " "; pen = true; });
    return d.trim();
  };
  // y 눈금
  const ticks = []; const step = Math.max(1, Math.round(maxR / 4));
  for (let r = 1; r <= maxR; r += step) ticks.push(r);
  if (ticks[ticks.length - 1] !== maxR) ticks.push(maxR);
  // x 라벨(너무 촘촘하면 솎아냄)
  const xEvery = pts.length > 8 ? Math.ceil(pts.length / 7) : 1;
  const lastOf = (key) => { for (let i = pts.length - 1; i >= 0; i--) if (pts[i][key] != null) return pts[i]; return null; };
  const lt = lastOf("t"), lc = lastOf("c");
  const series = [
    { key: "t", label: "통합검색", color: "#2563eb", last: lt },
    { key: "c", label: tabLabel, color: "#d97706", last: lc },
  ];

  return (
    <div>
      <div style={{ display: "flex", gap: "1.2rem", alignItems: "center", marginBottom: "0.4rem", fontSize: "0.82rem", color: "#475569" }}>
        {series.map(s => (
          <span key={s.key} style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
            <span style={{ width: "14px", height: "3px", background: s.color, borderRadius: "2px", display: "inline-block" }} />{s.label}
          </span>
        ))}
        <span style={{ marginLeft: "auto", color: "#94a3b8" }}>↑ 위쪽일수록 상위 노출 · 선이 끊긴 곳 = 미노출</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", minWidth: "480px", height: "auto", display: "block" }}>
          {/* 가로 눈금선 */}
          {ticks.map(r => (
            <g key={r}>
              <line x1={pl} y1={y(r)} x2={W - pr} y2={y(r)} stroke="#eef2f7" strokeWidth="1" />
              <text x={pl - 6} y={y(r) + 3} textAnchor="end" fontSize="10" fill="#94a3b8">{r}위</text>
            </g>
          ))}
          {/* x축 날짜 */}
          {pts.map((p, i) => (i % xEvery === 0 || i === pts.length - 1) ? (
            <text key={p.i} x={x(p.i)} y={H - pbot + 16} textAnchor="middle" fontSize="10" fill="#94a3b8">{md(p.date)}</text>
          ) : null)}
          {/* 라인 + 포인트 */}
          {series.map(s => (
            <g key={s.key}>
              <path d={path(s.key)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              {pts.map(p => p[s.key] != null ? (
                <circle key={p.i} cx={x(p.i)} cy={y(p[s.key])} r="4" fill="#fff" stroke={s.color} strokeWidth="2">
                  <title>{p.date} · {s.label} {p[s.key]}위</title>
                </circle>
              ) : null)}
              {/* 끝점 직접 라벨 */}
              {s.last ? (
                <text x={x(s.last.i) + 8} y={y(s.last[s.key]) + 3} fontSize="11" fontWeight="bold" fill={s.color}>{s.last[s.key]}위</text>
              ) : null}
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

function RankDetail({ item, tabLabel, onCheck }) {
  const hist = item.history || [];
  const best = (key) => { const v = hist.map(h => h[key]).filter(x => x != null); return v.length ? Math.min(...v) : null; };
  const rk = (v) => (v == null ? "미노출" : `${v}위`);
  const delta = (cur, prev) => {
    if (cur == null || prev == null) return null;
    const d = prev - cur;  // 순위는 작아질수록 상승
    if (d === 0) return <span style={{ color: "#94a3b8" }}>—</span>;
    return d > 0 ? <span style={{ color: "#16a34a", fontWeight: "bold" }}>▲ {d}</span> : <span style={{ color: "#dc2626", fontWeight: "bold" }}>▼ {-d}</span>;
  };
  const tile = { flex: "1 1 120px", background: "white", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "0.7rem 0.9rem" };
  const tileLbl = { fontSize: "0.72rem", color: "#64748b", marginBottom: "0.2rem" };
  const tileVal = { fontSize: "1.15rem", fontWeight: "bold", color: "#0f172a" };
  const th = { padding: "0.45rem 0.7rem", textAlign: "left", fontSize: "0.76rem", color: "#64748b", borderBottom: "1px solid #e2e8f0", whiteSpace: "nowrap" };
  const td2 = { padding: "0.45rem 0.7rem", fontSize: "0.82rem", borderBottom: "1px solid #f1f5f9" };
  const rows = [...hist].reverse();  // 최신 먼저

  return (
    <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.1rem 1.3rem" }}>
      {/* 요약 타일 */}
      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginBottom: "1.1rem" }}>
        <div style={{ ...tile, background: "#f8fafc" }}><div style={tileLbl}>현재 통합검색</div><div style={{ ...tileVal, color: item.latest_tongsearch_rank ? "#2563eb" : "#94a3b8" }}>{rk(item.latest_tongsearch_rank)}</div></div>
        <div style={{ ...tile, background: "#f8fafc" }}><div style={tileLbl}>현재 {tabLabel}</div><div style={{ ...tileVal, color: item.latest_cafetab_rank ? "#d97706" : "#94a3b8" }}>{rk(item.latest_cafetab_rank)}</div></div>
        <div style={{ ...tile, background: "#f8fafc" }}><div style={tileLbl}>최고 통합검색</div><div style={tileVal}>{rk(best("tongsearch_rank"))}</div></div>
        <div style={{ ...tile, background: "#f8fafc" }}><div style={tileLbl}>검사 횟수</div><div style={tileVal}>{hist.length}회</div></div>
      </div>

      {/* 순위 변동 그래프 */}
      <div style={{ fontSize: "0.9rem", fontWeight: "bold", color: "#334155", marginBottom: "0.5rem" }}>순위 변동 그래프</div>
      <RankChart history={hist} tabLabel={tabLabel} />

      {/* 매일 순위 분석 표 */}
      <div style={{ fontSize: "0.9rem", fontWeight: "bold", color: "#334155", margin: "1.3rem 0 0.5rem" }}>매일 검색 순위 분석</div>
      <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "420px" }}>
          <thead><tr>
            <th style={th}>날짜</th><th style={th}>통합검색</th><th style={th}>전일대비</th>
            <th style={th}>{tabLabel}</th><th style={th}>전일대비</th>
          </tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td style={td2} colSpan={5}><span style={{ color: "#94a3b8" }}>아직 수집된 기록이 없습니다. ‘지금 수집’을 눌러 첫 순위를 확인하세요.</span></td></tr>
            ) : rows.map((h, idx) => {
              const prev = rows[idx + 1];  // 하루 전(정렬상 다음)
              return (
                <tr key={h.date}>
                  <td style={td2}>{h.date}</td>
                  <td style={{ ...td2, fontWeight: "bold", color: h.tongsearch_rank ? "#2563eb" : "#94a3b8" }}>{rk(h.tongsearch_rank)}</td>
                  <td style={td2}>{prev ? delta(h.tongsearch_rank, prev.tongsearch_rank) : "-"}</td>
                  <td style={{ ...td2, fontWeight: "bold", color: h.cafetab_rank ? "#d97706" : "#94a3b8" }}>{rk(h.cafetab_rank)}</td>
                  <td style={td2}>{prev ? delta(h.cafetab_rank, prev.cafetab_rank) : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.1rem" }}>
        <button onClick={() => onCheck(item.id)} style={{ padding: "0.55rem 1.1rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>지금 수집</button>
      </div>
    </div>
  );
}

export default function CafeRankPage() {
  return (
    <Suspense fallback={null}>
      <CafeRankInner />
    </Suspense>
  );
}
