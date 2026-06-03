"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect } from "react";

export default function BlogCheckPage() {
  const [keywords, setKeywords] = useState([]);
  const [blogId, setBlogId] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
    </main>
  );
}