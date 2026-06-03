"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";
import { Loader2, Plus, Trash2, Send, LayoutDashboard, Search, KeyRound, TrendingUp } from 'lucide-react';

export default function BlogspotDashboard() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("accounts");
  
  // Add Account Form
  const [accountName, setAccountName] = useState("");
  const [blogId, setBlogId] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [clientId, setClientId] = useState("auto_fill_client");
  const [clientSecret, setClientSecret] = useState("auto_fill_secret");
  const [refreshToken, setRefreshToken] = useState("auto_fill_refresh");

  // Auto Post Form
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [aiProvider, setAiProvider] = useState("gemini");
  const [generateImage, setGenerateImage] = useState(true);
  const [postResult, setPostResult] = useState(null);

  // SEO Rank Form
  const [rankKeyword, setRankKeyword] = useState("");
  const [trackedKeywords, setTrackedKeywords] = useState([]);

  const loadTrackedKeywords = async () => {
    try {
      const res = await fetchWithAuth("/api/blogspot/rank");
      const data = await res.json();
      if(data.success) setTrackedKeywords(data.keywords || []);
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    loadAccounts();
    loadTrackedKeywords();
  }, []);

  const loadAccounts = async () => {
    try {
      const res = await fetchWithAuth("/api/blogspot/accounts");
      const data = await res.json();
      if (data.success) {
        setAccounts(data.accounts);
        if (data.accounts.length > 0) setSelectedAccountId(data.accounts[0].id);
      }
    } catch (e) { console.error(e); }
  };

  const handleAddAccount = async (e) => {
    e.preventDefault();
    if(!accountName || !blogId || !accessToken) return alert("필수 정보를 입력하세요.");
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/blogspot/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_name: accountName, blog_id: blogId, access_token: accessToken, client_id: clientId, client_secret: clientSecret, refresh_token: refreshToken })
      });
      const data = await res.json();
      if(data.success) {
        alert("다중 계정이 연동되었습니다!");
        setAccountName(""); setBlogId(""); setAccessToken("");
        loadAccounts();
      }
    } catch (e) { alert("연동 실패"); }
    finally { setLoading(false); }
  };

  const handleDeleteAccount = async (id) => {
    if(!confirm("이 블로그 계정을 삭제하시겠습니까?")) return;
    try {
      await fetchWithAuth(`/api/blogspot/accounts/${id}`, { method: "DELETE" });
      loadAccounts();
    } catch (e) { alert("삭제 실패"); }
  };

  const handleAutoPost = async (e) => {
    e.preventDefault();
    if(!selectedAccountId || !keyword) return alert("계정 선택 및 키워드를 입력하세요.");
    setLoading(true);
    setPostResult(null);
    try {
      const res = await fetchWithAuth("/api/blogspot/post", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: selectedAccountId, keyword, ai_provider: aiProvider, generate_image: generateImage })
      });
      const data = await res.json();
      if(data.success) {
        setPostResult({ success: true, url: data.post_url });
      } else {
        setPostResult({ success: false, error: JSON.stringify(data.error) });
      }
    } catch (e) { setPostResult({ success: false, error: e.message }); }
    finally { setLoading(false); }
  };

  const handleAddTrackKeyword = async (e) => {
    e.preventDefault();
    if(!selectedAccountId || !rankKeyword) return alert("계정 선택 및 키워드를 입력하세요.");
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/blogspot/rank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: selectedAccountId, keyword: rankKeyword })
      });
      if((await res.json()).success) {
        setRankKeyword("");
        loadTrackedKeywords();
      }
    } catch (e) { alert("추가 실패"); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem", fontFamily: "sans-serif" }}>
      <header style={{ marginBottom: "2rem", borderBottom: "2px solid #e2e8f0", paddingBottom: "1rem" }}>
        <h1 style={{ fontSize: "1.8rem", color: "#1e293b", display: "flex", alignItems: "center", gap: "0.5rem", margin: 0 }}>
          <LayoutDashboard size={28} color="#f97316"/> 블로그 스팟 자동화 대시보드
        </h1>
        <p style={{ color: "#64748b", marginTop: "0.5rem" }}>Blogger API V3 연동 및 다중 계정 AI 포스팅 시스템</p>
      </header>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem" }}>
        <button onClick={()=>setActiveTab("accounts")} style={{ padding: "0.8rem 1.5rem", background: activeTab==="accounts"?"#f97316":"white", color: activeTab==="accounts"?"white":"#475569", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: "bold", cursor: "pointer", display: "flex", gap: "0.5rem" }}><KeyRound size={18}/> 다중 계정 연동</button>
        <button onClick={()=>setActiveTab("autopost")} style={{ padding: "0.8rem 1.5rem", background: activeTab==="autopost"?"#f97316":"white", color: activeTab==="autopost"?"white":"#475569", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: "bold", cursor: "pointer", display: "flex", gap: "0.5rem" }}><Send size={18}/> 원격 AI 자동포스팅</button>
        <button onClick={()=>setActiveTab("rank")} style={{ padding: "0.8rem 1.5rem", background: activeTab==="rank"?"#f97316":"white", color: activeTab==="rank"?"white":"#475569", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: "bold", cursor: "pointer", display: "flex", gap: "0.5rem" }}><TrendingUp size={18}/> 구글 SEO 순위 추적</button>
      </div>

      {activeTab === "accounts" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
          <div style={{ background: "white", padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)" }}>
            <h2 style={{ fontSize: "1.2rem", marginBottom: "1rem", color: "#334155" }}>신규 계정 추가 (OAuth)</h2>
            <form onSubmit={handleAddAccount} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <input type="text" placeholder="블로그 별칭 (예: 뷰티 메인 블로그)" value={accountName} onChange={e=>setAccountName(e.target.value)} style={{ padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} required />
              <input type="text" placeholder="Blogger API 블로그 ID (숫자)" value={blogId} onChange={e=>setBlogId(e.target.value)} style={{ padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} required />
              <textarea placeholder="Access Token 입력 (디버그용 직접 입력)" value={accessToken} onChange={e=>setAccessToken(e.target.value)} style={{ padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px", minHeight: "80px" }} required />
              <button type="submit" disabled={loading} style={{ background: "#10b981", color: "white", padding: "0.8rem", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>{loading ? "연동 중..." : "다중 계정 추가"}</button>
            </form>
          </div>
          <div style={{ background: "white", padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)" }}>
            <h2 style={{ fontSize: "1.2rem", marginBottom: "1rem", color: "#334155" }}>연동된 다중 계정 목록 ({accounts.length}개)</h2>
            {accounts.length === 0 ? <p style={{ color: "#94a3b8" }}>연동된 계정이 없습니다.</p> : (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {accounts.map(acc => (
                  <li key={acc.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem", border: "1px solid #f1f5f9", borderRadius: "8px", marginBottom: "0.5rem", background: "#f8fafc" }}>
                    <div>
                      <div style={{ fontWeight: "bold", color: "#1e293b" }}>{acc.account_name}</div>
                      <div style={{ fontSize: "0.8rem", color: "#64748b" }}>ID: {acc.blog_id}</div>
                    </div>
                    <button onClick={()=>handleDeleteAccount(acc.id)} style={{ background: "transparent", border: "none", color: "#ef4444", cursor: "pointer" }}><Trash2 size={18}/></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {activeTab === "autopost" && (
        <div style={{ background: "white", padding: "2rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)" }}>
          <h2 style={{ fontSize: "1.3rem", marginBottom: "1.5rem", color: "#334155" }}>원터치 AI 포스팅 봇</h2>
          <form onSubmit={handleAutoPost} style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem", maxWidth: "600px" }}>
            
            <div>
              <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold", color: "#475569" }}>포스팅할 블로그 계정 선택</label>
              <select value={selectedAccountId} onChange={e=>setSelectedAccountId(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px" }}>
                {accounts.map(a => <option key={a.id} value={a.id}>{a.account_name} ({a.blog_id})</option>)}
              </select>
            </div>

            <div>
              <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold", color: "#475569" }}>타겟 키워드 (이 키워드로 글감 수집 및 작성)</label>
              <input type="text" value={keyword} onChange={e=>setKeyword(e.target.value)} placeholder="예: 2024년 해외여행지 추천" style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} required />
            </div>

            <div style={{ display: "flex", gap: "2rem" }}>
              <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold", color: "#475569" }}>생성 AI 엔진</label>
                <div style={{ display: "flex", gap: "1rem" }}>
                  <label><input type="radio" value="gemini" checked={aiProvider==="gemini"} onChange={e=>setAiProvider(e.target.value)}/> Gemini 1.5</label>
                  <label><input type="radio" value="claude" checked={aiProvider==="claude"} onChange={e=>setAiProvider(e.target.value)}/> Claude 3</label>
                </div>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold", color: "#475569" }}>대표 이미지 자동 생성</label>
                <label><input type="checkbox" checked={generateImage} onChange={e=>setGenerateImage(e.target.checked)}/> 썸네일 이미지 본문 삽입</label>
              </div>
            </div>

            <button type="submit" disabled={loading} style={{ background: "#3b82f6", color: "white", padding: "1rem", border: "none", borderRadius: "8px", fontSize: "1.1rem", fontWeight: "bold", cursor: loading?"wait":"pointer", display: "flex", justifyContent: "center", gap: "0.5rem" }}>
              {loading ? <Loader2 className="animate-spin"/> : <Send/>} {loading ? "AI가 글을 작성하고 구글에 발행중입니다..." : "AI 포스팅 즉시 발행"}
            </button>
          </form>

          {postResult && (
            <div style={{ marginTop: "2rem", padding: "1.5rem", background: postResult.success ? "#ecfdf5" : "#fef2f2", border: `1px solid ${postResult.success ? "#a7f3d0" : "#fecaca"}`, borderRadius: "8px" }}>
              {postResult.success ? (
                <>
                  <h3 style={{ color: "#059669", margin: "0 0 0.5rem 0" }}>🎉 블로그 스팟 발행 완료!</h3>
                  <a href={postResult.url} target="_blank" rel="noreferrer" style={{ color: "#3b82f6", fontWeight: "bold", textDecoration: "underline" }}>작성된 포스팅 보러가기</a>
                </>
              ) : (
                <>
                  <h3 style={{ color: "#dc2626", margin: "0 0 0.5rem 0" }}>🚨 발행 실패</h3>
                  <p style={{ color: "#ef4444", fontSize: "0.9rem", wordBreak: "break-all" }}>{postResult.error}</p>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === "rank" && (
        <div style={{ background: "white", padding: "2rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)" }}>
          <h2 style={{ fontSize: "1.3rem", marginBottom: "1.5rem", color: "#334155" }}>구글 검색결과(SERP) 노출 순위 실시간 모니터링</h2>
          <form onSubmit={handleAddTrackKeyword} style={{ display: "flex", gap: "1rem", marginBottom: "2rem", maxWidth: "800px" }}>
            <select value={selectedAccountId} onChange={e=>setSelectedAccountId(e.target.value)} style={{ width: "250px", padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px" }}>
              <option value="">블로그 계정 선택...</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.account_name}</option>)}
            </select>
            <input type="text" value={rankKeyword} onChange={e=>setRankKeyword(e.target.value)} placeholder="추적할 구글 검색 키워드 입력" style={{ flex: 1, padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} required />
            <button type="submit" disabled={loading} style={{ background: "#10b981", color: "white", padding: "0 1.5rem", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>
              {loading ? "등록중..." : "키워드 등록"}
            </button>
          </form>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
            <thead>
              <tr style={{ background: "#f1f5f9", borderBottom: "2px solid #cbd5e1" }}>
                <th style={{ padding: "1rem", textAlign: "left" }}>블로그 계정</th>
                <th style={{ padding: "1rem", textAlign: "left" }}>타겟 키워드</th>
                <th style={{ padding: "1rem", textAlign: "center" }}>현재 구글 순위</th>
                <th style={{ padding: "1rem", textAlign: "center" }}>최근 확인일시</th>
                <th style={{ padding: "1rem", textAlign: "center" }}>관리</th>
              </tr>
            </thead>
            <tbody>
              {trackedKeywords.length === 0 ? (
                <tr><td colSpan="5" style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>등록된 추적 키워드가 없습니다.</td></tr>
              ) : (
                trackedKeywords.map(k => (
                  <tr key={k.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                    <td style={{ padding: "1rem", fontWeight: "bold", color: "#475569" }}>{k.account_name}</td>
                    <td style={{ padding: "1rem", color: "#1e40af", fontWeight: "bold" }}>{k.keyword}</td>
                    <td style={{ padding: "1rem", textAlign: "center", fontWeight: "bold", color: k.current_rank > 0 && k.current_rank <= 10 ? "#10b981" : "#f59e0b" }}>
                      {k.current_rank > 0 ? `${k.current_rank}위` : "순위권 밖 (100위 밖)"}
                    </td>
                    <td style={{ padding: "1rem", textAlign: "center", color: "#64748b" }}>{k.last_checked_at || "조회 대기중"}</td>
                    <td style={{ padding: "1rem", textAlign: "center" }}>
                      <button style={{ background: "transparent", border: "none", color: "#ef4444", cursor: "pointer" }}><Trash2 size={18}/></button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}
