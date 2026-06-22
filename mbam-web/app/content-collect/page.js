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

  // 황금키워드 추천 state
  const [goldenLoading, setGoldenLoading] = useState(false);
  const [golden, setGolden] = useState(null); // { keywords:[...], seed:[...], candidate_count }
  const [goldenError, setGoldenError] = useState(null);

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

  // 2. 카테고리 선택 시 목록 + 저장된 황금키워드 결과 로드
  useEffect(() => {
    if (selectedCat) {
      fetchItems(selectedCat);
      fetchGoldenCache(selectedCat);
    }
  }, [selectedCat]);

  // 저장된 황금키워드 추천 결과 복원 (메뉴 이동/재접속 후에도 유지)
  const fetchGoldenCache = async (cat) => {
    setGoldenError(null);
    try {
      const res = await fetchWithAuth(`/api/content/golden?category=${encodeURIComponent(cat)}`);
      if (res.ok) {
        const data = await res.json();
        setGolden(data.keywords && data.keywords.length > 0 ? data : null);
      }
    } catch (err) {
      // 캐시 복원 실패는 조용히 무시
    }
  };

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
    const cat = selectedCat;
    setLoading(true);
    setError(null);
    try {
      // 1. 백그라운드 수집 작업 시작 (즉시 반환)
      const res = await fetchWithAuth("/api/content/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "수집 시작 실패");

      // 2. 완료될 때까지 상태 폴링 (Gemini 리서치 30~40초+ 소요)
      const POLL_INTERVAL = 2000;
      const MAX_WAIT_MS = 180000; // 3분 안전 한도
      const startedAt = Date.now();

      while (true) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL));

        const sres = await fetchWithAuth(
          `/api/content/refresh/status?category=${encodeURIComponent(cat)}`
        );
        const status = await sres.json();

        if (status.status === "done") {
          alert(`✅ ${status.count}건 수집 완료! 이어서 황금키워드를 자동 분석합니다.`);
          if (status.last_sync) setLastSync(status.last_sync);
          fetchItems(cat);
          // 수집 완료 후 황금키워드 자동 분석 (#자동 진행)
          handleGolden(cat);
          break;
        }
        if (status.status === "error") {
          throw new Error(status.error || "수집 실패");
        }
        if (Date.now() - startedAt > MAX_WAIT_MS) {
          throw new Error("수집 시간이 초과되었습니다. 잠시 후 목록을 새로고침해 주세요.");
        }
        // status.status === "running" | "idle" → 계속 폴링
      }
    } catch (err) {
      setError(err.message);
      alert(`데이터 수집 중 오류가 발생했습니다.${err.message ? `\n(${err.message})` : ""}`);
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

  const handleGolden = async (cat = selectedCat) => {
    setGoldenLoading(true);
    setGoldenError(null);
    setGolden(null);
    try {
      const res = await fetchWithAuth("/api/content/golden", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "분석 실패");
      setGolden(data);
    } catch (err) {
      setGoldenError(err.message);
    } finally {
      setGoldenLoading(false);
    }
  };

  // 키워드와의 관련도 점수로 글감 정렬 (제목/키워드/요약 토큰 겹침)
  const scoredItems = (keyword) => {
    const kwFlat = (keyword || "").replace(/\s/g, "");
    const tokens = (keyword || "").split(/\s+/).filter((t) => t.length > 1);
    return items
      .map((it) => {
        const hay = `${it.title || ""} ${(it.keywords || []).join(" ")} ${it.summary || ""}`.replace(/\s/g, "");
        let score = 0;
        if (kwFlat && hay.includes(kwFlat)) score += 3;
        for (const t of tokens) if (hay.includes(t)) score += 1;
        return { it, score };
      })
      .sort((a, b) => b.score - a.score || (a.it.priority || 99) - (b.it.priority || 99));
  };

  // 정확 매칭된 글감(점수>0) 1건 — 행 표시용
  const matchItem = (keyword) => {
    const top = scoredItems(keyword)[0];
    return top && top.score > 0 ? top.it : null;
  };

  const itemSource = (it) =>
    `[제목] ${it.title || ""}\n[요약] ${it.summary || ""}\n[대상] ${it.target || ""}\n[기간] ${it.deadline || "상시"}\n[출처] ${it.source || ""}\n[링크] ${it.url || ""}`;

  // 추천 키워드를 글쓰기 화면으로 전달.
  // 정확 매칭 글감이 있으면 그 글감을, 없으면 같은 카테고리 수집 글감 상위 N건을 '배경 컨텍스트'로 전달
  // → 매칭 실패에도 작성으로 넘어가되 AI가 수집된 사실을 근거로 작성(환각 위험↓).
  const goWrite = (channel, keyword) => {
    const ranked = scoredItems(keyword);
    const exact = ranked[0] && ranked[0].score > 0 ? ranked[0].it : null;
    let source_data;
    if (exact) {
      source_data = `${itemSource(exact)}\n[추천 황금키워드] ${keyword}`;
    } else {
      const refs = ranked
        .slice(0, 5)
        .map((r, i) => `${i + 1}) ${itemSource(r.it).replace(/\n/g, " ")}`)
        .join("\n");
      source_data =
        `[작성 주제 키워드] ${keyword}\n[카테고리] ${selectedCat}\n\n` +
        `[참고 — '${selectedCat}'에서 수집된 글감]\n${refs}\n\n` +
        `* 위 수집 글감을 사실 근거로 참고하되, 글의 핵심 주제는 '${keyword}'에 맞춰 작성하세요.`;
    }
    const params = new URLSearchParams({
      keyword: keyword,
      prompt_category: "content_collect",
      source_data: source_data,
    });
    window.location.href = `/${channel === "카페" ? "cafe-auto" : "blog-posting"}?${params.toString()}`;
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

      {/* 💎 황금키워드 추천 패널 (상단) */}
      {(goldenLoading || golden || goldenError) && (
        <div className="glass-card" style={{ padding: "2rem", marginBottom: "2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.4rem", color: "#1e293b" }}>
              💎 황금키워드 추천 <span style={{ fontSize: "0.9rem", color: "#94a3b8", fontWeight: "normal" }}>({selectedCat})</span>
            </h2>
            {golden?.seed?.length > 0 && (
              <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
                시드: {golden.seed.join(", ")} · 후보 {golden.candidate_count?.toLocaleString()}개 분석
              </span>
            )}
          </div>

          <p style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "1rem" }}>
            {golden?.is_news
              ? "뉴스는 제목에서 추출한 주제어를 화제성(월검색량) 순으로 정렬합니다. 문서수·황금점수는 참고용입니다."
              : "황금점수 = 월검색량 ÷ 문서수 (검색은 많고 글은 적을수록 높음). 점수가 높은 채널을 추천합니다."}
          </p>

          {goldenLoading ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>검색량·문서수 분석 중... (수 초 소요)</div>
          ) : goldenError ? (
            <div style={{ padding: "1.5rem", textAlign: "center", background: "#fef2f2", color: "#b91c1c", borderRadius: "8px" }}>{goldenError}</div>
          ) : golden?.keywords?.length === 0 ? (
            <div style={{ padding: "1.5rem", textAlign: "center", color: "#64748b" }}>추천할 키워드를 찾지 못했습니다.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ background: "#f8fafc", color: "#475569", textAlign: "left" }}>
                    <th style={{ padding: "0.6rem 0.8rem" }}>#</th>
                    <th style={{ padding: "0.6rem 0.8rem" }}>키워드</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "right" }}>월검색량</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>경쟁도</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "right" }}>블로그 문서</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "right" }}>카페 문서</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>추천 채널</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "right" }}>황금점수</th>
                    <th style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>작성</th>
                  </tr>
                </thead>
                <tbody>
                  {golden?.keywords?.map((k, i) => {
                    const compColor = k.comp === "높음" ? "#ef4444" : k.comp === "중간" ? "#f59e0b" : "#10b981";
                    const chanColor = k.channel === "카페" ? "#f59e0b" : "#3b82f6";
                    const matched = matchItem(k.keyword); // 작성 시 함께 넘어갈 글감
                    return (
                      <tr key={k.keyword} style={{ borderTop: "1px solid #e2e8f0" }}>
                        <td style={{ padding: "0.6rem 0.8rem", color: "#94a3b8" }}>{i + 1}</td>
                        <td style={{ padding: "0.6rem 0.8rem", color: "#1e293b" }}>
                          <div style={{ fontWeight: "bold" }}>{k.keyword}</div>
                          <div
                            title={matched ? matched.title : `정확 매칭 글감이 없어 '${selectedCat}' 수집 글감을 참고자료로 함께 전달합니다.`}
                            style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "0.15rem", maxWidth: "280px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                          >
                            {matched ? `📎 ${matched.title}` : "📎 카테고리 글감 참고"}
                          </div>
                        </td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "right" }}>{k.volume?.toLocaleString()}</td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>
                          <span style={{ color: compColor, fontWeight: "bold" }}>{k.comp || "-"}</span>
                        </td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "right", color: "#64748b" }}>{k.blog_docs == null ? "측정실패" : k.blog_docs.toLocaleString()}</td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "right", color: "#64748b" }}>{k.cafe_docs == null ? "측정실패" : k.cafe_docs.toLocaleString()}</td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>
                          {k.channel ? (
                            <span style={{ background: chanColor, color: "white", padding: "0.15rem 0.6rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: "bold" }}>
                              {k.channel === "카페" ? "☕ 카페" : "📝 블로그"}
                            </span>
                          ) : "-"}
                        </td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "right", fontWeight: "bold", color: "#d97706" }}>
                          {k.gold == null ? "-" : k.gold.toLocaleString()}
                        </td>
                        <td style={{ padding: "0.6rem 0.8rem", textAlign: "center", whiteSpace: "nowrap" }}>
                          <button
                            onClick={() => goWrite("블로그", k.keyword)}
                            title={k.channel === "블로그" ? "추천 채널" : "블로그로 작성"}
                            style={{
                              background: k.channel === "블로그" ? "#3b82f6" : "white",
                              color: k.channel === "블로그" ? "white" : "#3b82f6",
                              border: "1px solid #3b82f6", borderRadius: "6px",
                              padding: "0.35rem 0.6rem", cursor: "pointer", fontSize: "0.78rem", marginRight: "0.35rem"
                            }}
                          >
                            📝 블로그{k.channel === "블로그" ? " ★" : ""}
                          </button>
                          <button
                            onClick={() => goWrite("카페", k.keyword)}
                            title={k.channel === "카페" ? "추천 채널" : "카페로 작성"}
                            style={{
                              background: k.channel === "카페" ? "#f59e0b" : "white",
                              color: k.channel === "카페" ? "white" : "#f59e0b",
                              border: "1px solid #f59e0b", borderRadius: "6px",
                              padding: "0.35rem 0.6rem", cursor: "pointer", fontSize: "0.78rem"
                            }}
                          >
                            ☕ 카페{k.channel === "카페" ? " ★" : ""}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

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

            <button
              onClick={() => handleGolden()}
              style={{
                width: "100%", padding: "1rem", marginTop: "0.75rem",
                display: "flex", justifyContent: "center", gap: "0.5rem",
                background: "linear-gradient(90deg, #f59e0b, #d97706)", color: "white",
                border: "none", borderRadius: "8px", fontWeight: "bold", cursor: "pointer",
                opacity: goldenLoading ? 0.6 : 1
              }}
              disabled={goldenLoading}
              title="수집된 글감을 시드로 검색량↑·문서수↓ 황금키워드를 찾아 블로그/카페 채널을 추천합니다."
            >
              {goldenLoading ? "분석 중..." : "💎 황금키워드 추천"}
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
                              keyword: item.keywords?.[0] || (item.title || "").split(' ')[0],
                              prompt_category: "content_collect",
                              source_data: `[제목] ${item.title}\n[요약] ${item.summary}\n[대상] ${item.target}\n[기간] ${item.deadline}\n[출처] ${item.source}\n[링크] ${item.url}`
                            });
                            window.location.href = `/blog-posting?${params.toString()}`;
                          }}>📝 블로그 작성 준비</button>
                        <button className="btn-primary" style={{ flex: 1, background: "#f59e0b" }} onClick={() => {
                            const params = new URLSearchParams({
                              keyword: item.keywords?.[0] || (item.title || "").split(' ')[0],
                              prompt_category: "content_collect",
                              source_data: `[제목] ${item.title}\n[요약] ${item.summary}\n[대상] ${item.target}\n[기간] ${item.deadline}\n[출처] ${item.source}\n[링크] ${item.url}`
                            });
                            window.location.href = `/cafe-auto?${params.toString()}`;
                          }}>☕ 카페 작성 준비</button>
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