"use client";
import { fetchWithAuth } from "../../utils/api";
import { usePersistentState } from "../../utils/persistentState";
import { addHistory } from "../../utils/workHistory";
import WorkHistory from "../../components/WorkHistory";
import { useState, useEffect, useRef } from "react";
import { Search, Loader2, Star, ShoppingCart, Heart, Activity, Target, ShieldCheck, Trophy, Info, Zap, Trash2 } from 'lucide-react';

export default function ShoppingRankDashboard() {
  const handleRestore = (entry) => {
    const p = (entry && entry.payload) || {};
    if (p.keyword !== undefined) setKeyword(p.keyword);
    if (p.targetMid !== undefined) setTargetMid(p.targetMid);
    if (p.targetName !== undefined) setTargetName(p.targetName);
    if (p.result) { setResult(p.result); setActiveRightTab("ranking"); }
    try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) {}
  };
  const [keyword, setKeyword] = usePersistentState("shopping-rank:keyword", "");
  const [targetMid, setTargetMid] = usePersistentState("shopping-rank:targetMid", "");
  const [targetName, setTargetName] = usePersistentState("shopping-rank:targetName", "");

  const [loading, setLoading] = usePersistentState("shopping-rank:loading", false);
  const [result, setResult] = usePersistentState("shopping-rank:result", null);
  const [trackedPlaces, setTrackedPlaces] = useState([]);
  
  const [selectedPlaces, setSelectedPlaces] = useState([]);
  const [isBatchUpdating, setIsBatchUpdating] = useState(false);
  const [selectedTrackedItem, setSelectedTrackedItem] = useState(null);
  const [compareDays, setCompareDays] = useState(1);
  
  const handleDeleteTracked = async (e, tp) => {
    e.stopPropagation();
    if (!confirm(`'${tp.name}' 항목을 관심상품에서 삭제하시겠습니까?`)) return;
    
    try {
      const res = await fetchWithAuth(`/api/shopping/tracked/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mid: tp.mid, keyword: tp.keyword })
      });
      if (res.ok) {
        setTrackedPlaces(prev => prev.filter(item => !(item.mid === tp.mid && item.keyword === tp.keyword)));
        alert("삭제되었습니다.");
      } else {
        const data = await res.json();
        alert(data.detail || "삭제 실패");
      }
    } catch (err) {
      console.error("삭제 오류:", err);
      alert("삭제 중 오류가 발생했습니다.");
    }
  };

  const [activeRightTab, setActiveRightTab] = useState("ranking"); // "history" or "ranking"
  // 검색→상품 클릭 유입 부스트
  const [boostClicks, setBoostClicks] = useState(5);
  const [boostInterval, setBoostInterval] = useState(10);
  const [boostTethering, setBoostTethering] = useState(false);
  const [boostTaskId, setBoostTaskId] = useState(null);
  const [boostStatus, setBoostStatus] = useState("");
  const [boostLogs, setBoostLogs] = useState([]);
  const abortControllerRef = useRef(null);

  // Fetch tracked shopping items on mount
  useEffect(() => {
    fetchWithAuth("/api/shopping/tracked")
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setTrackedPlaces(data.tracked || []);
        }
      })
      .catch(err => console.error(err));
  }, []);
  
  const formatN = (val) => {
    if (val === undefined || val === null) return "0.00";
    return Number(val).toFixed(2);
  };
  
  const renderDeltaValue = (delta, isRank = false) => {
    if (!delta || delta === 0) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "4px"}}>-</span>;
    if (isRank) {
      return delta > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(delta)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(delta)}</span>;
    } else {
      return delta > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(delta)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(delta)}</span>;
    }
  };

  const handleTrackPlace = async () => {
    if (!result || !result.places) return;
    const target = result.places.find(p => p.is_target);
    if (!target) {
      alert("분석 결과에 내 상품이 포함되어 있지 않아 저장할 수 없습니다.");
      return;
    }
    try {
      const res = await fetchWithAuth("/api/shopping/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mid: target.mid || targetMid,
          keyword: keyword,
          name: target.title || targetName,
          places: result && result.places ? result.places : null,
          report: result && result.report ? result.report : null,
          target_stats: target
        })
      });
      const data = await res.json();
      if (data.success) {
        alert("관심 상품으로 저장되었습니다! 매일 순위 추이를 확인할 수 있습니다.");
        fetchWithAuth("/api/shopping/tracked")
          .then(res => res.json())
          .then(data => setTrackedPlaces(data.tracked || []));
      } else {
        alert("저장 실패: " + data.error);
      }
    } catch (err) {
      alert("저장 중 오류 발생");
    }
  };

  const handleBatchSaveSelected = async (targetMids, newResult) => {
    const currentResult = newResult || result;
    if (!currentResult || !currentResult.places) return;
    const isEvent = targetMids && targetMids.target;
    const midsToSave = (targetMids && Array.isArray(targetMids)) ? targetMids : selectedPlaces;
    if (!midsToSave || midsToSave.length === 0) return;

    setIsBatchUpdating(true);
    try {
      const itemsToSave = midsToSave
        .map((mid) => {
          const p = currentResult.places.find((x) => x.mid === mid);
          if (!p) return null;

          return {
            mid: p.mid,
            keyword: keyword,
            name: (p.mall_name ? "[" + p.mall_name + "] " : "") + (p.title || "이름없음"),
            places: null,
            report: null,
            target_stats: {
              rank: p.rank,
              title: (p.mall_name ? `[${p.mall_name}] ` : "") + p.title,
              mall_name: p.mall_name,
              price: p.price,
              reviews: p.reviews,
              purchases: p.purchases,
              keeps: p.keeps,
              is_ad: p.isAd || p.is_ad || p.ad || false,
            },
          };
        })
        .filter(Boolean);

      if (itemsToSave.length === 0) {
        setIsBatchUpdating(false);
        return;
      }

      const res = await fetchWithAuth("/api/shopping/track/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: itemsToSave }),
      });
      
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`${itemsToSave.length}개 상품이 관심상품으로 저장되었습니다!`);
        setSelectedPlaces([]);
        fetchWithAuth("/api/shopping/tracked")
          .then((r) => r.json())
          .then((data) => setTrackedPlaces(data.tracked || []));
      } else {
        alert("저장 실패: " + data.error);
      }
    } catch (err) {
      alert("다중 저장 중 오류 발생");
    } finally {
      setIsBatchUpdating(false);
    }
  };

  // 부스트 상태 폴링
  useEffect(() => {
    if (!boostTaskId || boostStatus === "completed" || boostStatus === "failed") return;
    const iv = setInterval(async () => {
      try {
        const res = await fetchWithAuth(`/api/shopping/boost/status/${boostTaskId}`);
        if (res.ok) { const d = await res.json(); setBoostLogs(d.logs || []); setBoostStatus(d.status); }
      } catch (e) {}
    }, 3000);
    return () => clearInterval(iv);
  }, [boostTaskId, boostStatus]);

  const startBoost = async () => {
    if (!keyword.trim()) return alert("검색 키워드를 입력하세요.");
    if (!targetMid.trim() && !targetName.trim()) return alert("내 상품 식별용 스토어명 또는 MID를 입력하세요.");
    if (!window.confirm("⚠️ 유입 보조 도구입니다. 비정상 클릭은 네이버 어뷰징 감지·페널티 위험이 있습니다.\n계속할까요?")) return;
    setBoostLogs([]); setBoostStatus("running"); setBoostTaskId(null);
    try {
      const res = await fetchWithAuth("/api/shopping/boost", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, store_name: targetName, target_mid: targetMid, clicks: Number(boostClicks), interval_min: Number(boostInterval), use_tethering: boostTethering }),
      });
      const d = await res.json();
      if (d.success && d.task_id) setBoostTaskId(d.task_id);
      else alert(d.detail || "시작 실패");
    } catch (e) { alert("서버 오류: " + e.message); }
  };

  const cancelBoost = async () => {
    if (!boostTaskId) return;
    try { await fetchWithAuth(`/api/shopping/boost/cancel/${boostTaskId}`, { method: "POST" }); setBoostStatus("failed"); } catch (e) {}
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!keyword.trim()) {
      return alert("검색 키워드를 입력해주세요.");
    }
    if (!targetMid.trim() && !targetName.trim()) {
      return alert("타겟 식별을 위해 업체명(스토어명)이나 MID 중 하나를 입력해주세요.");
    }
    
    setLoading(true);
    setResult(null);
    abortControllerRef.current = new AbortController();
    
    try {
      if (document.documentElement.getAttribute("data-naver-scraper-ext-installed") === "true") {
        const extPromise = new Promise((resolve, reject) => {
          const msgId = "ext_req_" + Date.now();
          const listener = (e) => {
            if (e.source !== window || !e.data || e.data.type !== "FROM_EXT_TO_PAGE") return;
            if (e.data.id === msgId) {
              window.removeEventListener("message", listener);
              resolve(e.data.response);
            }
          };
          window.addEventListener("message", listener);
          window.postMessage({ type: "FROM_PAGE_TO_EXT", id: msgId, message: { action: "SCRAPE_NAVER_SHOPPING", payload: { keyword: keyword, page: 1 } } }, "*");
          setTimeout(() => { window.removeEventListener("message", listener); reject(new Error("확장 프로그램 수집 응답 시간 초과")); }, 65000);
        });

        const extRes = await extPromise;
        if (!extRes || !extRes.success) throw new Error("확장 프로그램 수집 실패: " + (extRes ? extRes.error : "Unknown Error"));
        const extItems = extRes.data;
        // 수집 진단: 0개이거나 가격/구매/리뷰/찜이 전부 0이면 실제 DOM 구조를 안내(셀렉터 보정용)
        if (extRes.diag && (extRes.diag.count === 0 || extRes.diag.allZeroFields)) {
          console.warn("[MBAM] 쇼핑 수집 진단:", extRes.diag);
          alert("⚠️ 상품 데이터 수집이 비어있습니다(네이버 DOM 변경 가능).\n\n[진단]\n발견 항목 수: " + extRes.diag.count +
                "\n첫 항목 class: " + (extRes.diag.firstClass || "(없음)") +
                "\n첫 항목 텍스트: " + (extRes.diag.firstText || "(없음)").slice(0, 150) +
                "\n\n이 내용을 개발자에게 전달하면 셀렉터를 정확히 맞출 수 있습니다.");
        }

        const res = await fetchWithAuth("/api/shopping/analyze-keyword-ext", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword, target_mid: targetMid, store_name: targetName, items: extItems }),
          signal: abortControllerRef.current.signal
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "분석 실패");
        
        setResult(data);
        setActiveRightTab("ranking");
        addHistory("shopping-rank", { summary: `${keyword}${targetName ? ' · ' + targetName : ''}`, payload: { keyword, targetMid, targetName, result: data } });

        // Auto-save target item to history
        if (data.places) {
          const target = data.places.find(p => p.is_target);
          if (target) {
            handleBatchSaveSelected([target.mid], data);
          }
        }
      } else {
        const res = await fetchWithAuth("/api/shopping/analyze-keyword", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword, target_mid: targetMid, store_name: targetName }),
          signal: abortControllerRef.current.signal
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "분석 실패");
        
        setResult(data);
        setActiveRightTab("ranking");
        addHistory("shopping-rank", { summary: `${keyword}${targetName ? ' · ' + targetName : ''}`, payload: { keyword, targetMid, targetName, result: data } });

        // Auto-save target item to history
        if (data.places) {
          const target = data.places.find(p => p.is_target);
          if (target) {
            handleBatchSaveSelected([target.mid], data);
          }
        }
      }
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

  const handleTrackedClick = async (tp) => {
    setKeyword(tp.keyword);
    setTargetMid(tp.mid);
    setTargetName(tp.name);
    
    try {
      const res = await fetchWithAuth("/api/shopping/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: tp.keyword, target_mid: tp.mid })
      });
      if (res.ok) {
        const data = await res.json();
        setResult(prev => ({
          ...prev,
          found: true,
          history: data.history,
          places: data.places || (prev && prev.places) || [],
          report: data.report || (prev && prev.report) || ""
        }));
        setActiveRightTab("history");
      }
    } catch (err) {
      console.error("히스토리 로드 실패:", err);
    }
  };

  return (
    <main className="rank-shell" style={{ maxWidth: "1800px", margin: "0 auto", padding: "1.5rem", background: "#f8fafc", height: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ marginBottom: "0.5rem" }}>
        <h1 style={{ fontSize: "1.4rem", fontWeight: "bold", color: "#1e293b", margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <ShoppingCart size={24} color="#3b82f6"/> 쇼핑 N지수 하이브리드 분석기 (400위 초정밀 딥서치)
        </h1>
      </header>

      <div className="rank-row" style={{ display: "flex", gap: "1rem", flex: 1, minHeight: 0 }}>

        {/* 1. Left Sidebar: 분석리스트 */}
        <div className="rank-side" style={{ width: "260px", background: "white", border: "1px solid #cbd5e1", display: "flex", flexDirection: "column", borderRadius: "8px", overflow: "hidden" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", padding: "1rem", borderBottom: "1px solid #cbd5e1", margin: 0, background: "#f1f5f9" }}>관심 상품 분석리스트</h2>
          <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem" }}>
            {trackedPlaces.length === 0 ? (
              <div style={{ padding: "1rem", color: "#94a3b8", fontSize: "0.9rem" }}>저장된 관심 상품이 없습니다.</div>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {trackedPlaces.map((tp, i) => (
                  <li 
                    key={i} 
                    onClick={() => handleTrackedClick(tp)}
                    style={{ padding: "0.8rem", borderBottom: "1px solid #e2e8f0", cursor: "pointer", fontSize: "0.9rem", color: "#334155", background: "#f8fafc", marginBottom: "0.5rem", borderRadius: "4px", transition: "all 0.2s" }}
                    onMouseEnter={(e)=>e.currentTarget.style.background="#eff6ff"} 
                    onMouseLeave={(e)=>e.currentTarget.style.background="#f8fafc"}
                  >
                    <div style={{ fontWeight: "bold", color: "#1e293b", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{tp.name || "이름없음"}</div>
                    <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.3rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>키워드: {tp.keyword}</span>
                        <Trash2 
                          size={14} 
                          style={{ color: "#ef4444", cursor: "pointer" }} 
                          onClick={(e) => handleDeleteTracked(e, tp)}
                          title="삭제"
                        />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right Main Area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "1rem", minWidth: 0 }}>
          
          {/* 2. Top: 폼 영역 */}
          <div style={{ background: "white", border: "1px solid #cbd5e1", padding: "1.5rem", borderRadius: "8px" }}>
            <h2 style={{ fontSize: "1.2rem", fontWeight: "bold", marginBottom: "1rem", margin: 0, color: "#334155" }}>타겟 상품 순위 실시간 검색 (최대 400위)</h2>
            <form onSubmit={handleAnalyze} style={{ display: "flex", alignItems: "flex-end", flexWrap: "wrap", gap: "1rem", marginTop: "1rem" }}>
              <div style={{ flex: "1 1 250px", minWidth: "250px" }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: "0.5rem" }}>
                  <label style={{ width: "100px", fontSize: "0.9rem", fontWeight: "bold", color: "#475569" }}>스토어명</label>
                  <input type="text" value={targetName} onChange={e => setTargetName(e.target.value)} placeholder="예: 코스트코핫딜" style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                </div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <label style={{ width: "100px", fontSize: "0.9rem", fontWeight: "bold", color: "#475569" }}>상품명/ID</label>
                  <input type="text" value={targetMid} onChange={e => setTargetMid(e.target.value)} placeholder="상품명 또는 상품ID 입력" style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                </div>
              </div>
              <div style={{ flex: "1 1 250px", minWidth: "250px" }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: "0.5rem", height: "34px", display: "none" }}></div>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <label style={{ width: "80px", fontSize: "0.9rem", fontWeight: "bold", color: "#ef4444" }}>검색키워드</label>
                  <input type="text" value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="예: 씨솔트초콜릿" style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                <button type="submit" disabled={loading} style={{ padding: "0.5rem 2rem", height: "38px", background: "#3b82f6", color: "white", fontWeight: "bold", border: "none", cursor: loading ? "wait" : "pointer", borderRadius: "4px", display: "flex", alignItems: "center", gap: "0.5rem", whiteSpace: "nowrap", flexShrink: 0 }}>
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                  {loading ? "조회중..." : "초고속 조회"}
                </button>
                {loading && (
                  <button type="button" onClick={handleCancelSearch} style={{ padding: "0.5rem 1.5rem", height: "38px", background: "#ef4444", color: "white", fontWeight: "bold", border: "none", cursor: "pointer", borderRadius: "4px" }}>
                    중지
                  </button>
                )}
                {result && result.places && result.places.length > 0 && (
                  <button type="button" onClick={handleTrackPlace} style={{ padding: "0.5rem 1.5rem", height: "38px", background: "#0f172a", color: "white", fontWeight: "bold", border: "none", cursor: "pointer", borderRadius: "4px" }}>
                    관심상품 저장
                  </button>
                )}
                
                <div style={{ display: "flex", alignItems: "center", marginLeft: "1rem", gap: "0.5rem", borderLeft: "1px solid #e2e8f0", paddingLeft: "1rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#10b981", background: "#ecfdf5", padding: "0.4rem 0.8rem", borderRadius: "12px", border: "1px solid #a7f3d0", display: "flex", alignItems: "center", gap: "0.3rem", whiteSpace: "nowrap" }}>
                    <Zap size={14} /> 매일 새벽 5시 자동 순위 업데이트
                  </span>
                </div>
              </div>
            </form>

            {/* 검색→상품 클릭 유입 부스트 */}
            <div style={{ marginTop: "1rem", padding: "1rem", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: "8px" }}>
              <div style={{ fontWeight: "bold", color: "#9a3412", marginBottom: "0.5rem" }}>🔎 검색 → 내 상품 클릭 유입 (부스트)</div>
              <p style={{ margin: "0 0 0.7rem", fontSize: "0.8rem", color: "#b45309" }}>위 <b>키워드 + 스토어명/MID</b>로 검색해 내 상품을 찾아 클릭·체류합니다. ⚠️ 유입 보조용(순위 보장 X), 과도하면 어뷰징 페널티 위험. 프록시/테더링 IP로 분산하세요.</p>
              <div style={{ display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
                <label style={{ fontSize: "0.85rem" }}>클릭 횟수 <input type="number" min="1" value={boostClicks} onChange={e => setBoostClicks(e.target.value)} style={{ width: "60px", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} /></label>
                <label style={{ fontSize: "0.85rem" }}>간격 <input type="number" min="0" value={boostInterval} onChange={e => setBoostInterval(e.target.value)} style={{ width: "60px", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} /> 분</label>
                <label style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.85rem", fontWeight: "bold", color: boostTethering ? "#3b82f6" : "#64748b" }}>
                  <input type="checkbox" checked={boostTethering} onChange={e => setBoostTethering(e.target.checked)} /> 📱 USB 테더링 IP 회전
                </label>
                {boostStatus === "running"
                  ? <button onClick={cancelBoost} style={{ padding: "0.5rem 1rem", background: "#ef4444", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>■ 중지</button>
                  : <button onClick={startBoost} style={{ padding: "0.5rem 1rem", background: "#ea580c", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>🚀 유입 시작</button>}
                {boostStatus && <span style={{ fontSize: "0.85rem", color: boostStatus === "running" ? "#16a34a" : boostStatus === "completed" ? "#2563eb" : "#64748b" }}>{boostStatus === "running" ? "● 진행중" : boostStatus === "completed" ? "✓ 완료" : "중지됨"}</span>}
              </div>
              {boostLogs.length > 0 && (
                <div style={{ marginTop: "0.7rem", maxHeight: "160px", overflowY: "auto", background: "#1e293b", color: "#e2e8f0", padding: "0.7rem", borderRadius: "6px", fontFamily: "monospace", fontSize: "0.8rem" }}>
                  {boostLogs.map((l, i) => <div key={i}>{l}</div>)}
                </div>
              )}
            </div>
          </div>

          {/* AI 컨설팅 리포트 */}
          {result && result.report && (
            <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", padding: "1.5rem", borderRadius: "8px", position: "relative" }}>
              <div style={{ position: "absolute", top: "-12px", left: "20px", background: "#3b82f6", color: "white", padding: "3px 12px", fontSize: "0.85rem", fontWeight: "bold", borderRadius: "12px", display: "flex", alignItems: "center", gap: "0.3rem" }}><Target size={14}/> AI 컨설팅 (N1~N3 Model)</div>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "1rem", color: "#1e3a8a", lineHeight: "1.6", marginTop: "0.5rem" }}>
                {result.report}
              </pre>
            </div>
          )}

          {/* Bottom Split: 탭 영역 */}
          <div style={{ flex: 1, display: "flex", flexWrap: "wrap", gap: "1rem", minHeight: 0 }}>
            <div style={{ flex: "1", minWidth: 0, background: "white", border: "1px solid #cbd5e1", display: "flex", flexDirection: "column", borderRadius: "8px", overflow: "hidden" }}>
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
                <div style={{ display: "flex", alignItems: "center", marginLeft: "1rem", gap: "0.2rem", flexWrap: "wrap" }}>
                  <span style={{ fontSize: "0.85rem", color: "#64748b", marginRight: "0.5rem", whiteSpace: "nowrap" }}>증감비교:</span>
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

                {activeRightTab === "history" && <span style={{ marginLeft: "auto", paddingRight: "1.5rem", fontSize: "0.85rem", color: "#64748b" }}>실시간 경쟁사 비교는 상단의 [초고속 조회]를 눌러주세요.</span>}
                {activeRightTab === "ranking" && result && result.places && result.places.length > 0 && <span style={{ marginLeft: "auto", paddingRight: "1.5rem", fontSize: "0.85rem", color: "#3b82f6", fontWeight: "bold" }}>Top {result.places.length} 순위</span>}
              </div>
              
              <div style={{ flex: 1, overflow: "auto" }}>
                {activeRightTab === "history" ? (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem", textAlign: "center", whiteSpace: "nowrap" }}>
                    <thead style={{ position: "sticky", top: 0, background: "#f1f5f9", zIndex: 10, borderBottom: "2px solid #cbd5e1" }}>
                      <tr>
                        <th style={{ padding: "0.8rem 0.4rem" }}>조회 일자</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#3b82f6" }}>쇼핑 랭킹</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#10b981" }}>구매수</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#f59e0b" }}>리뷰수</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#8b5cf6" }}>찜수</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#3b82f6" }}>N1(적합도)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#10b981" }}>N2(실거래)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#8b5cf6" }}>N3(트래픽)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#ef4444" }}>N4(페널티)</th>
                        <th style={{ padding: "0.8rem 0.4rem", color: "#1e3a8a", fontWeight: "900" }}>총점 (S_shop)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!result || !result.history || result.history.length === 0 ? (
                        <tr>
                          <td colSpan="10" style={{ padding: "4rem", color: "#94a3b8" }}>히스토리 기록이 없습니다.</td>
                        </tr>
                      ) : (
                        [...result.history].map((h, idx, arr) => {
                          const prev = arr[idx + compareDays];
                          const prevWeek = arr[idx + 7];
                          
                          const renderDelta = (current, prevVal, isRank = false) => {
                            if (prevVal === undefined || prevVal === null) return null;
                            const diff = current - prevVal;
                            if (diff === 0) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "4px"}}>-</span>;
                            if (isRank) {
                              return diff < 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(diff)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(diff)}</span>;
                            } else {
                              return diff > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(diff)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(diff)}</span>;
                            }
                          };

                          const renderDeltaFloat = (current, prevVal) => {
                            if (prevVal === undefined || prevVal === null) return null;
                            const diff = current - prevVal;
                            if (Math.abs(diff) < 0.001) return <span style={{color: "#94a3b8", fontSize: "0.75rem", marginLeft: "4px"}}>-</span>;
                            return diff > 0 ? <span style={{color: "#ef4444", fontSize: "0.75rem", marginLeft: "4px"}}>▲{Math.abs(diff).toFixed(2)}</span> : <span style={{color: "#3b82f6", fontSize: "0.75rem", marginLeft: "4px"}}>▼{Math.abs(diff).toFixed(2)}</span>;
                          };

                          return (
                          <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0", transition: "background 0.2s" }} onMouseEnter={(e)=>e.currentTarget.style.background="#f8fafc"} onMouseLeave={(e)=>e.currentTarget.style.background="white"}>
                            <td style={{ padding: "0.8rem 1rem", fontWeight: "bold", color: "#475569" }}>{h.date}</td>
                            <td style={{ padding: "0.8rem 1rem", fontWeight: "bold", color: "#1e293b" }}>
                              {h.rank}위 (P.{Math.ceil(h.rank/40)})
                              {renderDelta(h.rank, prev?.rank, true)}
                            </td>
                            <td style={{ padding: "0.8rem 1rem", color: "#ef4444", fontWeight: "bold" }}>
                              {h.price ? h.price.toLocaleString() + '원' : '-'}
                            </td>
                            <td style={{ padding: "0.8rem 1rem", color: "#10b981", fontWeight: "bold" }}>
                              {(h.purchases || 0).toLocaleString()}
                              <div style={{ fontSize: "0.75rem", marginTop: "2px" }}>
                                <span style={{ color: "#64748b" }}>{compareDays}일:</span> {renderDelta(h.purchases, prev?.purchases) || "-"} 
                                <span style={{ color: "#e2e8f0", margin: "0 4px" }}>|</span> 
                                <span style={{ color: "#64748b" }}>주:</span> {renderDelta(h.purchases, prevWeek?.purchases) || "-"}
                              </div>
                            </td>
                            <td style={{ padding: "0.8rem 1rem", color: "#f59e0b" }}>{(h.visitor_reviews || 0).toLocaleString()} {renderDelta(h.visitor_reviews, prev?.visitor_reviews)}</td>
                            <td style={{ padding: "0.8rem 1rem", color: "#8b5cf6" }}>{(h.saves || 0).toLocaleString()} {renderDelta(h.saves, prev?.saves)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#3b82f6" }}>{formatN(h.n1)} {renderDeltaFloat(h.n1, prev?.n1)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#10b981" }}>{formatN(h.n2)} {renderDeltaFloat(h.n2, prev?.n2)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#8b5cf6" }}>{formatN(h.n3)} {renderDeltaFloat(h.n3, prev?.n3)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: h.n4 < 1.0 ? "#ef4444" : "#64748b" }}>{formatN(h.n4)} {renderDeltaFloat(h.n4, prev?.n4)}</td>
                            <td style={{ padding: "0.8rem 0.3rem", color: "#1e3a8a", fontWeight: "900" }}>{formatN(h.n5)} {renderDeltaFloat(h.n5, prev?.n5)}</td>
                          </tr>
                        )})
                      )}
                    </tbody>
                  </table>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem", textAlign: "center", whiteSpace: "nowrap" }}>
                    <thead
                      style={{
                        position: "sticky",
                        top: 0,
                        background: "#f1f5f9",
                        zIndex: 10,
                        borderBottom: "2px solid #cbd5e1",
                      }}
                    >
                      <tr>
                        <th style={{ padding: "0.8rem 0.5rem", width: "40px" }}>
                          <input
                            type="checkbox"
                            checked={
                              result?.places?.length > 0 &&
                              selectedPlaces.length === result.places.length
                            }
                            onChange={(e) => {
                              if (e.target.checked && result?.places) {
                                setSelectedPlaces(
                                  result.places.map((p) => p.mid),
                                );
                              } else {
                                setSelectedPlaces([]);
                              }
                            }}
                          />
                        </th>
                        <th style={{ padding: "0.8rem 0.5rem", width: "50px" }}>
                          순위
                        </th>
                        <th
                          style={{ padding: "0.8rem 1rem", textAlign: "left" }}
                        >
                          상품명/스토어명
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.5rem", color: "#ef4444" }}
                        >
                          판매가격
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.5rem", color: "#10b981" }}
                        >
                          구매수
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.5rem", color: "#f59e0b" }}
                        >
                          리뷰수
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.5rem", color: "#8b5cf6" }}
                        >
                          찜수
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.2rem", color: "#3b82f6" }}
                        >
                          N1(적합)
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.2rem", color: "#10b981" }}
                        >
                          N2(실거래)
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.2rem", color: "#8b5cf6" }}
                        >
                          N3(트래픽)
                        </th>
                        <th
                          style={{ padding: "0.8rem 0.2rem", color: "#ef4444" }}
                        >
                          N4(페널티)
                        </th>
                        <th
                          style={{
                            padding: "0.8rem 0.2rem",
                            color: "#1e3a8a",
                            fontWeight: "900",
                          }}
                        >
                          총점
                        </th>
                        <th style={{ padding: "0.8rem 0.5rem" }}>액션</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!result && !loading && (
                        <tr>
                          <td colSpan="13" style={{ padding: "4rem", color: "#94a3b8" }}>상단 폼에서 조회 조건을 입력해주세요.</td>
                        </tr>
                      )}
                      {loading && (
                        <tr>
                          <td colSpan="13" style={{ padding: "4rem", color: "#3b82f6", fontWeight: "bold" }}>네이버 쇼핑 400위 데이터를 수집하고 N지수를 수학적으로 연산하고 있습니다... (15~30초)</td>
                        </tr>
                      )}
                      {result && result.found === false && !loading && (
                        <tr>
                          <td colSpan="13" style={{ padding: "4rem", color: "#ef4444", fontWeight: "bold" }}>
                            {result.message || "조회된 순위 데이터가 없습니다."}
                          </td>
                        </tr>
                      )}
                      {result && result.found !== false && (!result.places || result.places.length === 0) && !loading && (
                        <tr>
                          <td colSpan="13" style={{ padding: "4rem", color: "#94a3b8" }}>조회된 순위 데이터가 없습니다.</td>
                        </tr>
                      )}
                      {result && result.places && result.places.map((place, idx) => {
                        const isTarget = place.is_target;
                        return (
                          <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0", background: isTarget ? "#eff6ff" : "white", fontWeight: isTarget ? "bold" : "normal" }}>
                            <td style={{ padding: "0.8rem 0.5rem" }}>
                              <input
                                type="checkbox"
                                checked={selectedPlaces.includes(place.mid)}
                                onChange={(e) => {
                                  if (e.target.checked)
                                    setSelectedPlaces([
                                      ...selectedPlaces,
                                      place.mid,
                                    ]);
                                  else
                                    setSelectedPlaces(
                                      selectedPlaces.filter(
                                        (m) => m !== place.mid,
                                      ),
                                    );
                                }}
                              />
                            </td>
                            <td style={{ padding: "0.8rem 0.5rem", color: isTarget ? "white" : "#475569" }}>
                              {isTarget ? <span style={{ background: "#3b82f6", padding: "0.2rem 0.6rem", borderRadius: "4px", fontWeight: "bold" }}>{place.rank}</span> : place.rank}
                            </td>
                            <td style={{ padding: "0.8rem 1rem", textAlign: "left", maxWidth: "300px", overflow: "hidden", textOverflow: "ellipsis" }}>
                              <div style={{ color: isTarget ? "#1e40af" : "#1e293b", fontSize: "0.95rem" }}>
                                {(place.isAd || place.is_ad || place.ad) && (
                                  <span
                                    style={{
                                      marginRight: "6px",
                                      background: "#fecaca",
                                      color: "#ef4444",
                                      border: "1px solid #f87171",
                                      padding: "0.1rem 0.3rem",
                                      borderRadius: "4px",
                                      fontSize: "0.7rem",
                                      fontWeight: "bold",
                                    }}
                                  >
                                    광고
                                  </span>
                                )}
                                {place.title}
                                {place.is_new && <span style={{ marginLeft: "6px", background: "#ef4444", color: "white", padding: "0.1rem 0.4rem", borderRadius: "12px", fontSize: "0.7rem", fontWeight: "bold" }}>새로오픈</span>}
                              </div>
                              {place.storeName && (
                                <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "4px" }}>
                                  🏢 {place.storeName}
                                </div>
                              )}
                              {(place.is_compare || place.reg_date) && (
                                <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "2px" }}>
                                  {place.is_compare && <span style={{ color: "#7c3aed", fontWeight: "bold" }}>📊 가격비교</span>}
                                  {place.is_compare && place.reg_date && " · "}
                                  {place.reg_date && `등록일 ${place.reg_date}`}
                                </div>
                              )}
                            </td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#0f766e", fontWeight: "bold" }}>{place.price ? place.price.toLocaleString() + "원" + (place.is_compare ? " 최저" : "") : "-"}</td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#10b981", fontWeight: "bold" }}>{(place.purchases || 0).toLocaleString()}</td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#f59e0b" }}>{(place.reviews || 0).toLocaleString()}</td>
                            <td style={{ padding: "0.8rem 0.5rem", color: "#8b5cf6" }}>{(place.keeps || 0).toLocaleString()}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#3b82f6" }}>{formatN(place.n1)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#10b981" }}>{formatN(place.n2)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#8b5cf6" }}>{formatN(place.n3)}</td>
                            <td style={{ padding: "0.8rem 0.2rem", color: (place.n4 < 1.0) ? "#ef4444" : "#64748b" }}>
                              {formatN(place.n4)} {(place.n4 < 1.0) && "🚨"}
                            </td>
                            <td style={{ padding: "0.8rem 0.2rem", color: "#1e3a8a", fontWeight: "900", background: "#f8fafc" }}>
                              {formatN(place.n5)}
                            </td>
                            <td style={{ padding: "0.8rem 0.5rem" }}>
                              {selectedPlaces.includes(place.mid) && (
                                <button
                                  onClick={() => handleBatchSaveSelected([place.mid])}
                                  style={{
                                    background: "#3b82f6",
                                    color: "white",
                                    border: "none",
                                    padding: "0.4rem 0.8rem",
                                    borderRadius: "4px",
                                    fontSize: "0.8rem",
                                    cursor: "pointer",
                                    fontWeight: "bold",
                                  }}
                                >
                                  저장
                                </button>
                              )}
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
      <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "0 1rem" }}>
        <WorkHistory menuKey="shopping-rank" onRestore={handleRestore} />
      </div>
    </main>
  );
}
