"use client";
import { fetchWithAuth } from "../utils/api";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";

import { useState, useEffect } from "react";

export default function CommunicationPage() {
  const [loginMode, setLoginMode] = useState("manual");
  const [naverId, setNaverId] = useState("");
  const [naverPw, setNaverPw] = useState("");
  
  // Load saved ID/PW on mount
  useEffect(() => {
    const savedId = localStorage.getItem("commNaverId");
    const savedPw = localStorage.getItem("commNaverPw");
    if (savedId) setNaverId(savedId);
    if (savedPw) setNaverPw(savedPw);
  }, []);

  const handleIdChange = (e) => {
    setNaverId(e.target.value);
    localStorage.setItem("commNaverId", e.target.value);
  };

  const handlePwChange = (e) => {
    setNaverPw(e.target.value);
    localStorage.setItem("commNaverPw", e.target.value);
  };
  
  const [targetKeyword, setTargetKeyword] = useState("");
  const [limit, setLimit] = useState(10);
  
  // Delay Settings
  const [minDelay, setMinDelay] = useState(30);
  const [maxDelay, setMaxDelay] = useState(120);
  
  const [enableNeighbor, setEnableNeighbor] = useState(true);
  const [neighborMessage, setNeighborMessage] = useState("블로그 잘 보고 갑니다! 서로이웃 해요 :)");
  
  const [enableLike, setEnableLike] = useState(true);
  
  const [enableComment, setEnableComment] = useState(false);
  const [commentMessage, setCommentMessage] = useState("좋은 글 잘 읽고 갑니다!");
  
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [statusLogs, setStatusLogs] = useState([]);
  const [taskStatus, setTaskStatus] = useState("");
  const [stopping, setStopping] = useState(false);

  // 저장된 네이버 계정 (계정 관리와 공유)
  const [accounts, setAccounts] = useState([]);
  const [showAddAcc, setShowAddAcc] = useState(false);
  const [newAcc, setNewAcc] = useState({ naver_id: "", naver_pw: "" });
  const [accMsg, setAccMsg] = useState("");

  const loadAccounts = async () => {
    try {
      const res = await fetchWithAuth("/api/accounts");
      if (res.ok) setAccounts((await res.json()).accounts || []);
    } catch (e) { /* ignore */ }
  };
  useEffect(() => { loadAccounts(); }, []);

  const addAccount = async () => {
    if (!newAcc.naver_id.trim()) { setAccMsg("아이디를 입력하세요."); return; }
    try {
      const res = await fetchWithAuth("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newAcc),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "추가 실패");
      setAccMsg("✅ 계정이 추가되었습니다. (계정 관리에서 기기인증 후 사용하세요)");
      setNaverId(newAcc.naver_id.trim());
      setNaverPw(newAcc.naver_pw || "");
      setNewAcc({ naver_id: "", naver_pw: "" });
      setShowAddAcc(false);
      loadAccounts();
    } catch (e) {
      setAccMsg("❌ " + e.message);
    }
  };

  const stopTask = async () => {
    if (!taskId) return;
    setStopping(true);
    try {
      await fetchWithAuth(`/api/communication/stop/${taskId}`, { method: "POST" });
      setTaskStatus("stopping");
    } catch (e) {
      console.error(e);
      setStopping(false);
    }
  };

  // 다른 메뉴 갔다 돌아와도 진행/완료 상태를 복원 (taskId+상태+로그를 localStorage에 보관)
  useEffect(() => {
    const saved = localStorage.getItem("mbam_comm_task");
    if (!saved) return;
    let parsed;
    try { parsed = JSON.parse(saved); } catch { return; }
    if (!parsed || !parsed.taskId) return;
    setTaskId(parsed.taskId);
    if (Array.isArray(parsed.logs)) setStatusLogs(parsed.logs);
    setTaskStatus(parsed.status || "running");
    if (parsed.status === "running" || parsed.status === "stopping") setLoading(true);
    // 서버에서 최신 상태 한 번 확인 (재시작으로 사라졌으면 정리)
    (async () => {
      try {
        const res = await fetchWithAuth(`/api/communication/status/${parsed.taskId}`);
        if (res.ok) {
          const data = await res.json();
          setStatusLogs(data.logs || []);
          setTaskStatus(data.status);
          if (data.status === "running" || data.status === "stopping") setLoading(true);
          else { setLoading(false); setStopping(false); }
        } else if (res.status === 404) {
          localStorage.removeItem("mbam_comm_task");
          setTaskId(null); setTaskStatus(""); setStatusLogs([]); setLoading(false);
        }
      } catch (e) { /* 일시 오류 무시 */ }
    })();
  }, []);

  // 상태/로그가 바뀔 때마다 보관 (완료 후 재방문 시 결과 표시용)
  useEffect(() => {
    if (taskId) {
      localStorage.setItem("mbam_comm_task", JSON.stringify({ taskId, status: taskStatus, logs: statusLogs }));
    }
  }, [taskId, taskStatus, statusLogs]);

  useEffect(() => {
    let intervalId;
    if (taskId && taskStatus !== "completed" && taskStatus !== "failed" && taskStatus !== "stopped") {
      intervalId = setInterval(async () => {
        try {
          const res = await fetchWithAuth(`/api/communication/status/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            setStatusLogs(data.logs || []);
            setTaskStatus(data.status);
            if (data.status === "completed" || data.status === "failed" || data.status === "stopped") {
              setLoading(false);
              setStopping(false);
            }
          } else if (res.status === 404) {
            setLoading(false);
            setStopping(false);
            setTaskStatus("failed");
            setStatusLogs((p) => [...(p || []), "서버가 재시작되어 기존 작업을 찾을 수 없습니다."]);
            localStorage.removeItem("mbam_comm_task");
          }
        } catch (e) {
          console.error("Status check failed", e);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [taskId, taskStatus]);

  const handleStart = async () => {
    if (loginMode === "auto" && (!naverId || !naverPw)) {
      alert("자동 로그인을 위한 네이버 아이디와 비밀번호를 입력해주세요.");
      return;
    }
    if (!targetKeyword) {
      alert("타겟 키워드를 입력해주세요.");
      return;
    }
    if (!enableNeighbor && !enableLike && !enableComment) {
      alert("최소 한 개 이상의 액션(이웃추가/공감/댓글)을 선택해주세요.");
      return;
    }
    
    setLoading(true);
    setStatusLogs([]);
    setTaskStatus("running");
    
    try {
      const payload = {
        login_mode: loginMode,
        naver_id: loginMode === "auto" ? naverId : null,
        naver_pw: loginMode === "auto" ? naverPw : null,
        target_keyword: targetKeyword,
        limit: parseInt(limit, 10),
        min_delay: parseInt(minDelay, 10),
        max_delay: parseInt(maxDelay, 10),
        enable_neighbor: enableNeighbor,
        neighbor_message: neighborMessage,
        enable_like: enableLike,
        enable_comment: enableComment,
        comment_message: commentMessage
      };

      const res = await fetchWithAuth("/api/communication/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success && data.task_id) {
        setTaskId(data.task_id);
        try { addHistory("communication", { summary: `소통·이웃 자동화 시작` }); } catch (e) {}
      } else {
        alert("자동화 시작에 실패했습니다.");
        setLoading(false);
      }
    } catch (e) {
      console.error(e);
      alert("서버 연결에 실패했습니다.");
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "2rem", display: "flex", gap: "2rem", height: "100%", boxSizing: "border-box" }}>
      <div style={{ flex: 2, display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "0.5rem" }}>소통 & 이웃 자동화</h1>
          <p style={{ color: "#64748b", margin: 0 }}>타겟 키워드를 검색하여 대상 블로그를 순회하며 공감, 댓글, 서로이웃 신청을 자동화합니다.</p>
        </div>

        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>1. 네이버 로그인 설정</h2>
          <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input type="radio" name="login" checked={loginMode === "manual"} onChange={() => setLoginMode("manual")} />
              <span>수동 로그인 대기 (안전)</span>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input type="radio" name="login" checked={loginMode === "auto"} onChange={() => setLoginMode("auto")} />
              <span>자동 로그인 (ID/PW 저장)</span>
            </label>
          </div>
          {loginMode === "auto" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem" }}>
              {/* 저장된 계정 선택 */}
              <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
                <select
                  value={naverId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setNaverId(id);
                    const a = accounts.find((x) => x.naver_id === id);
                    if (a && !a.has_pw) setNaverPw("");
                  }}
                  style={{ flex: 1, padding: "0.55rem", border: "1px solid #cbd5e1", borderRadius: "6px" }}>
                  <option value="">— 저장된 계정 선택 —</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.naver_id}>
                      {a.naver_id} {a.registered ? "✅인증완료" : "⚠️미인증"}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={() => setShowAddAcc((v) => !v)}
                  style={{ padding: "0.55rem 0.9rem", background: "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", whiteSpace: "nowrap" }}>
                  + 계정 추가
                </button>
              </div>

              {/* 계정 추가 인라인 폼 */}
              {showAddAcc && (
                <div style={{ display: "flex", gap: "0.6rem", padding: "0.8rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  <input type="text" placeholder="네이버 아이디" value={newAcc.naver_id} onChange={(e) => setNewAcc({ ...newAcc, naver_id: e.target.value })} style={{ flex: 1, minWidth: "130px", padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} />
                  <input type="password" placeholder="비밀번호(선택)" value={newAcc.naver_pw} onChange={(e) => setNewAcc({ ...newAcc, naver_pw: e.target.value })} style={{ flex: 1, minWidth: "130px", padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} />
                  <button type="button" onClick={addAccount} style={{ padding: "0.5rem 1rem", background: "#10b981", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>저장</button>
                </div>
              )}
              {accMsg && <div style={{ fontSize: "0.82rem", color: accMsg.startsWith("❌") ? "#dc2626" : "#16a34a" }}>{accMsg}</div>}

              {/* 직접 입력 (선택 계정에 비밀번호 보강용) */}
              <div style={{ display: "flex", gap: "1rem" }}>
                <input type="text" placeholder="네이버 아이디" value={naverId} onChange={e => setNaverId(e.target.value)} style={{ padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "6px", flex: 1 }} />
                <input type="password" placeholder="비밀번호 (기기인증된 계정은 불필요)" value={naverPw} onChange={e => setNaverPw(e.target.value)} style={{ padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "6px", flex: 1 }} />
              </div>
              <p style={{ fontSize: "0.8rem", color: "#94a3b8", margin: 0 }}>
                💡 계정을 선택하고 <b>계정 관리 &gt; 기기인증</b>을 1회 해두면 비밀번호 없이 자동 로그인됩니다.
              </p>
            </div>
          )}
        </div>

        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>2. 타겟 설정</h2>
          <div style={{ display: "flex", gap: "1rem" }}>
            <div style={{ flex: 2 }}>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>타겟 키워드 (어떤 글을 쓰는 블로거를 찾을까요?)</label>
              <input type="text" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} placeholder="예: 맛집탐방, 육아일기" style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>방문할 블로그 수</label>
              <select value={limit} onChange={e => setLimit(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }}>
                <option value="3">3곳 (테스트용)</option>
                <option value="5">5곳</option>
                <option value="10">10곳 (최대)</option>
              </select>
            </div>
          </div>
          
          <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>최소 지연 시간 (초)</label>
              <input type="number" value={minDelay} onChange={e => setMinDelay(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>최대 지연 시간 (초)</label>
              <input type="number" value={maxDelay} onChange={e => setMaxDelay(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
            </div>
          </div>
          <div style={{ marginTop: "1rem", fontSize: "0.85rem", color: "#64748b" }}>
            💡 블로그 순회 간격을 최소/최대 지연 시간 사이에서 무작위로 설정하여 어뷰징(봇 탐지)을 회피합니다. (권장: 30초~120초)
          </div>
          <div style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#ef4444" }}>
            * 봇 탐지 정책상 1회 실행 시 최대 10곳까지만 방문하는 것을 강력히 권장합니다.
          </div>
        </div>

        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>3. 자동화 액션 설정</h2>
          
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* 공감 */}
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold" }}>
              <input type="checkbox" checked={enableLike} onChange={e => setEnableLike(e.target.checked)} style={{ transform: "scale(1.2)" }} />
              ❤️ 타겟 게시물 공감(하트) 누르기
            </label>
            
            {/* 서로이웃 */}
            <div style={{ paddingLeft: "1.8rem", borderLeft: "2px solid #e2e8f0", marginLeft: "0.5rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", marginBottom: "0.5rem" }}>
                <input type="checkbox" checked={enableNeighbor} onChange={e => setEnableNeighbor(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                👥 서로이웃 신청하기
              </label>
              {enableNeighbor && (
                <textarea 
                  value={neighborMessage} 
                  onChange={e => setNeighborMessage(e.target.value)} 
                  placeholder="서로이웃 신청 메시지"
                  style={{ width: "100%", height: "60px", padding: "0.5rem", border: "1px solid #cbd5e1", resize: "none", fontSize: "0.9rem" }}
                />
              )}
            </div>
            
            {/* 댓글 */}
            <div style={{ paddingLeft: "1.8rem", borderLeft: "2px solid #e2e8f0", marginLeft: "0.5rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", marginBottom: "0.5rem" }}>
                <input type="checkbox" checked={enableComment} onChange={e => setEnableComment(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                💬 자동 댓글 달기
              </label>
              {enableComment && (
                <textarea 
                  value={commentMessage} 
                  onChange={e => setCommentMessage(e.target.value)} 
                  placeholder="댓글 내용"
                  style={{ width: "100%", height: "60px", padding: "0.5rem", border: "1px solid #cbd5e1", resize: "none", fontSize: "0.9rem" }}
                />
              )}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "0.8rem" }}>
          <button
            onClick={handleStart}
            disabled={loading}
            style={{
              flex: 1,
              padding: "1rem",
              background: loading ? "#94a3b8" : "#0f172a",
              color: "white",
              fontWeight: "bold",
              fontSize: "1.1rem",
              border: "none",
              cursor: loading ? "wait" : "pointer"
            }}>
            {loading ? "소통 봇 순회 중..." : "🚀 이웃 소통 시작하기"}
          </button>
          {loading && (
            <button
              onClick={stopTask}
              disabled={stopping}
              style={{
                padding: "1rem 1.6rem",
                background: stopping ? "#94a3b8" : "#dc2626",
                color: "white",
                fontWeight: "bold",
                fontSize: "1.1rem",
                border: "none",
                cursor: stopping ? "wait" : "pointer",
                whiteSpace: "nowrap"
              }}>
              {stopping ? "중지 중..." : "⏹ 중지"}
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, background: "#1e293b", border: "1px solid #0f172a", display: "flex", flexDirection: "column", color: "#f8fafc" }}>
        <div style={{ padding: "1rem", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0, color: "#f8fafc" }}>실시간 모니터링 로그</h2>
          {taskStatus === "running" && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>● Running</span>}
          {taskStatus === "stopping" && <span style={{ color: "#fbbf24", fontSize: "0.8rem" }}>● Stopping...</span>}
          {taskStatus === "completed" && <span style={{ color: "#60a5fa", fontSize: "0.8rem" }}>✓ Completed</span>}
          {taskStatus === "stopped" && <span style={{ color: "#fbbf24", fontSize: "0.8rem" }}>⏹ Stopped</span>}
          {taskStatus === "failed" && <span style={{ color: "#f87171", fontSize: "0.8rem" }}>✕ Failed</span>}
        </div>
        <div style={{ flex: 1, padding: "1rem", overflowY: "auto", fontFamily: "monospace", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {statusLogs.length === 0 ? (
            <div style={{ color: "#94a3b8" }}>대기 중... 작업을 시작하면 로그가 표시됩니다.</div>
          ) : (
            statusLogs.map((log, i) => (
              <div key={i} style={{ color: log.includes("✅") ? "#34d399" : log.includes("⚠️") || log.includes("❌") ? "#fbbf24" : "#cbd5e1" }}>
                {log}
              </div>
            ))
          )}
        </div>
      </div>
      <WorkHistory menuKey="communication" />
    </div>
  );
}