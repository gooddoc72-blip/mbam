"use client";
import { useEffect, useState } from "react";

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
        <button 
          onClick={fetchHistory}
          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1.2rem" }}
          title="새로고침"
        >
          🔄
        </button>
      </div>
      
      {history.length === 0 ? (
        <p className="text-sm">저장된 검색 기록이 없습니다.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {history.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => onSelectHistory(item)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "0.8rem",
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
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
