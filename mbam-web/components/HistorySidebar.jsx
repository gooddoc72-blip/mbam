"use client";
import { useEffect, useState } from "react";
import { fetchWithAuth } from "../app/utils/api";

export default function HistorySidebar({ onSelectHistory }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/seo/history");
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setLoading(false);
    }
  };

  const deleteOne = async (id, e) => {
    e.stopPropagation();
    // 낙관적 제거
    setHistory((prev) => prev.filter((h) => h.id !== id));
    try {
      await fetchWithAuth(`/api/seo/history/${id}`, { method: "DELETE" });
    } catch (err) {
      console.error("삭제 실패:", err);
      fetchHistory();
    }
  };

  const clearAll = async () => {
    if (!confirm("최근 검색 기록을 모두 삭제할까요?")) return;
    setHistory([]);
    try {
      await fetchWithAuth("/api/seo/history", { method: "DELETE" });
    } catch (err) {
      console.error("전체 삭제 실패:", err);
      fetchHistory();
    }
  };

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: "1rem" }}>
        <h3 className="mb-2">🕒 최근 검색 기록</h3>
        <div className="skeleton skeleton-text"></div>
        <div className="skeleton skeleton-text"></div>
        <div className="skeleton skeleton-text"></div>
      </div>
    );
  }

  return (
    <div className="glass-card" style={{ padding: "1rem", height: "100%" }}>
      <div className="flex items-center justify-between mb-2">
        <h3 style={{ margin: 0 }}>🕒 최근 검색 기록</h3>
        <div style={{ display: "flex", gap: "0.3rem", alignItems: "center" }}>
          {history.length > 0 && (
            <button
              onClick={clearAll}
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.8rem", color: "#ef4444", fontWeight: "bold" }}
              title="전체 삭제"
            >
              전체삭제
            </button>
          )}
          <button
            onClick={fetchHistory}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem" }}
            title="새로고침"
          >
            🔄
          </button>
        </div>
      </div>
      
      {history.length === 0 ? (
        <p className="text-sm">저장된 검색 기록이 없습니다.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {history.map((item) => (
            <li key={item.id} style={{ position: "relative" }}>
              <button
                onClick={() => onSelectHistory(item)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "0.8rem",
                  paddingRight: "2rem",
                  background: "rgba(255, 255, 255, 0.5)",
                  border: "1px solid rgba(0,0,0,0.05)",
                  borderRadius: "8px",
                  cursor: "pointer",
                  transition: "all 0.2s"
                }}
                onMouseOver={(e) => e.currentTarget.style.background = "rgba(16, 185, 129, 0.1)"}
                onMouseOut={(e) => e.currentTarget.style.background = "rgba(255, 255, 255, 0.5)"}
              >
                <div className="font-bold text-main">{item.keyword}</div>
                <div className="text-sm">{new Date(item.created_at).toLocaleString("ko-KR", {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                })}</div>
              </button>
              <button
                onClick={(e) => deleteOne(item.id, e)}
                title="삭제"
                style={{
                  position: "absolute", top: "6px", right: "6px",
                  background: "none", border: "none", cursor: "pointer",
                  color: "#94a3b8", fontSize: "1rem", lineHeight: 1, padding: "2px 4px",
                }}
                onMouseOver={(e) => (e.currentTarget.style.color = "#ef4444")}
                onMouseOut={(e) => (e.currentTarget.style.color = "#94a3b8")}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
