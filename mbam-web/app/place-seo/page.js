"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect, useRef } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function PlaceSeoDashboard() {
  const [keyword, setKeyword] = useState("");
  const [targetMid, setTargetMid] = useState("");
  const [targetName, setTargetName] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [trackedPlaces, setTrackedPlaces] = useState([]);
  
  const [scheduleHour, setScheduleHour] = useState(10);
  const [scheduleMinute, setScheduleMinute] = useState(0);

  const [activeRightTab, setActiveRightTab] = useState("history"); // "history" or "ranking"
  const [compareDays, setCompareDays] = useState(1);
  const abortControllerRef = useRef(null);

  // Fetch tracked places on mount
  useEffect(() => {
    fetchWithAuth("/api/place/tracked")
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setTrackedPlaces(data.tracked || []);
        }
      })
      .catch(err => console.error(err));
      
    // Fetch schedule time
    fetchWithAuth("/api/schedule/time")
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setScheduleHour(data.hour);
          setScheduleMinute(data.minute);
        }
      })
      .catch(err => console.error(err));
  }, []);
  
  const formatN = (val) => {
    if (val === undefined || val === null) return "0.000000";
    return Number(val).toFixed(6);
  };
  
  const renderDeltaValue = (delta, isRank = false) => {
    if (!delta || delta === 0) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "4px"}}>-</span>;
    if (isRank) {
      return delta > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(delta)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(delta)}</span>;
    } else {
      return delta > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(delta)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(delta)}</span>;
    }
  };
  
  const renderDeltaFloatValue = (delta) => {
    if (!delta || Math.abs(delta) < 0.001) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "4px"}}>-</span>;
    return delta > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(delta).toFixed(2)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(delta).toFixed(2)}</span>;
  };

  const handleSaveSchedule = async () => {
    try {
      const res = await fetchWithAuth("/api/schedule/time", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hour: parseInt(scheduleHour),
          minute: parseInt(scheduleMinute)
        })
      });
      const data = await res.json();
      if (data.success) {
        alert(data.message);
      } else {
        alert("시간 저장 실패: " + data.error);
      }
    } catch (err) {
      alert("시간 저장 중 오류 발생");
    }
  };

  const handleTrackPlace = async () => {
    if (!result || !result.places) return;
    const target = result.places.find(p => p.is_target);
    if (!target) {
      alert("분석 결과에 내 매장이 포함되어 있지 않아 저장할 수 없습니다.");
      return;
    }
    try {
      const res = await fetchWithAuth("/api/place/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mid: target.mid,
          keyword: keyword,
          name: target.name
        })
      });
      const data = await res.json();
      if (data.success) {
        alert("관심 매장으로 저장되었습니다! 매일 추이를 확인할 수 있습니다.");
        // refresh list
        fetchWithAuth("/api/place/tracked")
          .then(res => res.json())
          .then(data => setTrackedPlaces(data.tracked || []));
      } else {
        alert("저장 실패: " + data.error);
      }
    } catch (err) {
      alert("저장 중 오류 발생");
    }
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!keyword.trim() || !targetMid.trim()) {
      return alert("키워드와 타겟 MID를 모두 입력해주세요.");
    }
    
    setLoading(true);
    setResult(null);
    abortControllerRef.current = new AbortController();
    
    try {
      // 1. API 호출: 300위 수집 및 분석
      const res = await fetchWithAuth("/api/place/analyze-keyword", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, target_mid: targetMid, compare_days: compareDays }),
        signal: abortControllerRef.current.signal
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "분석 실패");
      
      setResult(data);
      setActiveRightTab("ranking"); // 조회 후에는 순위 탭으로 전환
    } catch (err) {
      if (err.name === 'AbortError') {
        alert("검색이 중지되었습니다.");
      } else {
        alert(err.message);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleCancelSearch = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const fetchMidInfo = async () => {
    if (!targetMid.trim()) return;
    try {
      const res = await fetchWithAuth("/api/place/fetch-mid", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mid: targetMid })
      });
      if (res.ok) {
        const data = await res.json();
        setTargetName(data.name || "");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleTrackedClick = async (tp) => {
    setKeyword(tp.keyword);
    setTargetMid(tp.mid);
    setTargetName(tp.name);
    
    try {
      const res = await fetchWithAuth("/api/place/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: tp.keyword, target_mid: tp.mid })
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        setActiveRightTab("history"); // 내역 클릭 시 히스토리 탭으로 전환
      }
    } catch (err) {
      console.error("히스토리 로드 실패:", err);
    }
  };

  return (
    <main style={{ maxWidth: "1800px", margin: "0 auto", padding: "1.5rem", background: "#f8fafc", height: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ marginBottom: "0.5rem" }}>
        <h1 style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#1e293b", margin: 0 }}>
          플레이스 400위 순위 및 N지수 비교분석
        </h1>
      </header>

      <div style={{ display: "flex", gap: "1rem", flex: 1, minHeight: 0 }}>
        
        {/* 1. Left Sidebar: 분석리스트 */}
        <div style={{ width: "240px", background: "white", border: "1px solid #cbd5e1", display: "flex", flexDirection: "column" }}>
          <h2 style={{ fontSize: "1.3rem", fontWeight: "bold", padding: "1rem", borderBottom: "1px solid #cbd5e1", margin: 0 }}>분석리스트</h2>
          <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem" }}>
            {trackedPlaces.length === 0 ? (
              <div style={{ padding: "1rem", color: "#94a3b8", fontSize: "0.9rem" }}>저장된 즐겨찾기가 없습니다.</div>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {trackedPlaces.map((tp, i) => (
                  <li 
                    key={i} 
                    onClick={() => handleTrackedClick(tp)}
                    style={{ padding: "0.8rem", borderBottom: "1px solid #e2e8f0", cursor: "pointer", fontSize: "0.9rem", color: "#334155", background: "#f8fafc", marginBottom: "0.5rem" }}
                  >
                    <div style={{ fontWeight: "bold", color: "#1e293b" }}>{tp.name || "이름없음"}</div>
                    <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.2rem" }}>{tp.keyword}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right Main Area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "1rem", minWidth: 0 }}>
          
          {/* 2. Top: 플레이스 순위 리스트 (Form) */}
          <div style={{ background: "white", border: "1px solid #cbd5e1", padding: "1.5rem" }}>
            <h2 style={{ fontSize: "1.3rem", fontWeight: "bold", marginBottom: "1rem", margin: 0 }}>플레이스 순위 리스트</h2>
            <form onSubmit={handleAnalyze} style={{ display: "flex", alignItems: "flex-end", flexWrap: "wrap", gap: "1rem" }}>
              <div style={{ flex: "1 1 250px", minWidth: "250px" }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: "0.5rem" }}>
                  <label style={{ width: "80px", fontSize: "0.9rem", fontWeight: "bold" }}>MID</label>
                  <input type="text" value={targetMid} onChange={e => setTargetMid(e.target.value)} onBlur={fetchMidInfo} style={{ flex: 1, padding: "0.5rem", border: "1px solid #cbd5e1" }} />
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <label style={{ width: "80px", fontSize: "0.9rem", fontWeight: "bold" }}>업체명</label>
                  <input type="text" value={targetName} onChange={e => setTargetName(e.target.value)} style={{ flex: 1, padding: "0.5rem", border: "1px solid #cbd5e1" }} />
                </div>
              </div>
              <div style={{ flex: "1 1 250px", minWidth: "250px" }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: "0.5rem", height: "34px", display: "none" }}>
                  {/* Empty placeholder to align with MID */}
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <label style={{ width: "80px", fontSize: "0.9rem", fontWeight: "bold" }}>검색키워드</label>
                  <input type="text" value={keyword} onChange={e => setKeyword(e.target.value)} style={{ flex: 1, padding: "0.5rem", border: "1px solid #cbd5e1" }} />
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button type="submit" disabled={loading} style={{ padding: "0.5rem 2rem", height: "35px", background: "#f8fafc", color: "#0f172a", fontWeight: "bold", border: "1px solid #cbd5e1", cursor: loading ? "wait" : "pointer", borderRadius: "4px" }}>
                  {loading ? "조회중..." : "조회"}
                </button>
                {loading && (
                  <button type="button" onClick={handleCancelSearch} style={{ padding: "0.5rem 1rem", height: "35px", background: "#ef4444", color: "white", fontWeight: "bold", border: "none", cursor: "pointer", borderRadius: "4px" }}>
                    중지
                  </button>
                )}
                {result && result.places && result.places.length > 0 && (
                  <button type="button" onClick={handleTrackPlace} style={{ padding: "0.5rem 1rem", height: "35px", background: "#0f172a", color: "white", fontWeight: "bold", border: "none", cursor: "pointer" }}>
                    저장
                  </button>
                )}
                
                <div style={{ display: "flex", alignItems: "center", marginLeft: "1rem", gap: "0.5rem", borderLeft: "1px solid #e2e8f0", paddingLeft: "1rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#10b981", background: "#ecfdf5", padding: "0.3rem 0.8rem", borderRadius: "12px", border: "1px solid #a7f3d0" }}>
                    ✨ 매일 새벽 5시 자동 일괄 최신화 적용 중
                  </span>
                </div>
              </div>
            </form>
          </div>
          
          {/* AI 1위 역산 컨설팅 리포트 (N1~N4 기반) */}
          {result && result.report && (
            <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", padding: "1.5rem", borderRadius: "8px", position: "relative" }}>
              <div style={{ position: "absolute", top: "-12px", left: "20px", background: "#3b82f6", color: "white", padding: "2px 10px", fontSize: "0.8rem", fontWeight: "bold", borderRadius: "12px" }}>AI 컨설팅 (N1~N4 Model)</div>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.95rem", color: "#1e3a8a", lineHeight: "1.6" }}>
                {result.report}
              </pre>
            </div>
          )}

          {/* Bottom Split */}
          <div style={{ flex: 1, display: "flex", flexWrap: "wrap", gap: "1rem", minHeight: 0 }}>
            

            {/* 4. Bottom Right: 탭 영역 (히스토리 & 전체순위) */}
            <div style={{ flex: "3 1 500px", minWidth: 0, background: "white", border: "1px solid #cbd5e1", display: "flex", flexDirection: "column" }}>
              <div style={{ background: "#f8fafc", padding: "0", borderBottom: "1px solid #cbd5e1", display: "flex", alignItems: "center", flexWrap: "wrap" }}>
                <button 
                  onClick={() => setActiveRightTab("history")} 
                  style={{ padding: "1rem 1.5rem", background: activeRightTab === "history" ? "white" : "transparent", border: "none", borderBottom: activeRightTab === "history" ? "2px solid #3b82f6" : "2px solid transparent", fontWeight: activeRightTab === "history" ? "bold" : "normal", color: activeRightTab === "history" ? "#1e293b" : "#64748b", cursor: "pointer", fontSize: "1rem", outline: "none" }}>
                  일자별 히스토리 상세 내역
                </button>
                <button 
                  onClick={() => setActiveRightTab("ranking")} 
                  style={{ padding: "1rem 1.5rem", background: activeRightTab === "ranking" ? "white" : "transparent", border: "none", borderBottom: activeRightTab === "ranking" ? "2px solid #3b82f6" : "2px solid transparent", fontWeight: activeRightTab === "ranking" ? "bold" : "normal", color: activeRightTab === "ranking" ? "#1e293b" : "#64748b", cursor: "pointer", fontSize: "1rem", outline: "none" }}>
                  전체순위
                </button>

                {/* 증감비교 필터 영역 */}
                <div style={{ display: "flex", alignItems: "center", marginLeft: "1rem", gap: "0.2rem" }}>
                  <span style={{ fontSize: "0.85rem", color: "#64748b", marginRight: "0.5rem" }}>증감비교:</span>
                  {[1, 5, 7, 10, 14, 20, 30, 60].map(days => (
                    <button
                      key={days}
                      onClick={() => setCompareDays(days)}
                      style={{
                        padding: "0.3rem 0.6rem",
                        fontSize: "0.85rem",
                        background: compareDays === days ? "#3b82f6" : "white",
                        color: compareDays === days ? "white" : "#475569",
                        border: "1px solid #cbd5e1",
                        borderRadius: "4px",
                        cursor: "pointer",
                        fontWeight: compareDays === days ? "bold" : "normal"
                      }}
                    >
                      {days}일전
                    </button>
                  ))}
                </div>

                {activeRightTab === "history" && <span style={{ marginLeft: "auto", paddingRight: "1.5rem", fontSize: "0.85rem", color: "#64748b" }}>실시간 400위 경쟁사 비교는 상단의 [조회]를 눌러주세요.</span>}
                {activeRightTab === "ranking" && result && result.places && result.places.length > 0 && <span style={{ marginLeft: "auto", paddingRight: "1.5rem", fontSize: "0.85rem", color: "#3b82f6", fontWeight: "bold" }}>Top {result.places.length} 순위</span>}
              </div>
              
              <div style={{ flex: 1, overflow: "auto" }}>
                {activeRightTab === "history" ? (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "center", whiteSpace: "nowrap" }}>
                    <thead style={{ position: "sticky", top: 0, background: "#f1f5f9", zIndex: 10, borderBottom: "2px solid #cbd5e1" }}>
                      <tr>
                        <th style={{ padding: "0.8rem 0.4rem" }}>조회 일자</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#3b82f6" }}>플레이스 순위</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#10b981" }}>저장수</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#f59e0b" }}>방문자리뷰</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#8b5cf6" }}>블로그리뷰</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#3b82f6" }}>N1(검증)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#10b981" }}>N2(내부)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#8b5cf6" }}>N3(외부)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#ef4444" }}>N4(필터)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#1e3a8a", fontWeight: "900" }}>N5(총점)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!result || !result.history || result.history.length === 0 ? (
                        <tr>
                          <td colSpan="8" style={{ padding: "4rem", color: "#94a3b8" }}>히스토리 기록이 없습니다.</td>
                        </tr>
                      ) : (
                        [...result.history].reverse().map((h, idx, arr) => {
                          const prev = arr[idx + 1];
                          const renderDelta = (current, prevVal, isRank = false) => {
                            if (prevVal === undefined || prevVal === null) return null;
                            const diff = current - prevVal;
                            if (diff === 0) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "6px"}}>-</span>;
                            if (isRank) {
                              return diff < 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "6px"}}>▲{Math.abs(diff)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "6px"}}>▼{Math.abs(diff)}</span>;
                            } else {
                              return diff > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "6px"}}>▲{Math.abs(diff)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "6px"}}>▼{Math.abs(diff)}</span>;
                            }
                          };
                          const formatSaves = (saves) => {
                            if (saves === undefined || saves === null) return "0";
                            if (saves >= 10000) return (Math.floor(saves / 10000)) + "만+";
                            if (saves >= 1000) return (Math.floor(saves / 1000)) + ",000+";
                            return saves.toLocaleString();
                          };
                          const renderDeltaFloat = (current, prevVal) => {
                            if (prevVal === undefined || prevVal === null) return null;
                            const diff = current - prevVal;
                            if (Math.abs(diff) < 0.001) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "6px"}}>-</span>;
                            return diff > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "6px"}}>▲{Math.abs(diff).toFixed(2)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "6px"}}>▼{Math.abs(diff).toFixed(2)}</span>;
                          };

                          return (
                          <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0", transition: "background 0.2s" }} onMouseEnter={(e)=>e.currentTarget.style.background="#f8fafc"} onMouseLeave={(e)=>e.currentTarget.style.background="white"}>
                            <td style={{ padding: "0.8rem 1rem", fontWeight: "bold", color: "#475569" }}>{h.date}</td>
                            <td style={{ padding: "0.8rem 1rem", fontWeight: "bold", color: "#1e293b" }}>{h.rank}위 {renderDelta(h.rank, prev?.rank, true)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#64748b" }}>{formatSaves(h.saves)} {renderDelta(h.saves, prev?.saves)}</td>
                            <td style={{ padding: "0.8rem 1rem", color: "#64748b" }}>{h.visitor_reviews.toLocaleString()}건 {renderDelta(h.visitor_reviews, prev?.visitor_reviews)}</td>
                            <td style={{ padding: "0.8rem 1rem", color: "#64748b" }}>{h.blog_reviews.toLocaleString()}건 {renderDelta(h.blog_reviews, prev?.blog_reviews)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#64748b" }}>{formatN(h.n1)} {renderDeltaFloat(h.n1, prev?.n1)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#64748b" }}>{formatN(h.n2)} {renderDeltaFloat(h.n2, prev?.n2)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#64748b" }}>{formatN(h.n3)} {renderDeltaFloat(h.n3, prev?.n3)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: h.n4 < 0.90 ? "#ef4444" : (h.n4 < 1.0 ? "#f59e0b" : "#64748b"), fontWeight: h.n4 < 1.0 ? "bold" : "normal" }}>
                              {formatN(h.n4 !== undefined ? h.n4 : 1.0)} {h.n4 < 0.90 && "🚨"}
                            </td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#1e3a8a", fontWeight: "900" }}>
                              {formatN(h.n5 !== undefined ? h.n5 : 0)}
                            </td>
                          </tr>
                        )})
                      )}
                    </tbody>
                  </table>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "center", whiteSpace: "nowrap" }}>
                    <thead style={{ position: "sticky", top: 0, background: "#f1f5f9", zIndex: 10, borderBottom: "2px solid #cbd5e1" }}>
                      <tr>
                        <th style={{ padding: "0.8rem 0.5rem", width: "40px" }}>비교</th>
                        <th style={{ padding: "0.8rem 0.5rem", width: "50px" }}>전국 순위</th>
                        <th style={{ padding: "0.8rem 0.5rem", width: "50px", color: "#3b82f6" }}>로컬 순위</th>
                        <th style={{ padding: "0.8rem 1rem", textAlign: "left" }}>업체명/카테고리</th>
                        <th style={{ padding: "0.8rem 0.5rem" }}>방문자리뷰</th>
                        <th style={{ padding: "0.8rem 0.5rem" }}>블로그리뷰</th>
                        <th style={{ padding: "0.8rem 0.5rem" }}>저장수</th>
                        <th style={{ padding: "0.8rem 0.2rem", color: "#3b82f6" }}>N1(검증)</th>
                        <th style={{ padding: "0.8rem 0.2rem", color: "#10b981" }}>N2(내부)</th>
                        <th style={{ padding: "0.8rem 0.2rem", color: "#8b5cf6" }}>N3(외부)</th>
                        <th style={{ padding: "0.8rem 0.2rem", color: "#ef4444" }}>N4(필터)</th>
                        <th style={{ padding: "0.8rem 0.2rem", color: "#1e3a8a", fontWeight: "900" }}>N5(총점)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!result && !loading && (
                        <tr>
                          <td colSpan="10" style={{ padding: "4rem", color: "#94a3b8" }}>상단 폼에서 조회 조건을 입력해주세요.</td>
                        </tr>
                      )}
                      {loading && (
                        <tr>
                          <td colSpan="10" style={{ padding: "4rem", color: "#3b82f6", fontWeight: "bold" }}>네이버 플레이스 400위 듀얼 크롤링(전국/로컬)을 동시 진행하고 있습니다... (40~60초)</td>
                        </tr>
                      )}
                      {result && result.places && result.places.length === 0 && !loading && (
                        <tr>
                          <td colSpan="10" style={{ padding: "4rem", color: "#94a3b8" }}>전체 순위 데이터가 없습니다. 상단의 [조회] 버튼을 눌러 새롭게 수집해주세요.</td>
                        </tr>
                      )}
                      {result && result.places && result.places.map((place) => {
                        const isTarget = place.is_target;
                        const formatSaves = (saves) => {
                          if (saves === undefined || saves === null) return "0";
                          if (saves >= 10000) return (Math.floor(saves / 10000)) + "만+";
                          if (saves >= 1000) return (Math.floor(saves / 1000)) + ",000+";
                          return saves.toLocaleString();
                        };
                        return (
                          <tr key={place.mid} style={{ borderBottom: "1px solid #e2e8f0", background: isTarget ? "#eff6ff" : "white", fontWeight: isTarget ? "bold" : "normal" }}>
                            <td style={{ padding: "0.8rem 0.5rem" }}><input type="checkbox" /></td>
                            <td style={{ padding: "0.8rem 0.5rem", color: isTarget ? "white" : "#475569", background: isTarget ? "#1e293b" : "#f1f5f9" }}>
                              {isTarget ? <span style={{ background: "#3b82f6", padding: "0.2rem 0.6rem", borderRadius: "4px", fontWeight: "bold" }}>{place.rank}</span> : place.rank}
                              {place.delta_rank !== undefined && renderDeltaValue(place.delta_rank, true)}
                            </td>
                            <td style={{ padding: "0.8rem 0.5rem", color: isTarget ? "white" : "#3b82f6", fontWeight: "bold", background: isTarget ? "#1e293b" : "#eff6ff" }}>
                              {isTarget ? <span style={{ background: "#ef4444", padding: "0.2rem 0.6rem", borderRadius: "4px", fontWeight: "bold" }}>{place.local_rank || "-"}</span> : (place.local_rank || "-")}
                            </td>
                            <td style={{ padding: "0.8rem 1rem", textAlign: "left" }}>
                              <div style={{ color: isTarget ? "#1e40af" : "#1e293b", fontSize: "0.95rem" }}>
                                {place.name}
                                {place.is_new && <span style={{ marginLeft: "6px", background: "#ef4444", color: "white", padding: "0.1rem 0.4rem", borderRadius: "12px", fontSize: "0.7rem", fontWeight: "bold" }}>새로오픈</span>}
                                {place.has_revisit && <span style={{ marginLeft: "6px", background: "#ff6b6b", color: "white", padding: "0.1rem 0.4rem", borderRadius: "12px", fontSize: "0.7rem", fontWeight: "bold" }}>재방문 많은</span>}
                              </div>
                              <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: "0.2rem" }}>{place.category}</div>
                            </td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#64748b" }}>{place.visitor_reviews.toLocaleString()} {place.delta_visitor_reviews !== undefined && renderDeltaValue(place.delta_visitor_reviews)}</td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#64748b" }}>{place.blog_reviews.toLocaleString()} {place.delta_blog_reviews !== undefined && renderDeltaValue(place.delta_blog_reviews)}</td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#1e293b" }}>{formatSaves(place.saves)} {place.delta_saves !== undefined && renderDeltaValue(place.delta_saves)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#64748b" }}>{formatN(place.n1)} {place.delta_n1 !== undefined && renderDeltaFloatValue(place.delta_n1)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#64748b" }}>{formatN(place.n2)} {place.delta_n2 !== undefined && renderDeltaFloatValue(place.delta_n2)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#64748b" }}>{formatN(place.n3)} {place.delta_n3 !== undefined && renderDeltaFloatValue(place.delta_n3)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: (place.n4 !== undefined && place.n4 < 0.90) ? "#ef4444" : ((place.n4 !== undefined && place.n4 < 1.0) ? "#f59e0b" : "#64748b"), fontWeight: (place.n4 !== undefined && place.n4 < 1.0) ? "bold" : "normal" }}>
                              {formatN(place.n4 !== undefined ? place.n4 : 1.0)} {(place.n4 !== undefined && place.n4 < 0.90) && "🚨"}
                            </td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#1e3a8a", fontWeight: "900", background: "#f8fafc" }}>
                              {formatN(place.n5 !== undefined ? place.n5 : 0)} {place.delta_n5 !== undefined && renderDeltaFloatValue(place.delta_n5)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}