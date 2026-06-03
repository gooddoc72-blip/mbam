"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect } from "react";

export default function ContentCollectPage() {
  const [categories, setCategories] = useState([]);
  const [selectedCat, setSelectedCat] = useState("공공서비스");
  const [fullSyncTime, setFullSyncTime] = useState("기록 없음");
  const [items, setItems] = useState([]);
  const [lastSync, setLastSync] = useState("없음");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Schedule state
  const [scheduleTime, setScheduleTime] = useState("09:00");
  const [interestCategories, setInterestCategories] = useState([]);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);

  // 1. 카테고리 목록 로드
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const res = await fetchWithAuth("/api/content/categories");
        if (res.ok) {
          const data = await res.json();
          setCategories(data.categories || []);
          setFullSyncTime(data.full_sync_time || "기록 없음");
          if (data.categories && data.categories.length > 0 && !selectedCat) {
            setSelectedCat(data.categories[0]);
          }
        }
      } catch (err) {
        console.error("카테고리 로드 실패:", err);
      }
    };
    
    const fetchSchedule = async () => {
      try {
        const res = await fetchWithAuth("/api/content/schedule");
        if (res.ok) {
          const data = await res.json();
          setScheduleTime(data.schedule_time);
          if (data.interest_categories) {
            setInterestCategories(data.interest_categories);
          }
        }
      } catch (err) {
        console.error("스케줄 로드 실패:", err);
      }
    };
    
    fetchCategories();
    fetchSchedule();
  }, []);

  // 2. 카테고리 선택 시 목록 로드
  useEffect(() => {
    if (selectedCat) {
      fetchItems(selectedCat);
    }
  }, [selectedCat]);

  const fetchItems = async (cat) => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/content/list?category=${encodeURIComponent(cat)}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
        setLastSync(data.last_sync || "없음");
      }
    } catch (err) {
      console.error("아이템 로드 실패:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/content/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: selectedCat }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "수집 실패");
      
      alert(`✅ ${data.count}건 수집 완료!`);
      setLastSync(data.last_sync);
      fetchItems(selectedCat);
    } catch (err) {
      setError(err.message);
      alert("데이터 수집 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSchedule = async () => {
    setIsSavingSchedule(true);
    try {
      const res = await fetchWithAuth("/api/content/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schedule_time: scheduleTime, interest_categories: interestCategories }),
      });
      if (res.ok) {
        alert("수집 시간이 저장되었습니다.");
      } else {
        const data = await res.json();
        alert(data.detail || "저장에 실패했습니다.");
      }
    } catch (err) {
      alert("스케줄 저장 중 오류가 발생했습니다.");
    } finally {
      setIsSavingSchedule(false);
    }
  };

  // Handle interest category toggle
  const toggleInterest = (categoryName) => {
    setInterestCategories(prev => {
      if (prev.includes(categoryName)) {
        return prev.filter(c => c !== categoryName);
      } else {
        return [...prev, categoryName];
      }
    });
  };

  const filteredItems = items.filter(item => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (item.title && item.title.toLowerCase().includes(q)) || 
           (item.source && item.source.toLowerCase().includes(q));
  });

  return (
    <main style={{ maxWidth: "1400px", margin: "0 auto", padding: "2rem" }}>
      <header style={{ marginBottom: "2rem", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontSize: "2.5rem", fontWeight: "bold", background: "linear-gradient(90deg, #3b82f6, #8b5cf6)", WebkitBackgroundClip: "text", color: "transparent", marginBottom: "0.5rem" }}>
            📰 글감 수집
          </h1>
          <p style={{ color: "#64748b", fontSize: "1.1rem" }}>
            정부 지원금, K-MOOC, 트렌드 뉴스 등 양질의 포스팅 글감을 수집합니다.
          </p>
        </div>
        
        <div style={{ background: "white", padding: "1rem", borderRadius: "8px", border: "1px solid #e2e8f0", display: "flex", alignItems: "center", gap: "1rem", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
          <div style={{ fontSize: "0.9rem", color: "#475569", fontWeight: "bold" }}>🕒 매일 자동 수집 시간</div>
          <input 
            type="time" 
            value={scheduleTime} 
            onChange={(e) => setScheduleTime(e.target.value)} 
            style={{ padding: "0.5rem", borderRadius: "6px", border: "1px solid #cbd5e1" }}
          />
          <div style={{ fontSize: "0.85rem", color: "#64748b", marginLeft: "0.5rem" }}>
            *저장 시 선택된 ⭐관심 카테고리 요약이 텔레그램으로 전송됩니다.
          </div>
          <button 
            onClick={handleSaveSchedule} 
            disabled={isSavingSchedule}
            className="btn-primary" 
            style={{ padding: "0.5rem 1rem", fontSize: "0.9rem" }}
          >
            {isSavingSchedule ? "저장 중..." : "설정 저장"}
          </button>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "2rem" }}>
        
        {/* 좌측 패널 (카테고리) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1rem", color: "#1e293b" }}>📂 카테고리</h3>
            <ul style={{ listStyle: "none", padding: 0 }}>
              {categories.map((cat) => {
                const isSelected = selectedCat === cat;
                const isInterest = interestCategories.includes(cat);
                return (
                  <li key={cat} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                    <button
                      onClick={() => toggleInterest(cat)}
                      title="관심 카테고리로 지정하여 텔레그램 알림 받기"
                      style={{ 
                        background: "none", border: "none", cursor: "pointer", 
                        fontSize: "1.2rem", padding: "0", color: isInterest ? "#fbbf24" : "#cbd5e1",
                        transition: "color 0.2s"
                      }}
                    >
                      {isInterest ? "⭐" : "☆"}
                    </button>
                    <button
                      onClick={() => setSelectedCat(cat)}
                      style={{
                        flex: 1,
                        display: "block",
                        width: "100%",
                        padding: "0.75rem 1rem",
                        textAlign: "left",
                        background: isSelected ? "#eff6ff" : "transparent",
                        color: isSelected ? "#2563eb" : "#475569",
                        border: "none",
                        borderRadius: "6px",
                        fontWeight: isSelected ? "bold" : "normal",
                        cursor: "pointer",
                        transition: "all 0.2s"
                      }}
                    >
                      <span style={{ marginRight: "0.5rem" }}>
                        {isSelected ? "🔘" : "○"}
                      </span>
                      {cat}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="glass-card" style={{ padding: "1.5rem" }}>
            <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase" }}>전체 시스템 동기화</div>
              <div style={{ fontSize: "1rem", fontWeight: "bold", color: "#3b82f6" }}>{fullSyncTime}</div>
            </div>

            <div style={{ background: "white", padding: "12px", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase" }}>선택 카테고리 업데이트</div>
              <div style={{ fontSize: "0.9rem", fontWeight: "bold", color: "#1e293b" }}>{lastSync}</div>
            </div>

            <button 
              onClick={handleRefresh}
              className="btn-primary" 
              style={{ width: "100%", padding: "1rem", display: "flex", justifyContent: "center", gap: "0.5rem" }}
              disabled={loading}
            >
              {loading ? "데이터 수집 중..." : "🔄 현재 항목 실시간 수집"}
            </button>
          </div>
        </div>

        {/* 우측 메인 패널 (데이터 목록) */}
        <div className="glass-card" style={{ padding: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
            <h2 style={{ fontSize: "1.5rem", color: "#1e293b" }}>📋 {selectedCat} 목록</h2>
            
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input
                type="text"
                placeholder="검색어 입력..."
                style={{ padding: "0.5rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1" }}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button onClick={() => setSearchQuery("")} className="btn-secondary" style={{ padding: "0.5rem 1rem" }}>초기화</button>
            </div>
          </div>

          {loading && !items.length ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "#64748b" }}>로딩 중...</div>
          ) : filteredItems.length === 0 ? (
            <div style={{ padding: "3rem", textAlign: "center", background: "#f8fafc", borderRadius: "12px", color: "#64748b" }}>
              데이터가 없습니다. 실시간 수집 버튼을 눌러주세요.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {filteredItems.map((item, idx) => {
                let badgeStr = "";
                if (item.priority === 1) badgeStr = "🆕[최신/혜택]";
                else if (item.priority === 2) badgeStr = "🔥[트렌드]";
                else if (item.priority === 3) badgeStr = "🚨[긴급성]";

                return (
                  <details key={item.id || idx} style={{ background: "white", borderRadius: "12px", border: "1px solid #e2e8f0", overflow: "hidden" }}>
                    <summary style={{ padding: "1rem 1.5rem", cursor: "pointer", fontWeight: "bold", color: "#1e293b", background: "#f8fafc", listStyle: "none", display: "flex", alignItems: "center" }}>
                      <span style={{ color: "#ef4444", marginRight: "0.5rem" }}>{badgeStr}</span>
                      {item.title} ({item.source}) | {item.deadline || "상시"}
                    </summary>
                    <div style={{ padding: "1.5rem", borderTop: "1px solid #e2e8f0" }}>
                      <p style={{ marginBottom: "0.5rem" }}><strong>기관:</strong> {item.source}</p>
                      {item.target && <p style={{ marginBottom: "0.5rem" }}><strong>대상:</strong> {item.target}</p>}
                      {item.amount && <p style={{ marginBottom: "0.5rem" }}><strong>지원내용:</strong> {item.amount}</p>}
                      {item.professor && <p style={{ marginBottom: "0.5rem" }}><strong>교수:</strong> {item.professor}</p>}
                      <p style={{ marginTop: "1rem", color: "#475569" }}>{item.summary}</p>
                      
                      <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
                        <button className="btn-primary" style={{ flex: 1, background: "#10b981" }} onClick={() => {
                            const params = new URLSearchParams({
                              keyword: item.keywords?.[0] || item.title.split(' ')[0],
                              source_data: `[제목] ${item.title}\n[요약] ${item.summary}\n[대상] ${item.target}\n[기간] ${item.deadline}\n[출처] ${item.source}\n[링크] ${item.url}`
                            });
                            window.location.href = `/blog-auto?${params.toString()}`;
                          }}>📝 블로그 작성 준비</button>
                        <button className="btn-primary" style={{ flex: 1, background: "#f59e0b" }} onClick={() => alert("준비중: 카페 자동화로 데이터 연동")}>☕ 카페 작성 준비</button>
                      </div>
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}