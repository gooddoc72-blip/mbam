"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";

function BlogAutoContent() {
  // 1. Account Settings
  const [accounts, setAccounts] = useState([{ id: "", pw: "" }]);
  const [intervalMins, setIntervalMins] = useState(5);

  const addAccount = () => setAccounts([...accounts, { id: "", pw: "" }]);
  const removeAccount = (index) => setAccounts(accounts.filter((_, i) => i !== index));
  const updateAccount = (index, field, value) => {
    const newAcc = [...accounts];
    newAcc[index][field] = value;
    setAccounts(newAcc);
  };

  // 2. Content Settings
  const [targetKeyword, setTargetKeyword] = useState("");
  const [aiProvider, setAiProvider] = useState("claude");
  const [referenceData, setReferenceData] = useState(null);

  // Generated Contents & Manual Contents
  // For AI, we hold an array of { account_id, title, content }
  const [generatedContents, setGeneratedContents] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);

  // 3. Image Settings
  const [washImages, setWashImages] = useState(true);
  const [imageUploadMode, setImageUploadMode] = useState("folder"); // "folder" or "direct"
  const [imageFolderPath, setImageFolderPath] = useState("");
  const [directImages, setDirectImages] = useState("");

  // 4. Publish Settings
  const [publishMode, setPublishMode] = useState("instant");
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [statusLogs, setStatusLogs] = useState([]);
  const [taskStatus, setTaskStatus] = useState(""); 
  const [generateCardNews, setGenerateCardNews] = useState(true);
  
  const searchParams = useSearchParams();
  const initKeyword = searchParams?.get("keyword") || "";
  const sourceData = searchParams?.get("source_data") || null;

  // Initialize keyword from query
  useEffect(() => {
    if (initKeyword && !targetKeyword) {
      setTargetKeyword(initKeyword);
    }
  }, [initKeyword]);

  // Status Polling
  useEffect(() => {
    let intervalId;
    if (taskId && taskStatus !== "completed" && taskStatus !== "failed") {
      intervalId = setInterval(async () => {
        try {
          const res = await fetchWithAuth(`/api/auto_post/status/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            setStatusLogs(data.logs || []);
            setTaskStatus(data.status);
            if (data.status === "completed" || data.status === "failed") {
              setLoading(false);
            }
          }
        } catch (e) {
          console.error("Status check failed", e);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [taskId, taskStatus]);

  const handleGenerateContent = async () => {
    if (!targetKeyword) {
      alert("타겟 키워드를 입력해주세요.");
      return;
    }
    const validAccounts = accounts.filter(a => a.id.trim() !== "");
    if (validAccounts.length === 0) {
      alert("원고를 생성할 계정을 최소 1개 이상 입력해주세요.");
      return;
    }

    setIsGenerating(true);
    setGeneratedContents([]);
    try {
      const payload = {
        accounts: validAccounts,
        target_keyword: targetKeyword,
        ai_provider: aiProvider,
        reference_data: referenceData,
        source_data: sourceData,
        generate_card_news: generateCardNews
      };
      const res = await fetchWithAuth("/api/auto_post/generate-content", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        setGeneratedContents(data.generated_contents);
      } else {
        alert("원고 생성에 실패했습니다.");
      }
    } catch (e) {
      alert("서버 오류가 발생했습니다.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleUpdateGeneratedContent = (index, field, value) => {
    const newContents = [...generatedContents];
    newContents[index][field] = value;
    setGeneratedContents(newContents);
  };

  const handleStartAutomation = async () => {
    const validAccounts = accounts.filter(a => a.id.trim() !== "");
    if (validAccounts.length === 0) {
      alert("계정을 1개 이상 입력해주세요.");
      return;
    }
    
    // Check if generated contents exist
    if (generatedContents.length === 0) {
      alert("먼저 AI 원고를 생성해주세요.");
      return;
    }

    setLoading(true);
    setStatusLogs([]);
    setTaskStatus("running");
    
    try {
      const payload = {
        target_type: "blog",
        accounts: validAccounts,
        interval_mins: parseInt(intervalMins) || 0,
        wash_images: washImages,
        image_folder_path: imageUploadMode === "folder" ? imageFolderPath : null,
        images: imageUploadMode === "direct" ? directImages.split("\n").filter(p => p.trim()) : [],
        post_mode: "manual_text",
        generated_contents: generatedContents,
        publish_mode: publishMode,
        schedule_date: scheduleDate,
        schedule_time: scheduleTime,
        source_data: sourceData,
        generate_card_news: generateCardNews
      };      const res = await fetchWithAuth("/api/auto_post/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success && data.task_id) {
        setTaskId(data.task_id);
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
      
      {/* Left Control Panel */}
      <div style={{ flex: 2, display: "flex", flexDirection: "column", gap: "1.5rem", overflowY: "auto", paddingRight: "10px" }}>
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "0.5rem" }}>블로그 자동화 (글감수집 연동)</h1>
          <p style={{ color: "#64748b", margin: 0 }}>글감 수집 데이터를 기반으로 이미지가 없을 시 AI 카드뉴스도 자동 생성합니다.</p>
        </div>

        {/* 1. Account Settings */}
        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>1. 네이버 다중 계정 설정</h2>
            <button onClick={addAccount} style={{ padding: "0.4rem 0.8rem", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "4px", cursor: "pointer" }}>+ 계정 추가</button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
            {accounts.map((acc, idx) => (
              <div key={idx} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <span style={{ width: "20px", fontWeight: "bold", color: "#64748b" }}>{idx+1}.</span>
                <input type="text" placeholder="네이버 아이디" value={acc.id} onChange={(e) => updateAccount(idx, "id", e.target.value)} style={{ padding: "0.6rem", border: "1px solid #cbd5e1", flex: 1 }} />
                <input type="password" placeholder="비밀번호" value={acc.pw} onChange={(e) => updateAccount(idx, "pw", e.target.value)} style={{ padding: "0.6rem", border: "1px solid #cbd5e1", flex: 1 }} />
                {accounts.length > 1 && (
                  <button onClick={() => removeAccount(idx)} style={{ padding: "0.6rem", background: "#fee2e2", color: "#ef4444", border: "none", cursor: "pointer" }}>삭제</button>
                )}
              </div>
            ))}
          </div>
          <div style={{ marginTop: "1rem", display: "flex", alignItems: "center", gap: "1rem", background: "#f8fafc", padding: "1rem", border: "1px solid #e2e8f0" }}>
            <span style={{ fontWeight: "bold", color: "#475569" }}>계정 간 발행 텀 (딜레이):</span>
            <input type="number" value={intervalMins} onChange={e => setIntervalMins(e.target.value)} style={{ width: "60px", padding: "0.4rem", border: "1px solid #cbd5e1", textAlign: "center" }} />
            <span style={{ color: "#64748b" }}>분 대기 후 다음 계정 발행</span>
          </div>
        </div>

        {/* 2. Image Settings */}
        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>2. 이미지 설정</h2>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
             <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: washImages ? "#3b82f6" : "#64748b" }}>
               <input type="checkbox" checked={washImages} onChange={e => setWashImages(e.target.checked)} style={{ transform: "scale(1.2)" }} />
               ✨ 이미지 자동 세탁 적용 (메타데이터 제거 및 노이즈 추가)
             </label>
          </div>
          <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input type="radio" checked={imageUploadMode === "folder"} onChange={() => setImageUploadMode("folder")} />
              <span>로컬 PC 폴더 연동 (추천)</span>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input type="radio" checked={imageUploadMode === "direct"} onChange={() => setImageUploadMode("direct")} />
              <span>이미지 절대 경로 직접 입력</span>
            </label>
          </div>
          {imageUploadMode === "folder" ? (
            <div>
              <input type="text" value={imageFolderPath} onChange={e => setImageFolderPath(e.target.value)} placeholder="예: C:\Users\Images\Cafe (서버 PC 기준 폴더 경로)" style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
              <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0.5rem 0 0 0" }}>* 폴더에 이미지가 있다면 최대 3장 추출, 폴더가 비어있거나 없으면 아래 설정에 따라 카드뉴스를 생성합니다.</p>
            </div>
          ) : (
            <textarea value={directImages} onChange={e => setDirectImages(e.target.value)} placeholder="C:\images\img1.jpg (엔터로 구분)" style={{ width: "100%", height: "80px", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box", resize: "vertical" }} />
          )}
          
          <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "8px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: "#166534" }}>
              <input type="checkbox" checked={generateCardNews} onChange={e => setGenerateCardNews(e.target.checked)} style={{ transform: "scale(1.2)" }} />
              🎨 업로드할 이미지가 없을 경우 AI 카드뉴스 자동 생성
            </label>
            <p style={{ fontSize: "0.85rem", color: "#15803d", margin: "0.5rem 0 0 0" }}>
              * 백엔드의 AI 이미지 생성기를 호출하여 원고 내용에 맞는 정보성 카드뉴스를 생성한 후 포스팅에 첨부합니다.
            </p>
          </div>
        </div>

        {/* 3. Content Settings */}
        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>3. 원고 설정 (다중 스핀 지원)</h2>
          
          <div style={{ padding: "1rem", background: "#f8fafc", color: "#334155", fontSize: "0.95rem", border: "1px solid #e2e8f0", marginBottom: "1.5rem" }}>
            {sourceData ? (
              <span><strong>✅ 글감 수집 데이터 연동 완료!</strong><br />수집된 정보를 바탕으로 AI가 최적의 원고를 창작합니다.</span>
            ) : (
              <span>글감 수집 메뉴에서 선택하신 데이터를 기반으로 자동 포스팅합니다. 현재 직접 키워드를 입력해 생성할 수도 있습니다.</span>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>타겟 키워드 (필수)</label>
              <input type="text" placeholder="예: 강남역 맛집, 서울 카페 추천" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>AI 작성 엔진 선택</label>
              <select value={aiProvider} onChange={e => setAiProvider(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1" }}>
                <option value="claude">Claude (추천/고품질)</option>
                <option value="gemini">Gemini (빠름/무료)</option>
                <option value="openai">ChatGPT (OpenAI)</option>
              </select>
            </div>
            
            <button onClick={handleGenerateContent} disabled={isGenerating} style={{ padding: "1rem", background: "#2563eb", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", borderRadius: "6px", cursor: isGenerating ? "wait" : "pointer", marginTop: "1rem" }}>
              {isGenerating ? "AI가 각 계정별 원고를 창작 중입니다..." : "AI 다중 원고 자동 생성하기"}
            </button>
          </div>

          {/* AI Generated Contents Review Section */}
          {generatedContents.length > 0 && (
            <div style={{ marginTop: "2rem", borderTop: "2px dashed #cbd5e1", paddingTop: "1.5rem" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", marginBottom: "1rem" }}>✅ 생성된 계정별 원고 검토 및 수정</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                {generatedContents.map((gc, idx) => (
                  <div key={idx} style={{ background: "#f8fafc", padding: "1rem", border: "1px solid #e2e8f0" }}>
                    <div style={{ fontWeight: "bold", color: "#2563eb", marginBottom: "0.8rem" }}>▶ [{accounts[idx]?.id || "계정 미정"}] 에 발행될 원고</div>
                    <input type="text" value={gc.title} onChange={(e) => handleUpdateGeneratedContent(idx, "title", e.target.value)} style={{ width: "100%", padding: "0.6rem", border: "1px solid #cbd5e1", boxSizing: "border-box", marginBottom: "0.5rem", fontWeight: "bold" }} />
                    <textarea value={gc.content} onChange={(e) => handleUpdateGeneratedContent(idx, "content", e.target.value)} style={{ width: "100%", height: "150px", padding: "0.6rem", border: "1px solid #cbd5e1", boxSizing: "border-box", resize: "vertical" }} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Publish Action */}
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginTop: "1rem" }}>
          <select value={publishMode} onChange={e => setPublishMode(e.target.value)} style={{ padding: "0.8rem", border: "1px solid #0f172a", fontWeight: "bold", outline: "none" }}>
            <option value="instant">🚀 즉시 발행</option>
            <option value="schedule">⏰ 예약 발행</option>
          </select>
          
          {publishMode === "schedule" && (
            <>
              <input type="date" value={scheduleDate} onChange={e => setScheduleDate(e.target.value)} style={{ padding: "0.8rem", border: "1px solid #cbd5e1" }} />
              <input type="time" value={scheduleTime} onChange={e => setScheduleTime(e.target.value)} style={{ padding: "0.8rem", border: "1px solid #cbd5e1" }} />
            </>
          )}

          <button 
            onClick={handleStartAutomation} 
            disabled={loading}
            style={{ 
              flex: 1, padding: "1rem", background: loading ? "#94a3b8" : "#0f172a", color: "white", 
              fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: loading ? "wait" : "pointer" 
            }}>
            {loading ? "다중 포스팅 작업 중..." : "다중 계정 자동 포스팅 시작하기"}
          </button>
        </div>
      </div>

      {/* Right Monitoring Panel */}
      <div style={{ flex: 1, background: "#1e293b", border: "1px solid #0f172a", display: "flex", flexDirection: "column", color: "#f8fafc" }}>
        <div style={{ padding: "1rem", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0, color: "#f8fafc" }}>실시간 작업 로그</h2>
          {taskStatus === "running" && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>● Running</span>}
          {taskStatus === "completed" && <span style={{ color: "#60a5fa", fontSize: "0.8rem" }}>✓ Completed</span>}
        </div>
        <div style={{ flex: 1, padding: "1rem", overflowY: "auto", fontFamily: "monospace", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {statusLogs.length === 0 ? (
            <div style={{ color: "#94a3b8" }}>작업을 시작하면 로그가 표시됩니다.</div>
          ) : (
            statusLogs.map((log, i) => (
              <div key={i} style={{ color: log.includes("✅") ? "#34d399" : log.includes("⚠️") || log.includes("❌") ? "#fbbf24" : "#cbd5e1" }}>
                {log}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function BlogAutoPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <BlogAutoContent />
    </Suspense>
  );
}

