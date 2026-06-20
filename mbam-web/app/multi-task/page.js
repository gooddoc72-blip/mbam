"use client";
import { fetchWithAuth } from "../utils/api";

import { useState, useEffect } from "react";

// 전체 멀티 태스크 상태를 모니터링하는 컴포넌트
function TaskMonitorCard({ taskId }) {
  const [statusLogs, setStatusLogs] = useState([]);
  const [taskStatus, setTaskStatus] = useState("running");

  useEffect(() => {
    let intervalId;
    if (taskId && taskStatus !== "completed" && taskStatus !== "failed") {
      intervalId = setInterval(async () => {
        try {
          const res = await fetchWithAuth(`/api/multi_task/status/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            setStatusLogs(data.logs || []);
            setTaskStatus(data.status);
          }
        } catch (e) {
          console.error("Status check failed", e);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [taskId, taskStatus]);

  return (
    <div style={{ flex: 1, minWidth: "300px", background: "#1e293b", border: "1px solid #334155", color: "#f8fafc", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "0.8rem", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1rem", color: "#f8fafc" }}>멀티 계정 순차 실행 모니터링</h3>
        {taskStatus === "running" && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>● Running</span>}
        {taskStatus === "completed" && <span style={{ color: "#60a5fa", fontSize: "0.8rem" }}>✓ Done</span>}
        {taskStatus === "failed" && <span style={{ color: "#f87171", fontSize: "0.8rem" }}>✕ Fail</span>}
      </div>
      <div style={{ padding: "0.8rem", height: "200px", overflowY: "auto", fontFamily: "monospace", fontSize: "0.8rem", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
        {statusLogs.map((log, i) => (
          <div key={i} style={{ color: log.includes("✅") ? "#34d399" : log.includes("⚠️") ? "#fbbf24" : "#cbd5e1" }}>
            {log}
          </div>
        ))}
      </div>
    </div>
  );
}


export default function MultiTaskPage() {
  const [accounts, setAccounts] = useState([{ id: "", pw: "" }]);
  const [targetTask, setTargetTask] = useState("blog"); // "blog", "cafe", "communication"
  
  // Blog specific (simplified for Multi-task prototype)
  const [targetKeyword, setTargetKeyword] = useState("");
  const [aiProvider, setAiProvider] = useState("claude");
  
  const [useTethering, setUseTethering] = useState(false);
  const [scheduleTime, setScheduleTime] = useState("");
  
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const savedAccounts = localStorage.getItem("mbam_saved_accounts");
    if (savedAccounts) {
      try {
        setAccounts(JSON.parse(savedAccounts));
      } catch (e) {
        console.error("Failed to parse saved accounts", e);
      }
    }
  }, []);

  const saveAccounts = () => {
    localStorage.setItem("mbam_saved_accounts", JSON.stringify(accounts));
    alert("입력하신 계정 정보가 브라우저에 안전하게 저장되었습니다.");
  };

  const handleAddAccount = () => {
    setAccounts([...accounts, { id: "", pw: "" }]);
  };

  const handleRemoveAccount = (index) => {
    setAccounts(accounts.filter((_, i) => i !== index));
  };

  const handleAccountChange = (index, field, value) => {
    const newAccounts = [...accounts];
    newAccounts[index][field] = value;
    setAccounts(newAccounts);
  };

  const handleStartMultiTask = async () => {
    const validAccounts = accounts.filter(a => a.id && a.pw);
    if (validAccounts.length === 0) {
      alert("최소 1개 이상의 네이버 계정(ID/PW)을 입력해주세요.");
      return;
    }
    if (!targetKeyword) {
      alert("공통 실행할 타겟 키워드를 입력해주세요.");
      return;
    }

    setLoading(true);
    setActiveTaskId(null);

    try {
      const payload = {
        target_task: targetTask,
        accounts: validAccounts.map(a => ({ id: a.id, pw: a.pw, keyword: targetKeyword, ai_provider: aiProvider })),
        global_config: { 
          keyword: targetKeyword, 
          ai_provider: aiProvider,
          use_tethering: useTethering,
          schedule_time: scheduleTime || null
        }
      };
      
      const res = await fetchWithAuth("/api/multi_task/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      if (data.success && data.task_id) {
        setActiveTaskId(data.task_id);
      } else {
        alert("작업 시작에 실패했습니다.");
      }
    } catch (e) {
      console.error("Task trigger failed", e);
      alert("서버 오류가 발생했습니다.");
    }
    
    setLoading(false);
  };

  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div>
        <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "0.5rem" }}>멀티 계정 실행 (순차 모드)</h1>
        <p style={{ color: "#64748b", margin: 0 }}>여러 개의 네이버 계정으로 똑같은 작업(포스팅/소통)을 <b>프록시(테더링) 변경과 딜레이를 주며 안전하게 순차 실행</b>합니다.</p>
      </div>

      <div style={{ display: "flex", gap: "2rem" }}>
        {/* Left: Accounts Setup */}
        <div style={{ flex: 1, background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>계정 리스트</h2>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button onClick={saveAccounts} style={{ padding: "0.4rem 0.8rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.9rem" }}>💾 저장</button>
              <button onClick={handleAddAccount} style={{ padding: "0.4rem 0.8rem", background: "#f1f5f9", border: "1px solid #cbd5e1", cursor: "pointer", fontSize: "0.9rem" }}>+ 추가</button>
            </div>
          </div>
          
          <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
            {accounts.map((acc, i) => (
              <div key={i} style={{ display: "flex", gap: "0.5rem" }}>
                <input 
                  type="text" placeholder={`ID ${i+1}`} value={acc.id} onChange={e => handleAccountChange(i, 'id', e.target.value)} 
                  style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1" }} 
                />
                <input 
                  type="password" placeholder={`PW ${i+1}`} value={acc.pw} onChange={e => handleAccountChange(i, 'pw', e.target.value)} 
                  style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1" }} 
                />
                {accounts.length > 1 && (
                  <button onClick={() => handleRemoveAccount(i)} style={{ padding: "0.6rem", background: "#fee2e2", color: "#ef4444", border: "1px solid #fca5a5", cursor: "pointer" }}>X</button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Job Setup */}
        <div style={{ flex: 1, background: "white", padding: "1.5rem", border: "1px solid #cbd5e1", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", marginBottom: "1rem" }}>공통 실행 작업</h2>
            <select value={targetTask} onChange={e => setTargetTask(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", fontSize: "1rem" }}>
              <option value="blog">블로그 AI 포스팅 자동화</option>
              <option value="cafe">카페 포스팅/댓글 자동화</option>
              <option value="communication">블로그 소통 & 이웃 자동화</option>
            </select>
          </div>
          
          <div>
            <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>타겟 키워드 (각 계정별로 AI가 다르게 변형하여 작성합니다)</label>
            <input 
              type="text" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} placeholder="예: 부산 맛집" 
              style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} 
            />
          </div>

          <div>
            <label style={{ display: "block", marginBottom: "0.5rem", fontSize: "0.9rem", color: "#475569", fontWeight: "bold" }}>AI 작성 엔진 선택</label>
            <select 
              value={aiProvider} 
              onChange={e => setAiProvider(e.target.value)}
              style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", background: "white", outline: "none" }}
            >
              <option value="claude">Claude (추천/고품질)</option>
              <option value="gemini">Gemini (빠름/무료)</option>
              <option value="openai">ChatGPT (OpenAI)</option>
            </select>
          </div>

          <div style={{ padding: "1rem", background: "#f8fafc", border: "1px solid #e2e8f0" }}>
            <h3 style={{ margin: "0 0 0.8rem 0", fontSize: "1rem", color: "#334155" }}>고급 설정</h3>
            
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", cursor: "pointer", fontWeight: "bold" }}>
              <input type="checkbox" checked={useTethering} onChange={e => setUseTethering(e.target.checked)} style={{ transform: "scale(1.2)" }} />
              📱 USB 테더링 IP 우회 사용 (스마트폰 연결 필요)
            </label>
            
            <div>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>매일 자동 실행 예약 (선택 사항)</label>
              <input 
                type="time" 
                value={scheduleTime} 
                onChange={e => setScheduleTime(e.target.value)} 
                style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} 
              />
              <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0.5rem 0 0 0" }}>시간을 설정하면 지금 즉시 실행되지 않고, 설정한 시간에 매일 반복 실행됩니다.</p>
            </div>
          </div>

          <button 
            onClick={handleStartMultiTask} 
            disabled={loading}
            style={{ 
              marginTop: "auto",
              padding: "1rem", 
              background: loading ? "#94a3b8" : "#2563eb", 
              color: "white", 
              fontWeight: "bold", 
              fontSize: "1.1rem",
              border: "none", 
              cursor: loading ? "wait" : "pointer" 
            }}>
            {loading ? "작업 지시 중..." : `🚀 ${accounts.filter(a=>a.id).length}개 계정 순차 실행하기`}
          </button>
        </div>
      </div>

      {/* Monitoring Panel */}
      {activeTaskId && (
        <div style={{ marginTop: "1rem" }}>
          <h2 style={{ fontSize: "1.2rem", fontWeight: "bold", marginBottom: "1rem", color: "#1e293b" }}>모니터링 패널</h2>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <TaskMonitorCard taskId={activeTaskId} />
          </div>
        </div>
      )}
    </div>
  );
}