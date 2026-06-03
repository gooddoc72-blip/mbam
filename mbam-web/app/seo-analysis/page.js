"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect } from "react";
import Skeleton from "../../components/Skeleton";
import SeoResults from "../../components/SeoResults";
import HistorySidebar from "../../components/HistorySidebar";

export default function Home() {
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  
  // 2-Step States
  const [searchPhase, setSearchPhase] = useState("idle"); // 'idle' | 'searching' | 'selecting' | 'analyzing' | 'done'
  const [blockList, setBlockList] = useState([]);
  const [selectedUrls, setSelectedUrls] = useState([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const savedState = sessionStorage.getItem("seoAnalysisState");
    if (savedState) {
      try {
        const parsed = JSON.parse(savedState);
        setKeyword(parsed.keyword || "");
        setData(parsed.data || null);
        setSearchPhase(parsed.searchPhase || "idle");
        setBlockList(parsed.blockList || []);
        setSelectedUrls(parsed.selectedUrls || []);
      } catch (e) {
        console.error("Failed to parse saved state", e);
      }
    }
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (isLoaded) {
      sessionStorage.setItem("seoAnalysisState", JSON.stringify({
        keyword,
        data,
        searchPhase,
        blockList,
        selectedUrls
      }));
    }
  }, [isLoaded, keyword, data, searchPhase, blockList, selectedUrls]);

  const handleSearchList = async (e) => {
    e.preventDefault();
    if (!keyword.trim()) return;

    setSearchPhase("searching");
    setError(null);
    setData(null);
    setBlockList([]);
    setSelectedUrls([]);

    try {
      const res = await fetchWithAuth(`http://localhost:8000/api/seo/search?keyword=${encodeURIComponent(keyword)}`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "리스트 검색에 실패했습니다.");
      }
      const result = await res.json();
      
      // result structure: { keyword, monthly_vol, blocks: [{ block_title, links: [{title, url}] }] }
      setBlockList(result.blocks || []);
      setData({...result, searchData: result}); // store search volume data
      setSearchPhase("selecting");
    } catch (err) {
      setError(err.message);
      setSearchPhase("idle");
    }
  };

  const toggleSelection = (url) => {
    setSelectedUrls(prev => 
      prev.includes(url) ? prev.filter(u => u !== url) : [...prev, url]
    );
  };

  const selectAll = () => {
    const allUrls = [];
    blockList.forEach(b => {
      if (b.links) {
        b.links.forEach(l => allUrls.push(l.url));
      }
    });
    
    if (selectedUrls.length === allUrls.length && allUrls.length > 0) {
      setSelectedUrls([]);
    } else {
      setSelectedUrls(allUrls);
    }
  };

  const handleAnalyzeSelected = async () => {
    if (selectedUrls.length === 0) {
      alert("분석할 포스팅을 하나 이상 선택해주세요.");
      return;
    }

    setSearchPhase("analyzing");
    setError(null);

    try {
      const res = await fetchWithAuth("http://localhost:8000/api/seo/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, target_urls: selectedUrls }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "분석에 실패했습니다.");
      }

      const result = await res.json();
      setData(result);
      setSearchPhase("done");
    } catch (err) {
      setError(err.message);
      setSearchPhase("selecting");
    }
  };

  const handleSelectHistory = (historyItem) => {
    setKeyword(historyItem.keyword);
    setData(historyItem.data);
    setError(null);
    setSearchPhase("done");
  };

  return (
    <main style={{ maxWidth: "1400px", margin: "0 auto", padding: "2rem" }}>
      <header style={{ textAlign: "center", marginBottom: "3rem" }}>
        <h1 className="text-gradient" style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>
          NextGen SEO Analyzer
        </h1>
        <p style={{ color: "var(--text-sub)", fontSize: "1.2rem" }}>
          AI 기반 네이버 블로그 정밀 분석 및 상위 노출 공식 도출
        </p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "300px minmax(0, 1fr)", gap: "2rem" }}>
        <aside>
          <HistorySidebar onSelectHistory={handleSelectHistory} />
        </aside>

        <section>
          
          {/* 우측 메인 영역 */}
          <div className="right-main" style={{ display: "flex", flexDirection: "column", gap: "1rem", minWidth: 0 }}>
            {/* 검색 폼 */}
            <form onSubmit={handleSearchList} style={{ display: "flex", gap: "0.5rem", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: "1rem", marginBottom: "1rem" }}>
              <input
                type="text"
                style={{ flex: 1, padding: "0.75rem", border: "none", borderBottom: "2px solid #3b82f6", fontSize: "1.1rem", outline: "none", background: "transparent" }}
                placeholder="키워드를 입력하세요"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                disabled={searchPhase === "searching" || searchPhase === "analyzing"}
              />
              <button 
                type="submit" 
                style={{ background: "#34d399", color: "white", padding: "0.75rem 1.5rem", borderRadius: "8px", fontWeight: "bold", border: "none", cursor: "pointer", whiteSpace: "nowrap" }}
                disabled={searchPhase === "searching" || searchPhase === "analyzing" || !keyword.trim()}
              >
                {searchPhase === "searching" ? "검색 중..." : "🔍 스마트블록 리스트 검색"}
              </button>
            </form>
            
            {error && (
              <div className="glass-card" style={{ borderLeft: "4px solid #ef4444", padding: "1rem" }}>
                <p style={{ margin: 0, color: "#ef4444" }}>{error}</p>
              </div>
            )}
            
            {(searchPhase === "searching" || searchPhase === "analyzing") && <Skeleton />}
            
            {/* 키워드 분석 카드 */}
            {searchPhase === "selecting" && data && (
              <div className="glass-card" style={{ padding: "1.5rem", marginBottom: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                  <h3 style={{ fontSize: "1.2rem", margin: 0 }}>키워드 분석</h3>
                  <span style={{ cursor: "pointer", color: "#3b82f6" }}>↻</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <span style={{ fontSize: "1rem", fontWeight: "bold" }}>인공지능 분석</span>
                  <button className="btn-primary" style={{ padding: "0.4rem 1.5rem" }}>분석시작</button>
                </div>
                
                                <div style={{ marginBottom: "1.5rem" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                    {data?.related_keywords && data.related_keywords.map((rk, i) => (
                      <div key={i} style={{ background: "white", border: "1px solid #e2e8f0", padding: "0.8rem 1rem", borderRadius: "8px", fontSize: "0.95rem", display: "flex", flexDirection: "column", gap: "0.3rem", minWidth: "180px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ fontWeight: "bold", color: "#1e293b" }}>{rk.keyword}</span>
                          <span style={{ fontSize: "0.75rem", color: rk.type === '함께찾는' ? '#10b981' : '#cbd5e1', fontWeight: "bold" }}>{rk.type}</span>
                        </div>
                        <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
                          ( PC : {rk.pc_vol?.toLocaleString() || 0} / MO : {rk.mo_vol?.toLocaleString() || 0} )
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div>
                  <p style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>스마트블록/통합 노출 키워드</p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                    {blockList.map((b, i) => (
                      <span key={i} style={{ background: "#3b82f6", color: "white", padding: "4px 12px", borderRadius: "16px", fontSize: "0.85rem" }}>
                        {b.block_title}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {/* 블로그 검색 결과 카드 */}
            {searchPhase === "selecting" && blockList.length > 0 && (
              <div className="glass-card" style={{ padding: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", borderBottom: "1px solid #e2e8f0", paddingBottom: "1rem" }}>
                  <h3 style={{ fontSize: "1.2rem", margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    블로그 <span>v</span> 검색 결과
                  </h3>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button onClick={selectAll} className="btn-secondary" style={{ padding: "0.4rem 1rem", fontSize: "0.85rem" }}>
                      {selectedUrls.length === blockList.reduce((acc, b) => acc + (b.links ? b.links.length : 0), 0) && selectedUrls.length > 0 ? "전체 해제" : "전체 선택"}
                    </button>
                    <button onClick={handleAnalyzeSelected} className="btn-primary" disabled={selectedUrls.length === 0} style={{ padding: "0.4rem 1rem", fontSize: "0.85rem" }}>
                      선택 분석 ({selectedUrls.length}개)
                    </button>
                  </div>
                </div>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                  {blockList.map((block, idx) => (
                    <div key={idx}>
                      <div style={{ fontSize: "1rem", fontWeight: "bold", color: "#334155", marginBottom: "0.8rem", background: "#f1f5f9", padding: "0.5rem 1rem", borderRadius: "4px" }}>
                         {block.block_title}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.5rem" }}>
                        {block.links.map((item, i) => (
                          <label key={i} className="flex items-center gap-3 p-2" style={{ cursor: "pointer", background: selectedUrls.includes(item.url) ? "#f0fdf4" : "transparent", transition: "all 0.2s", borderRadius: "4px", borderBottom: "1px solid #f1f5f9" }}>
                            <input 
                              type="checkbox" 
                              checked={selectedUrls.includes(item.url)}
                              onChange={() => toggleSelection(item.url)}
                              style={{ width: "16px", height: "16px" }}
                            />
                            <div style={{ flex: 1, overflow: "hidden" }}>
                              <div style={{ fontSize: "0.95rem", color: "#1e293b", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                {item.type && (
                                  <span style={{ fontSize: "0.75rem", padding: "2px 6px", borderRadius: "4px", backgroundColor: "#e2e8f0", color: "#475569", fontWeight: "bold" }}>
                                    {item.type}
                                  </span>
                                )}
                                <span>{item.title}</span>
                              </div>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {searchPhase === "done" && data && (
              <div className="fade-in">
                  <div style={{ marginBottom: "1rem", textAlign: "right" }}>
                      <button onClick={() => setSearchPhase("selecting")} className="btn-secondary" style={{ padding: "0.5rem 1rem" }}>
                          ← 리스트 다시 보기
                      </button>
                  </div>
                  <SeoResults data={data} />
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
