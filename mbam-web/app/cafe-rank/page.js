"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchWithAuth } from "../utils/api";

function CafeRankInner() {
  const searchParams = useSearchParams();
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
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
        <button onClick={addItem} disabled={loading} style={{ padding: "0.65rem 1.2rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: loading ? "wait" : "pointer", whiteSpace: "nowrap" }}>＋ 추적 추가</button>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
        <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: 0 }}>추적 목록 ({shownItems.length})</h2>
        <button onClick={load} style={{ padding: "0.45rem 0.9rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem" }}>🔄 새로고침</button>
      </div>

      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "10px", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "760px" }}>
          <thead>
            <tr>
              <th style={th}>키워드 / 별칭</th>
              <th style={th}>카페 글 URL</th>
              <th style={th}>통합검색</th>
              <th style={th}>{tabLabel}</th>
              <th style={th}>최근 수집</th>
              <th style={th}>최근 추이(통검)</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {shownItems.length === 0 ? (
              <tr><td style={td} colSpan={7}><span style={{ color: "#94a3b8" }}>아직 추적 중인 {typeLabel} 글이 없습니다. 위에서 추가하세요.</span></td></tr>
            ) : shownItems.map(it => (
              <tr key={it.id}>
                <td style={td}><b>{it.keyword}</b>{it.name ? <div style={{ color: "#64748b", fontSize: "0.8rem" }}>{it.name}</div> : null}</td>
                <td style={{ ...td, maxWidth: "260px" }}><a href={it.target_url} target="_blank" rel="noreferrer" style={{ color: "#2563eb", wordBreak: "break-all", fontSize: "0.8rem" }}>{it.target_url}</a></td>
                <td style={{ ...td, fontWeight: "bold", color: it.latest_tongsearch_rank ? "#16a34a" : "#94a3b8" }}>{rankText(it.latest_tongsearch_rank)}</td>
                <td style={{ ...td, fontWeight: "bold", color: it.latest_cafetab_rank ? "#16a34a" : "#94a3b8" }}>{rankText(it.latest_cafetab_rank)}</td>
                <td style={{ ...td, color: "#64748b", fontSize: "0.82rem" }}>{it.last_checked_date || "-"}</td>
                <td style={{ ...td, fontSize: "0.78rem", color: "#475569" }}>{(it.history || []).map(h => h.tongsearch_rank ?? "-").join(" → ") || "-"}</td>
                <td style={{ ...td, whiteSpace: "nowrap" }}>
                  <button onClick={() => checkNow(it.id)} style={{ padding: "0.35rem 0.7rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: "bold", marginRight: "0.4rem" }}>지금 수집</button>
                  <button onClick={() => removeItem(it.id)} style={{ padding: "0.35rem 0.7rem", background: "#ef4444", color: "white", border: "none", borderRadius: "5px", cursor: "pointer" }}>삭제</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
