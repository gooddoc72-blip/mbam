"use client";
import { fetchWithAuth, resolveMaybeAgent } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";
import { useState, useEffect } from "react";

export default function BlogCheckPage() {
  const [keywords, setKeywords] = usePersistentState("blog-check:keywords", []);
  const [blogId, setBlogId] = usePersistentState("blog-check:blogId", "");
  const [keywordInput, setKeywordInput] = usePersistentState("blog-check:keywordInput", "");
  const [loading, setLoading] = usePersistentState("blog-check:loading", false);
  const [error, setError] = usePersistentState("blog-check:error", null);

  // 블로그 지수 진단
  const [idxInput, setIdxInput] = useState("");
  const [idxLoading, setIdxLoading] = useState(false);
  const [idxError, setIdxError] = useState(null);
  const [idxResult, setIdxResult] = useState(null);
  const [idxSaving, setIdxSaving] = useState(false);
  const [savedList, setSavedList] = useState([]);

  const loadSavedIndex = async () => {
    try {
      const res = await fetchWithAuth("/api/seo/blog-index/saved");
      if (res.ok) setSavedList((await res.json()).items || []);
    } catch (e) { /* ignore */ }
  };
  useEffect(() => { loadSavedIndex(); }, []);

  const saveCurrentIndex = async () => {
    if (!idxResult) return;
    setIdxSaving(true);
    try {
      const s = idxResult.stats, i = idxResult.index;
      const res = await fetchWithAuth("/api/seo/blog-index/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          blog_id: s.blog_id, title: s.title || s.blog_id,
          score: i.score, grade: i.grade, tier: i.tier, level: i.level,
          result: idxResult,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "저장 실패");
      alert("진단 결과를 저장했습니다.");
      loadSavedIndex();
    } catch (err) {
      alert(err.message);
    } finally {
      setIdxSaving(false);
    }
  };

  const deleteSavedIndex = async (id) => {
    if (!confirm("저장된 진단을 삭제할까요?")) return;
    try {
      const res = await fetchWithAuth(`/api/seo/blog-index/saved/${id}`, { method: "DELETE" });
      if (res.ok) loadSavedIndex();
    } catch (e) { /* ignore */ }
  };

  const diagnoseIndex = async (e) => {
    e.preventDefault();
    if (!idxInput.trim()) return;
    setIdxLoading(true); setIdxError(null); setIdxResult(null);
    try {
      const res = await fetchWithAuth("/api/seo/blog-index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blog: idxInput.trim() }),
      });
      let data = await res.json();
      if (!res.ok) throw new Error(data.detail || "진단 실패");
      data = await resolveMaybeAgent(data, { tries: 120, intervalMs: 1000 });
      setIdxResult(data);
      try { addHistory("blog-check", { summary: `블로그 지수 진단 · ${idxInput || ''}` }); } catch (e) {}
    } catch (err) {
      setIdxError(err.message);
    } finally {
      setIdxLoading(false);
    }
  };

  const tierColor = (tier) => {
    if (!tier) return "#64748b";
    if (tier.startsWith("최적")) return "#10b981";
    if (tier.startsWith("준최적")) return "#3b82f6";
    if (tier === "일반") return "#f59e0b";
    return "#ef4444"; // 저품질
  };
  const fmtNum = (n) => (n == null ? "-" : Number(n).toLocaleString());
  const fmtDate = (ms) => (ms ? new Date(ms).toLocaleDateString("ko-KR") : "-");
  const BD_LABELS = { audience: "이웃·영향력", traffic: "방문·트래픽", engagement: "인게이지먼트", volume: "누적 글수", age: "업력", consistency: "전문성", exposureRaw: "검색노출" };

  // 블덱스 스타일 레벨 사다리 (위=최상 최적5 → 아래=저품질). 진단 티어를 이 목록과 매칭해 강조.
  const TIER_LADDER = [
    { label: "최적5", c: "#047857" }, { label: "최적4", c: "#059669" }, { label: "최적3", c: "#10b981" },
    { label: "최적2", c: "#10b981" }, { label: "최적1", c: "#34d399" },
    { label: "준최적8", c: "#1d4ed8" }, { label: "준최적7", c: "#2563eb" }, { label: "준최적6", c: "#3b82f6" },
    { label: "준최적5", c: "#3b82f6" }, { label: "준최적4", c: "#60a5fa" }, { label: "준최적3", c: "#60a5fa" },
    { label: "준최적2", c: "#93c5fd" }, { label: "준최적1", c: "#93c5fd" },
    { label: "일반", c: "#f59e0b" }, { label: "저품질", c: "#ef4444" },
  ];

  // 컴포넌트 마운트 시 키워드 목록 로드
  useEffect(() => {
    fetchKeywords();
  }, []);

  const fetchKeywords = async () => {
    try {
      const res = await fetchWithAuth("/api/seo/rank/keywords");
      if (res.ok) {
        const data = await res.json();
        setKeywords(data.data || []);
      }
    } catch (err) {
      console.error("키워드 로드 실패:", err);
    }
  };

  const handleAddKeyword = async (e) => {
    e.preventDefault();
    if (!blogId.trim() || !keywordInput.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/seo/rank/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blog_id: blogId, keyword: keywordInput }),
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || "추가 실패");
      }

      setBlogId("");
      setKeywordInput("");
      fetchKeywords(); // 전체 갱신
      
      if (data.rank > 0) {
        alert(`실시간 조회 결과: 현재 ${data.rank}위에 노출 중입니다!`);
      } else {
        alert("검색 결과 Top 75 이내에 해당 블로그의 글이 발견되지 않았습니다.");
      }
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async (id) => {
    try {
      const res = await fetchWithAuth("/api/seo/rank/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword_id: id }),
      });
      if (res.ok) {
        fetchKeywords();
      }
    } catch (err) {
      console.error("새로고침 실패", err);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("정말 삭제하시겠습니까?")) return;
    try {
      const res = await fetchWithAuth("/api/seo/rank/delete", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword_id: id }),
      });
      if (res.ok) {
        fetchKeywords();
      }
    } catch (err) {
      console.error("삭제 실패", err);
    }
  };

  // 상태 뱃지 렌더러
  const renderBadge = (rankVal) => {
    if (rankVal === -1 || rankVal === "-") return <span style={{ color: "#64748b", fontWeight: "bold" }}>미조회</span>;
    if (rankVal === 0 || rankVal > 75) return <span style={{ color: "#ef4444", fontWeight: "bold" }}>권외</span>;
    if (rankVal <= 5) return <span style={{ color: "#10b981", fontWeight: "bold" }}>최상위 (Top 5)</span>;
    return <span style={{ color: "#3b82f6", fontWeight: "bold" }}>노출 중</span>;
  };

  return (
    <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem" }}>
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2.5rem", fontWeight: "bold", background: "linear-gradient(90deg, #3b82f6, #8b5cf6)", WebkitBackgroundClip: "text", color: "transparent", marginBottom: "0.5rem" }}>
          🛡️ 블로그 진단 및 순위
        </h1>
        <p style={{ color: "#64748b", fontSize: "1.1rem" }}>
          내 블로그의 건강 상태와 검색 순위를 실시간으로 추적하고 관리합니다.
        </p>
      </header>

      {/* 블로그 지수 진단 카드 */}
      <div className="glass-card" style={{ padding: "2rem", marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.5rem", marginBottom: "0.3rem", color: "#1e293b", fontWeight: "bold" }}>🩺 블로그 지수 진단 (추정)</h2>
        <p style={{ color: "#64748b", marginBottom: "1.2rem", fontSize: "0.92rem" }}>
          개설일·누적 글수·이웃·방문자·발행 활성도·인게이지먼트를 종합해 블로그 지수(0~100)와 등급을 추정합니다. <span style={{ color: "#94a3b8" }}>※ 네이버 공식 지수가 아닌 추정치입니다.</span>
        </p>
        <form onSubmit={diagnoseIndex} style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginBottom: idxResult || idxError ? "1.5rem" : 0 }}>
          <input
            type="text"
            style={{ flex: "1 1 280px", padding: "0.8rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none" }}
            placeholder="블로그 ID 또는 URL (예: bonetacasa, blog.naver.com/bonetacasa)"
            value={idxInput}
            onChange={(e) => setIdxInput(e.target.value)}
            disabled={idxLoading}
          />
          <button type="submit" className="btn-primary" style={{ padding: "0.8rem 1.6rem", fontSize: "1rem" }} disabled={idxLoading || !idxInput.trim()}>
            {idxLoading ? "진단 중... (5~10초)" : "🩺 지수 진단"}
          </button>
        </form>

        {idxError && <div style={{ color: "#ef4444", fontWeight: "bold" }}>{idxError}</div>}

        {idxResult && (() => {
          const s = idxResult.stats, i = idxResult.index;
          return (
            <>
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.8rem" }}>
              <button onClick={saveCurrentIndex} disabled={idxSaving} style={{ padding: "0.5rem 1.1rem", background: "#10b981", color: "white", border: "none", borderRadius: "8px", fontWeight: "bold", cursor: idxSaving ? "wait" : "pointer" }}>
                {idxSaving ? "저장 중..." : "💾 진단 결과 저장"}
              </button>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "1.5rem" }}>
              {/* 점수 + 블덱스 스타일 레벨 사다리 */}
              <div style={{ flex: "0 0 230px", padding: "1.2rem", background: "#f8fafc", borderRadius: "12px" }}>
                <div style={{ textAlign: "center", marginBottom: "0.8rem" }}>
                  <div style={{ fontSize: "0.9rem", color: "#64748b" }}>{s.title || s.blog_id}</div>
                  <div style={{ fontSize: "2.8rem", fontWeight: "bold", color: tierColor(i.tier), lineHeight: 1.1 }}>{i.score}<span style={{ fontSize: "1rem", color: "#94a3b8" }}>/100</span></div>
                  <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>객관지수 Lv {i.level} · 등급 {i.grade} · 활성도 ×{i.operation_factor}</div>
                </div>
                {/* 사다리: 위=최적5 ~ 아래=저품질, 진단 레벨 강조 */}
                <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                  {TIER_LADDER.map((t) => {
                    const active = t.label === i.tier;
                    return (
                      <div key={t.label} style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: active ? "0.4rem 0.7rem" : "0.18rem 0.7rem",
                        borderRadius: "6px",
                        background: active ? t.c : "#eef2f7",
                        color: active ? "white" : "#94a3b8",
                        fontWeight: active ? "bold" : "normal",
                        fontSize: active ? "0.95rem" : "0.8rem",
                        boxShadow: active ? "0 2px 8px rgba(0,0,0,0.15)" : "none",
                        transition: "all 0.15s",
                      }}>
                        <span>{t.label}</span>
                        {active && <span style={{ fontSize: "0.8rem" }}>◀ 내 블로그 ({i.score}점)</span>}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 핵심 통계 */}
              <div style={{ flex: "1 1 260px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", alignContent: "start" }}>
                {[
                  ["개설(추정)", fmtDate(s.first_post_date)],
                  ["누적 글수", fmtNum(s.total_post_count ?? s.post_count)],
                  ["이웃·구독", fmtNum(s.subscriber_count)],
                  ["누적 방문", fmtNum(s.total_visitor_count)],
                  ["오늘 방문", fmtNum(s.day_visitor_count)],
                  ["최근30일 발행", `${s.recent_post_count_30d}건`],
                  ["글당 댓글", s.avg_comments.toFixed(1)],
                  ["글당 공감", s.avg_sympathy.toFixed(1)],
                ].map(([k, v]) => (
                  <div key={k} style={{ background: "#f8fafc", borderRadius: "8px", padding: "0.6rem 0.8rem" }}>
                    <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{k}</div>
                    <div style={{ fontSize: "1.05rem", fontWeight: "bold", color: "#1e293b" }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* 항목별 기여 (breakdown) */}
              <div style={{ flex: "1 1 240px" }}>
                <div style={{ fontSize: "0.85rem", color: "#475569", fontWeight: "bold", marginBottom: "0.5rem" }}>항목별 기여도</div>
                {Object.entries(i.breakdown).map(([k, v]) => (
                  <div key={k} style={{ marginBottom: "0.5rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", color: "#64748b" }}>
                      <span>{BD_LABELS[k] || k}</span><span style={{ fontWeight: "bold", color: "#1e293b" }}>{v}</span>
                    </div>
                    <div style={{ background: "#e2e8f0", borderRadius: "999px", height: "7px", overflow: "hidden" }}>
                      <div style={{ width: `${Math.min(100, v * 4)}%`, height: "100%", background: "linear-gradient(90deg,#3b82f6,#8b5cf6)" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
            </>
          );
        })()}

        {/* 저장된 진단 목록 */}
        {savedList.length > 0 && (
          <div style={{ marginTop: "1.8rem", borderTop: "1px solid #e2e8f0", paddingTop: "1.2rem" }}>
            <div style={{ fontSize: "1rem", fontWeight: "bold", color: "#334155", marginBottom: "0.7rem" }}>💾 저장된 진단 ({savedList.length})</div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem", whiteSpace: "nowrap" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#64748b", textAlign: "left" }}>
                    <th style={{ padding: "0.5rem 0.7rem" }}>블로그</th>
                    <th style={{ padding: "0.5rem 0.7rem" }}>지수</th>
                    <th style={{ padding: "0.5rem 0.7rem" }}>티어</th>
                    <th style={{ padding: "0.5rem 0.7rem" }}>레벨</th>
                    <th style={{ padding: "0.5rem 0.7rem" }}>진단일</th>
                    <th style={{ padding: "0.5rem 0.7rem", textAlign: "center" }}>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {savedList.map((r) => (
                    <tr key={r.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "0.5rem 0.7rem", fontWeight: "bold", color: "#1e293b" }}>{r.title || r.blog_id} <span style={{ color: "#94a3b8", fontWeight: "normal" }}>({r.blog_id})</span></td>
                      <td style={{ padding: "0.5rem 0.7rem", fontWeight: "bold", color: tierColor(r.tier) }}>{r.score}</td>
                      <td style={{ padding: "0.5rem 0.7rem" }}><span style={{ padding: "0.15rem 0.6rem", borderRadius: "999px", background: tierColor(r.tier), color: "white", fontSize: "0.8rem", fontWeight: "bold" }}>{r.tier}</span></td>
                      <td style={{ padding: "0.5rem 0.7rem", color: "#475569" }}>Lv {r.level}</td>
                      <td style={{ padding: "0.5rem 0.7rem", color: "#64748b", fontSize: "0.82rem" }}>{r.created_at ? new Date(r.created_at).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" }) : "-"}</td>
                      <td style={{ padding: "0.5rem 0.7rem", textAlign: "center" }}>
                        <button onClick={() => { if (r.result) { setIdxResult(r.result); setIdxInput(r.blog_id); } }} style={{ background: "transparent", border: "none", cursor: "pointer", marginRight: "0.4rem" }} title="결과 보기">👁️</button>
                        <button onClick={() => deleteSavedIndex(r.id)} style={{ background: "transparent", border: "none", cursor: "pointer" }} title="삭제">🗑️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "2rem" }}>

        {/* 좌측 입력 패널 */}
        <div className="glass-card" style={{ flex: "1 1 300px", padding: "2rem", height: "fit-content" }}>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "1.5rem", color: "#1e293b", fontWeight: "bold" }}>
            🏢 순위 추적 등록
          </h2>
          <form onSubmit={handleAddKeyword} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "#475569", fontWeight: "bold" }}>블로그 ID 또는 URL</label>
              <input
                type="text"
                style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none" }}
                placeholder="예: naver_blog_id"
                value={blogId}
                onChange={(e) => setBlogId(e.target.value)}
                disabled={loading}
              />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "#475569", fontWeight: "bold" }}>추적 키워드</label>
              <input
                type="text"
                style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none" }}
                placeholder="예: 부산 서면 맛집"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                disabled={loading}
              />
            </div>
            
            {error && <div style={{ color: "#ef4444", fontSize: "0.9rem" }}>{error}</div>}
            
            <button 
              type="submit" 
              className="btn-primary" 
              style={{ marginTop: "1rem", width: "100%", padding: "1rem", fontSize: "1.1rem" }}
              disabled={loading || !blogId.trim() || !keywordInput.trim()}
            >
              {loading ? "네이버 실시간 순위 조회 중..." : "➕ 추적 등록 및 실시간 조회"}
            </button>
          </form>
        </div>

        {/* 우측 모니터링 테이블 */}
        <div className="glass-card" style={{ flex: "2 1 600px", minWidth: 0, padding: "2rem" }}>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "1.5rem", color: "#1e293b", fontWeight: "bold", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span>📈 순위 모니터링 보드</span>
            <button onClick={fetchKeywords} style={{ background: "transparent", border: "none", cursor: "pointer", fontSize: "1.5rem" }} title="새로고침">🔄</button>
          </h2>

          {keywords.length === 0 ? (
            <div style={{ textAlign: "center", padding: "3rem", background: "#f8fafc", borderRadius: "12px", color: "#64748b" }}>
              현재 추적 중인 키워드가 없습니다.<br/>왼쪽 패널에서 블로그 ID와 키워드를 입력해 등록해 주세요.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.95rem", whiteSpace: "nowrap" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#475569" }}>
                    <th style={{ padding: "1rem" }}>블로그 ID</th>
                    <th style={{ padding: "1rem" }}>추적 키워드</th>
                    <th style={{ padding: "1rem" }}>최근 순위</th>
                    <th style={{ padding: "1rem" }}>상태</th>
                    <th style={{ padding: "1rem" }}>최근 조회일</th>
                    <th style={{ padding: "1rem", textAlign: "center" }}>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {keywords.map((kw) => (
                    <tr key={kw.id} style={{ borderBottom: "1px solid #f1f5f9", transition: "background 0.2s" }} onMouseEnter={(e)=>e.currentTarget.style.background="#f8fafc"} onMouseLeave={(e)=>e.currentTarget.style.background="transparent"}>
                      <td style={{ padding: "1rem", fontWeight: "bold", color: "#1e293b" }}>{kw.blog_id}</td>
                      <td style={{ padding: "1rem", color: "#475569" }}>{kw.keyword}</td>
                      <td style={{ padding: "1rem", fontWeight: "bold", color: kw.rank_val > 0 ? "#1e293b" : "#ef4444" }}>{kw.rank}</td>
                      <td style={{ padding: "1rem" }}>{renderBadge(kw.rank_val)}</td>
                      <td style={{ padding: "1rem", color: "#64748b", fontSize: "0.85rem" }}>{kw.date}</td>
                      <td style={{ padding: "1rem", textAlign: "center" }}>
                        <button onClick={() => handleRefresh(kw.id)} style={{ background: "transparent", border: "none", cursor: "pointer", marginRight: "0.5rem" }} title="실시간 조회">🔄</button>
                        <button onClick={() => handleDelete(kw.id)} style={{ background: "transparent", border: "none", cursor: "pointer" }} title="삭제">🗑️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      <WorkHistory menuKey="blog-check" />
    </main>
  );
}