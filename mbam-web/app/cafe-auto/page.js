"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect } from "react";
import ManuscriptLoaderModal from "../components/ManuscriptLoaderModal";

export default function CafeAutoPage() {
  const [mainTab, setMainTab] = useState("single"); // "single", "target", "nurture"

  // --- Tab 1: Single/Loop ---
  const [activeTab, setActiveTab] = useState("manual"); // "manual", "ai"
  const [loginMode, setLoginMode] = useState("manual"); // "manual", "auto"
  const [naverId, setNaverId] = useState("");
  const [naverPw, setNaverPw] = useState("");
  const [cafeUrl, setCafeUrl] = useState("");
  const [boardName, setBoardName] = useState("");
  const [actionType, setActionType] = useState("post"); // "post" or "comment"
  const [targetKeyword, setTargetKeyword] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [images, setImages] = useState([]);
  const [referenceData, setReferenceData] = useState(null);

  // --- Tab 2: Target Multi ---
  const [targetUrls, setTargetUrls] = useState("");
  const [selectedAccounts, setSelectedAccounts] = useState([]);
  const [targetMultiKeyword, setTargetMultiKeyword] = useState("");
  const [delayMin, setDelayMin] = useState(30);
  const [delayMax, setDelayMax] = useState(60);

  // --- Tab 3: Nurture ---
  const [accounts, setAccounts] = useState([]);
  const [schedules, setSchedules] = useState([]);
  
  // Nurture Form States
  const [newAccId, setNewAccId] = useState("");
  const [newAccPw, setNewAccPw] = useState("");
  const [newCafeAccId, setNewCafeAccId] = useState("");
  const [newCafeUrl, setNewCafeUrl] = useState("");
  const [newCafeBoard, setNewCafeBoard] = useState("");
  const [newSchAccId, setNewSchAccId] = useState("");
  const [newSchCafeId, setNewSchCafeId] = useState("");
  const [newSchTime, setNewSchTime] = useState("");
  const [newSchCategory, setNewSchCategory] = useState("");
  const [newSchContentItem, setNewSchContentItem] = useState("");
  const [newSchContentItemTitle, setNewSchContentItemTitle] = useState("");
  const [newSchCount, setNewSchCount] = useState(1);
  const [newSchQty, setNewSchQty] = useState(1);
  const [categories, setCategories] = useState([]);
  const [categoryItems, setCategoryItems] = useState([]);

  // --- Common ---
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [statusLogs, setStatusLogs] = useState([]);
  const [taskStatus, setTaskStatus] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    // Load accounts and schedules if in nurture or target tab
    if (mainTab === "nurture" || mainTab === "target") {
      fetchAccounts();
      if (mainTab === "nurture") fetchSchedules();
    }
  }, [mainTab]);

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const res = await fetchWithAuth("/api/content/categories");
        if (res.ok) {
          const data = await res.json();
          setCategories(data.categories || []);
        }
      } catch (err) {}
    };
    fetchCategories();
  }, []);

  useEffect(() => {
    if (newSchCategory) {
      const fetchItems = async () => {
        try {
          const res = await fetchWithAuth(`/api/content/list?category=${encodeURIComponent(newSchCategory)}`);
          if (res.ok) {
            const data = await res.json();
            setCategoryItems(data.items || []);
          }
        } catch (e) {}
      };
      fetchItems();
    } else {
      setCategoryItems([]);
      setNewSchContentItem("");
      setNewSchContentItemTitle("");
    }
  }, [newSchCategory]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const source = params.get("source_data");
      const kw = params.get("keyword");
      if (source) {
        setContent(source);
      }
      if (kw) {
        setTargetKeyword(kw);
      }
    }
  }, []);

  const fetchAccounts = async () => {
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/accounts");
      if (res.ok) {
        setAccounts(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchSchedules = async () => {
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/schedules");
      if (res.ok) {
        setSchedules(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Status polling
  useEffect(() => {
    let intervalId;
    if (taskId && taskStatus !== "completed" && taskStatus !== "failed") {
      intervalId = setInterval(async () => {
        try {
          // Check which endpoint to poll based on tab
          const endpoint = mainTab === "target" 
            ? `/api/cafe-nurture/status/${taskId}`
            : `/api/auto_post/status/${taskId}`;
            
          const res = await fetchWithAuth(endpoint);
          if (res.ok) {
            const data = await res.json();
            setStatusLogs(data.logs || []);
            setTaskStatus(data.status);
            if (data.status === "completed" || data.status === "failed") {
              setLoading(false);
            }
          } else if (res.status === 404) {
            setLoading(false);
            setTaskStatus("failed");
          }
        } catch (e) {
          console.error("Status check failed", e);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [taskId, taskStatus, mainTab]);

  // --- Handlers Tab 1 ---
  const handleStartSingle = async () => {
    if (!cafeUrl || !boardName) return alert("타겟 카페 주소와 게시판 이름을 입력해주세요.");
    
    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null);
    try {
      const payload = {
        target_type: "cafe", login_mode: loginMode,
        naver_id: loginMode === "auto" ? naverId : null,
        naver_pw: loginMode === "auto" ? naverPw : null,
        post_mode: activeTab === "ai" ? "ai_generate" : "manual_text",
        target_keyword: targetKeyword, title, content,
        publish_mode: "instant", cafe_url: cafeUrl, board_name: boardName,
        images: images, cafe_action_type: actionType, reference_data: referenceData
      };
      const res = await fetchWithAuth("/api/auto_post/", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) setTaskId(data.task_id);
      else { alert("실패했습니다."); setLoading(false); }
    } catch (e) { alert("서버 오류"); setLoading(false); }
  };

  const handleLoadManuscript = (manuscript) => {
    setTitle(manuscript.title);
    setContent(manuscript.content);
    alert("원고가 성공적으로 불러와졌습니다.");
  };

  // --- Handlers Tab 2 ---
  const handleStartTargetMulti = async () => {
    if (!targetUrls || selectedAccounts.length === 0 || !targetMultiKeyword) {
      return alert("URL 목록, 계정 선택, 키워드를 모두 입력해주세요.");
    }
    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null);
    try {
      const payload = {
        urls: targetUrls.split("\\n").map(u => u.trim()).filter(u => u),
        account_ids: selectedAccounts,
        keyword: targetMultiKeyword,
        delay_min: delayMin,
        delay_max: delayMax
      };
      const res = await fetchWithAuth("/api/cafe-nurture/trigger-targeted", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) setTaskId(data.task_id);
      else { alert(data.detail || "실패했습니다."); setLoading(false); }
    } catch (e) { alert("서버 오류"); setLoading(false); }
  };

  const handleCancelTask = async () => {
    if (!taskId) return;
    if (!window.confirm("정말 진행 중인 작업을 중단하시겠습니까?")) return;
    try {
      const endpoint = mainTab === "target" 
        ? `/api/cafe-nurture/cancel/${taskId}`
        : `/api/auto_post/cancel/${taskId}`;
      const res = await fetchWithAuth(endpoint, { method: "POST" });
      const data = await res.json();
      if (res.ok && data.success) {
        setTaskStatus("failed");
        setLoading(false);
      } else {
        alert(data.message || "작업 중지에 실패했습니다.");
      }
    } catch(e) {
      alert("작업 중지 오류: " + e.message);
    }
  };

  const toggleAccountSelection = (id) => {
    setSelectedAccounts(prev => prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]);
  };

  // --- Handlers Tab 3 ---
  const handleRegisterAccount = async (acc) => {
    if (!window.confirm(`'${acc.naver_id}' 계정의 기기 인증을 시작합니다.\n잠시 후 열리는 브라우저 창에서 로그인 + 2단계 인증을 완료해주세요.\n(최초 1회만 하면 이후 자동 로그인됩니다)`)) return;
    try {
      setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null);
      const res = await fetchWithAuth("/api/auto_post/register-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ naver_id: acc.naver_id, naver_pw: null })
      });
      const data = await res.json();
      if (data.success && data.task_id) { setTaskId(data.task_id); }
      else { alert("기기 인증 시작에 실패했습니다."); setLoading(false); }
    } catch (e) { alert("서버 오류 (백엔드 서버가 켜져 있는지 확인해주세요)"); setLoading(false); }
  };

  const handleAddAccount = async () => {
    if (!newAccId || !newAccPw) return;
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/accounts", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ naver_id: newAccId, naver_pw: newAccPw })
      });
      if (res.ok) { alert("추가 완료"); setNewAccId(""); setNewAccPw(""); fetchAccounts(); }
      else { const d = await res.json(); alert(d.detail); }
    } catch (e) { alert("오류"); }
  };

  const handleAddCafe = async () => {
    if (!newCafeAccId || !newCafeUrl || !newCafeBoard) return;
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/cafes", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: newCafeAccId, cafe_url: newCafeUrl, board_name: newCafeBoard })
      });
      if (res.ok) { alert("추가 완료"); fetchAccounts(); }
    } catch (e) { alert("오류"); }
  };

  const handleAddSchedule = async () => {
    if (!newSchAccId || !newSchCafeId || !newSchTime) return;
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/schedules", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ 
            account_id: newSchAccId, 
            cafe_id: newSchCafeId, 
            schedule_time: newSchTime,
            content_category: newSchCategory || null,
            content_item_id: newSchContentItem || null,
            content_item_title: newSchContentItemTitle || null,
            post_count_per_day: Number(newSchCount),
            post_qty_per_time: Number(newSchQty)
        })
      });
      if (res.ok) { alert("추가 완료"); fetchSchedules(); }
    } catch (e) { alert("오류"); }
  };

  return (
    <div style={{ padding: "2rem", display: "flex", gap: "2rem", height: "100%", boxSizing: "border-box" }}>
      <div style={{ flex: 2, display: "flex", flexDirection: "column", gap: "1rem" }}>
        
        {/* Header Tabs */}
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "1rem" }}>카페 전문 육성 & 자동화</h1>
          <div style={{ display: "flex", gap: "1rem", borderBottom: "2px solid #e2e8f0" }}>
            {[
              { id: "single", label: "일반 포스팅/순회" },
              { id: "target", label: "타겟 게시글 다중 작업" },
              { id: "nurture", label: "계정 육성 관리 (스케줄)" }
            ].map(tab => (
              <button key={tab.id} onClick={() => setMainTab(tab.id)}
                style={{
                  padding: "0.8rem 1.5rem", border: "none", background: "none",
                  fontWeight: "bold", fontSize: "1.05rem", cursor: "pointer",
                  color: mainTab === tab.id ? "#2563eb" : "#64748b",
                  borderBottom: mainTab === tab.id ? "3px solid #2563eb" : "3px solid transparent",
                  marginBottom: "-2px"
                }}>
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", overflowY: "auto" }}>
          
          {/* TAB 1: SINGLE / LOOP */}
          {mainTab === "single" && (
            <>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>작업 유형</h2>
                <div style={{ display: "flex", gap: "1rem" }}>
                  <label><input type="radio" checked={actionType === "post"} onChange={() => setActionType("post")} /> 새 게시글 발행</label>
                  <label><input type="radio" checked={actionType === "comment"} onChange={() => setActionType("comment")} /> 기존 글 순회 & 자동 댓글</label>
                </div>
              </div>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>타겟 카페</h2>
                <div style={{ display: "flex", gap: "1rem" }}>
                  <input type="text" placeholder="카페 URL (예: https://cafe.naver.com/joonggonara)" value={cafeUrl} onChange={e => setCafeUrl(e.target.value)} style={{ flex: 1, padding: "0.8rem" }} />
                  <input type="text" placeholder="게시판 이름 (예: 자유게시판)" value={boardName} onChange={e => setBoardName(e.target.value)} style={{ flex: 1, padding: "0.8rem" }} />
                </div>
              </div>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>로그인 방식</h2>
                <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
                  <label><input type="radio" checked={loginMode === "manual"} onChange={() => setLoginMode("manual")} /> 수동 대기</label>
                  <label><input type="radio" checked={loginMode === "auto"} onChange={() => setLoginMode("auto")} /> ID/PW 자동</label>
                </div>
                {loginMode === "auto" && (
                  <div style={{ display: "flex", gap: "1rem" }}>
                    <input type="text" placeholder="네이버 아이디" value={naverId} onChange={e => setNaverId(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} />
                    <input type="password" placeholder="비밀번호" value={naverPw} onChange={e => setNaverPw(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} />
                  </div>
                )}
              </div>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>원고 (키워드)</h2>
                  <button onClick={() => setIsModalOpen(true)} style={{ padding: '0.4rem 0.8rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                    ☁️ 웹에서 불러오기
                  </button>
                </div>
                <input type="text" placeholder="타겟 키워드 (AI 댓글 생성용)" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem" }} />
                {actionType === "post" && <input type="text" placeholder="직접 제목 작성 시" value={title} onChange={e => setTitle(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem" }} />}
                <textarea placeholder="직접 본문 작성 시 (비워두면 AI 자동작성)" value={content} onChange={e => setContent(e.target.value)} style={{ width: "100%", height: "100px", padding: "0.8rem" }} />
              </div>
              <div style={{ display: "flex", gap: "1rem" }}>
                <button onClick={handleStartSingle} disabled={loading} style={{ flex: 1, padding: "1rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: loading ? "wait" : "pointer" }}>
                  {loading ? "작업 중..." : "일반 작업 시작하기"}
                </button>
                {loading && (
                  <button onClick={handleCancelTask} style={{ padding: "1rem 2rem", background: "#ef4444", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer" }}>
                    ■ 작업 강제 중지
                  </button>
                )}
              </div>
            </>
          )}

          {/* TAB 2: TARGET MULTI */}
          {mainTab === "target" && (
            <>
              <div style={{ padding: "1rem", background: "#eff6ff", color: "#1e3a8a", border: "1px solid #bfdbfe", borderRadius: "8px" }}>
                💡 <b>여론 형성(품앗이) 모드</b>: 입력된 게시글 URL들을 저장된 여러 개의 네이버 아이디로 차례대로 방문하여, 지정된 키워드의 뉘앙스로 자연스러운 호응 댓글을 작성합니다.
              </div>
              
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>1. 참여할 계정 선택</h2>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {accounts.map(acc => (
                    <label key={acc.id} style={{ padding: "0.5rem 1rem", border: "1px solid #cbd5e1", borderRadius: "20px", cursor: "pointer", background: selectedAccounts.includes(acc.id) ? "#2563eb" : "white", color: selectedAccounts.includes(acc.id) ? "white" : "black" }}>
                      <input type="checkbox" style={{ display: "none" }} checked={selectedAccounts.includes(acc.id)} onChange={() => toggleAccountSelection(acc.id)} />
                      {acc.naver_id}
                    </label>
                  ))}
                  {accounts.length === 0 && <span style={{ color: "#94a3b8" }}>'계정 육성 관리' 탭에서 아이디를 먼저 등록해주세요.</span>}
                </div>
              </div>

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>2. 타겟 게시글 URL 입력</h2>
                <textarea placeholder="댓글을 달 게시글 URL을 한 줄에 하나씩 입력하세요." value={targetUrls} onChange={e => setTargetUrls(e.target.value)} style={{ width: "100%", height: "120px", padding: "0.8rem", border: "1px solid #cbd5e1" }} />
              </div>

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>3. 댓글 방향성 및 설정</h2>
                <input type="text" placeholder="예: 무조건 칭찬하는, 정보가 유익하다는 반응" value={targetMultiKeyword} onChange={e => setTargetMultiKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem", border: "1px solid #cbd5e1" }} />
                
                <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                  <span>게시글 간 대기시간 (초):</span>
                  <input type="number" value={delayMin} onChange={e => setDelayMin(e.target.value)} style={{ width: "80px", padding: "0.5rem" }} />
                  <span>~</span>
                  <input type="number" value={delayMax} onChange={e => setDelayMax(e.target.value)} style={{ width: "80px", padding: "0.5rem" }} />
                </div>
              </div>
              
              <div style={{ display: "flex", gap: "1rem" }}>
                <button onClick={handleStartTargetMulti} disabled={loading} style={{ flex: 1, padding: "1rem", background: loading ? "#94a3b8" : "#0f172a", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: loading ? "wait" : "pointer" }}>
                  {loading ? "작업 중..." : "다중 타겟 댓글 작업 시작"}
                </button>
                {loading && (
                  <button onClick={handleCancelTask} style={{ padding: "1rem 2rem", background: "#ef4444", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer" }}>
                    ■ 작업 강제 중지
                  </button>
                )}
              </div>
            </>
          )}

          {/* TAB 3: NURTURE */}
          {mainTab === "nurture" && (
            <>
              <div style={{ padding: "1rem", background: "#fdf2f8", color: "#831843", border: "1px solid #fbcfe8", borderRadius: "8px" }}>
                💡 <b>계정 자동 육성</b>: 내 네이버 아이디들을 등록하고 가입된 카페를 매핑한 뒤, 스케줄을 설정해두면 백그라운드 서버가 알아서 매일 방문하여 소통(댓글) 작업을 수행합니다.
              </div>

              {/* 1. Account Management */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>1. 네이버 아이디 풀 관리</h2>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                  <input type="text" placeholder="네이버 아이디" value={newAccId} onChange={e => setNewAccId(e.target.value)} style={{ padding: "0.5rem" }} />
                  <input type="password" placeholder="비밀번호" value={newAccPw} onChange={e => setNewAccPw(e.target.value)} style={{ padding: "0.5rem" }} />
                  <button onClick={handleAddAccount} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none" }}>추가</button>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>ID</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>상태</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>기기 인증</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map(acc => (
                      <tr key={acc.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                        <td style={{ padding: "0.5rem" }}>{acc.naver_id}</td>
                        <td style={{ padding: "0.5rem" }}>
                          <span style={{ background: "#dcfce7", color: "#166534", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>{acc.status}</span>
                        </td>
                        <td style={{ padding: "0.5rem" }}>
                          <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="최초 1회 수동 로그인+2단계 인증으로 기기를 등록하면 이후 자동 로그인됩니다." style={{ padding: "0.3rem 0.6rem", background: "#fef3c7", color: "#b45309", border: "1px solid #fcd34d", borderRadius: "4px", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap" }}>🔐 기기 인증</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 2. Cafe Mapping */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>2. 아이디별 가입 카페 매핑</h2>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                  <select value={newCafeAccId} onChange={e => setNewCafeAccId(e.target.value)} style={{ padding: "0.5rem" }}>
                    <option value="">계정 선택</option>
                    {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                  </select>
                  <input type="text" placeholder="카페 주소 URL" value={newCafeUrl} onChange={e => setNewCafeUrl(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} />
                  <input type="text" placeholder="게시판 이름" value={newCafeBoard} onChange={e => setNewCafeBoard(e.target.value)} style={{ padding: "0.5rem", width: "120px" }} />
                  <button onClick={handleAddCafe} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none" }}>등록</button>
                </div>
                <ul style={{ paddingLeft: "1.5rem", margin: 0, fontSize: "0.9rem" }}>
                  {accounts.map(acc => (
                    acc.cafes && acc.cafes.map(cafe => (
                      <li key={cafe.id} style={{ marginBottom: "0.3rem" }}>
                        <strong>{acc.naver_id}</strong> ➔ {cafe.cafe_url} ({cafe.board_name})
                      </li>
                    ))
                  ))}
                </ul>
              </div>

              {/* 3. Scheduling */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>3. 일일 자동 방문(육성) 스케줄</h2>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <select value={newSchAccId} onChange={e => {
                    setNewSchAccId(e.target.value); setNewSchCafeId("");
                  }} style={{ padding: "0.5rem" }}>
                    <option value="">계정 선택</option>
                    {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                  </select>
                  
                  <select value={newSchCafeId} onChange={e => setNewSchCafeId(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} disabled={!newSchAccId}>
                    <option value="">매핑된 카페 선택</option>
                    {accounts.find(a => a.id === newSchAccId)?.cafes.map(cafe => (
                      <option key={cafe.id} value={cafe.id}>{cafe.cafe_url} ({cafe.board_name})</option>
                    ))}
                  </select>

                  <input type="time" value={newSchTime} onChange={e => setNewSchTime(e.target.value)} style={{ padding: "0.5rem" }} />
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                  <select value={newSchCategory} onChange={e => setNewSchCategory(e.target.value)} style={{ padding: "0.5rem", flex: 1 }}>
                    <option value="">글감 선택 안함 (일반 육성)</option>
                    {categories.map((c, i) => <option key={i} value={c}>{c}</option>)}
                  </select>
                  {newSchCategory && (
                    <select 
                      value={newSchContentItem} 
                      onChange={e => {
                        setNewSchContentItem(e.target.value);
                        const selectedItem = categoryItems.find(item => item.id === e.target.value);
                        if (selectedItem) {
                          setNewSchContentItemTitle(selectedItem.title);
                        } else {
                          setNewSchContentItemTitle("");
                        }
                      }} 
                      style={{ padding: "0.5rem", flex: 1 }}
                    >
                      <option value="">카테고리 전체 랜덤</option>
                      {categoryItems.map(item => (
                        <option key={item.id} value={item.id}>{item.title}</option>
                      ))}
                    </select>
                  )}
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.2rem'}}>
                    <span style={{fontSize: '0.9rem'}}>일일횟수</span>
                    <input type="number" min="1" value={newSchCount} onChange={e => setNewSchCount(e.target.value)} style={{ padding: "0.5rem", width: "60px" }} />
                  </div>
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.2rem'}}>
                    <span style={{fontSize: '0.9rem'}}>1회수량</span>
                    <input type="number" min="1" value={newSchQty} onChange={e => setNewSchQty(e.target.value)} style={{ padding: "0.5rem", width: "60px" }} />
                  </div>
                  <button onClick={handleAddSchedule} style={{ padding: "0.5rem 1rem", background: "#0f172a", color: "white", border: "none" }}>예약</button>
                </div>
                
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>실행 시간</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>대상 계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>대상 카페</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>글감 연동</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedules.map(sch => (
                      <tr key={sch.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                        <td style={{ padding: "0.5rem", fontWeight: "bold" }}>매일 {sch.schedule_time}</td>
                        <td style={{ padding: "0.5rem" }}>{sch.naver_id}</td>
                        <td style={{ padding: "0.5rem" }}>{sch.cafe_url} ({sch.board_name})</td>
                        <td style={{ padding: "0.5rem", fontSize: "0.85rem", color: "#475569" }}>
                          {sch.content_category ? `${sch.content_category}${sch.content_item_title ? ` - ${sch.content_item_title}` : ''} (${sch.post_count_per_day}회/${sch.post_qty_per_time}개)` : "-"}
                        </td>
                        <td style={{ padding: "0.5rem" }}>
                          <span style={{ background: sch.is_active ? "#dcfce7" : "#f1f5f9", color: sch.is_active ? "#166534" : "#64748b", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
                            {sch.is_active ? "활성화" : "정지"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

        </div>
      </div>

      <div style={{ flex: 1, background: "#1e293b", border: "1px solid #0f172a", display: "flex", flexDirection: "column", color: "#f8fafc" }}>
        <div style={{ padding: "1rem", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0, color: "#f8fafc" }}>실시간 모니터링 로그</h2>
          {taskStatus === "running" && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>● Running</span>}
          {taskStatus === "completed" && <span style={{ color: "#60a5fa", fontSize: "0.8rem" }}>✓ Completed</span>}
          {taskStatus === "failed" && <span style={{ color: "#f87171", fontSize: "0.8rem" }}>✕ Failed</span>}
        </div>
        <div style={{ flex: 1, padding: "1rem", overflowY: "auto", fontFamily: "monospace", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {statusLogs.length === 0 ? (
            <div style={{ color: "#94a3b8" }}>대기 중... 작업을 시작하면 로그가 표시됩니다.</div>
          ) : (
            statusLogs.map((log, i) => (
              <div key={i} style={{ color: log.includes("✅") ? "#34d399" : log.includes("⚠️") ? "#fbbf24" : "#cbd5e1" }}>
                {log}
              </div>
            ))
          )}
        </div>
      </div>

      <ManuscriptLoaderModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSelect={handleLoadManuscript} 
      />
    </div>
  );
}