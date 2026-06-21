"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";

function BlogPostingContent() {

  // 1. Account Settings
  const searchParams = useSearchParams();
  const [generateCardNews, setGenerateCardNews] = useState(true);
  const [sourceData, setSourceData] = useState("");

  const [accounts, setAccounts] = useState([{ id: "", pw: "" }]);
  const [intervalMins, setIntervalMins] = useState(5);
  const [useTethering, setUseTethering] = useState(false);

  const addAccount = () => setAccounts([...accounts, { id: "", pw: "" }]);
  const removeAccount = (index) => setAccounts(accounts.filter((_, i) => i !== index));
  const updateAccount = (index, field, value) => {
    const newAcc = [...accounts];
    newAcc[index][field] = value;
    setAccounts(newAcc);
  };

  const saveAccounts = () => {
    localStorage.setItem("mbam_saved_accounts", JSON.stringify(accounts));
    alert("입력하신 계정 정보가 브라우저에 안전하게 저장되었습니다.");
  };

  // 2. Content Settings
  const [targetKeyword, setTargetKeyword] = useState("");
  const [productUrl, setProductUrl] = useState("");
  const [extractUrlImages, setExtractUrlImages] = useState(false);
  const [aiProvider, setAiProvider] = useState("claude");
  const [postPurpose, setPostPurpose] = useState("review");
  const [promoType, setPromoType] = useState("product");
  const [distributionMode, setDistributionMode] = useState("normal");
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

  // 5. Saved Manuscripts Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedManuscriptIds, setSelectedManuscriptIds] = useState([]);
  const [savedManuscripts, setSavedManuscripts] = useState([]);
  const [isLoadingManuscripts, setIsLoadingManuscripts] = useState(false);

  const handleSelectFolder = async (e) => {
    e.preventDefault();
    try {
      const res = await fetchWithAuth("/api/settings/select-folder");
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setImageFolderPath(data.path);
        } else {
          alert("선택된 폴더가 없습니다.");
        }
      } else {
        alert("백엔드 응답 오류: " + res.status);
      }
    } catch (e) {
      alert("네트워크 오류: " + e.message);
    }
  };


  // Fetch referenceData from localStorage if it exists (from SEO Analyzer)
  useEffect(() => {
    const savedSource = localStorage.getItem('autoWriteSourceData');
    if (savedSource) {
      setSourceData(savedSource);
    } else if (searchParams) {
      const paramSource = searchParams.get("source_data");
      if (paramSource) {
        setSourceData(paramSource);
      }
    }

    const saved = localStorage.getItem('autoWriteRefData');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.keyword) setTargetKeyword(parsed.keyword);
        if (parsed.formula || parsed.references) {
          setReferenceData(parsed);
        }
      } catch(e) {
        console.error("Failed to parse autoWriteRefData", e);
      }
    }
    
    const savedAccounts = localStorage.getItem("mbam_saved_accounts");
    if (savedAccounts) {
      try {
        setAccounts(JSON.parse(savedAccounts));
      } catch (e) {
        console.error("Failed to parse saved accounts", e);
      }
    }

    const savedTaskId = localStorage.getItem("mbam_auto_post_task_id");
    if (savedTaskId) {
      setTaskId(savedTaskId);
      setTaskStatus("running");
      setLoading(true);
    }
  }, []);


  const loadAccounts = () => {
    const savedAccounts = localStorage.getItem("mbam_saved_accounts");
    if (savedAccounts) {
      try {
        setAccounts(JSON.parse(savedAccounts));
        alert("멀티실행메뉴에서 저장된 계정을 성공적으로 불러왔습니다.");
      } catch (e) {
        console.error("Failed to parse saved accounts", e);
      }
    } else {
      alert("저장된 다중 계정이 없습니다. 멀티 태스크 메뉴에서 계정을 먼저 저장해주세요.");
    }
  };

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
            if (data.status === "completed" || data.status === "failed" || data.status === "not_found") {
              setLoading(false);
              clearInterval(intervalId);
              localStorage.removeItem("mbam_auto_post_task_id");
              if (data.status === "not_found") {
                setStatusLogs(["서버가 재시작되어 기존 작업을 찾을 수 없습니다."]);
              }
            }
          } else if (res.status === 404) {
            setLoading(false);
            setTaskStatus("failed");
            clearInterval(intervalId);
            localStorage.removeItem("mbam_auto_post_task_id");
          }
        } catch (e) {
          console.error("Status check failed", e);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [taskId, taskStatus]);

  // Web Save & Load Functions
  const fetchManuscripts = async () => {
    setIsLoadingManuscripts(true);
    try {
      const res = await fetchWithAuth("/api/manuscripts");
      if (res.ok) {
        const data = await res.json();
        setSavedManuscripts(data);
      }
    } catch (e) {
      console.error("Failed to fetch manuscripts", e);
    } finally {
      setIsLoadingManuscripts(false);
    }
  };

  const openManuscriptModal = () => {
    setIsModalOpen(true);
    setSelectedManuscriptIds([]);
    fetchManuscripts();
  };

  const toggleManuscriptSelection = (id) => {
    setSelectedManuscriptIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const loadSelectedManuscripts = () => {
    const selected = savedManuscripts.filter(m => selectedManuscriptIds.includes(m.id));
    // Convert to the format expected by generatedContents
    const newContents = selected.map(m => ({ title: m.title, content: m.content, keyword: m.keyword }));
    setGeneratedContents([...generatedContents, ...newContents]);
    alert(`${newContents.length}개의 글감이 추가되었습니다.`);
    setIsModalOpen(false);
  };

  const saveManuscriptToWeb = async (idx) => {
    const gc = generatedContents[idx];
    const accountId = accounts[idx]?.id || "";
    try {
      const payload = {
        title: gc.title,
        content: gc.content,
        keyword: targetKeyword,
        account_id: accountId
      };
      const res = await fetchWithAuth("/api/manuscripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        alert("원고가 웹(서버)에 안전하게 저장되었습니다.");
      } else {
        alert("저장에 실패했습니다.");
      }
    } catch (e) {
      alert("서버 오류: " + e.message);
    }
  };

  const deleteManuscriptFromWeb = async (id) => {
    if (!confirm("정말 이 원고를 삭제하시겠습니까?")) return;
    try {
      const res = await fetchWithAuth(`/api/manuscripts/${id}`, { method: "DELETE" });
      if (res.ok) {
        setSavedManuscripts(savedManuscripts.filter(m => m.id !== id));
      }
    } catch (e) {
      alert("삭제 실패: " + e.message);
    }
  };

  const loadManuscriptToWorkspace = (manuscript) => {
    setGeneratedContents([...generatedContents, { title: manuscript.title, content: manuscript.content }]);
    alert("원고가 맨 아래 추가되었습니다.");
    setIsModalOpen(false);
  };

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
        product_url: productUrl,
        extract_url_images: extractUrlImages,
        ai_provider: aiProvider,
        post_purpose: sourceData ? "info" : postPurpose,
        promo_type: sourceData ? "info" : promoType,
        distribution_mode: distributionMode,

        reference_data: referenceData,
        generate_card_news: generateCardNews,
        source_data: sourceData,
        post_mode: "ai_generate",

        login_mode: "manual",
        publish_mode: "instant",
        target_type: "blog",
        cafe_action_type: "post"
      };
      const res = await fetchWithAuth("/next_api/auto_post/generate-content", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errText = await res.text();
        alert(`서버 응답 오류: ${res.status} - ${errText}`);
        return;
      }
      const data = await res.json();
      if (data.success) {
        setGeneratedContents(data.generated_contents);
        if (data.scraped_image_folder) {
          setImageUploadMode("folder");
          setImageFolderPath(data.scraped_image_folder);
          alert("✅ 원고 생성 완료! 타겟 URL에서 이미지 수집도 성공하여 이미지 폴더가 자동 지정되었습니다.");
        }
      } else {
        alert("원고 생성에 실패했습니다: " + JSON.stringify(data));
      }
    } catch (e) {
      alert("서버 연결 실패 또는 예외 발생: " + e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleUpdateGeneratedContent = (index, field, value) => {
    const newContents = [...generatedContents];
    newContents[index][field] = value;
    setGeneratedContents(newContents);
  };

  const handleDownloadSingle = (idx) => {
    const gc = generatedContents[idx];
    const accountId = accounts[idx]?.id || `account_${idx + 1}`;
    const text = `제목: ${gc.title}\n\n${gc.content}`;
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `원고_${accountId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadAll = () => {
    generatedContents.forEach((gc, idx) => {
      handleDownloadSingle(idx);
    });
  };

  const handleAddBlankManuscript = () => {
    setGeneratedContents([...generatedContents, { title: "직접 작성한 원고", content: "" }]);
  };

  const handleLoadLocalFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      const text = evt.target.result;
      const lines = text.split('\n');
      const titleLine = lines.find(l => l.trim().length > 0) || file.name;
      const title = titleLine.replace(/^제목:\s*/, '').trim();
      setGeneratedContents([...generatedContents, { title: title, content: text }]);
    };
    reader.readAsText(file, "utf-8");
    e.target.value = "";
  };

  const handleDeleteManuscript = (idx) => {
    if (!window.confirm("이 원고를 삭제하시겠습니까?")) return;
    setGeneratedContents(generatedContents.filter((_, i) => i !== idx));
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
        post_mode: "manual_text", // We always send generated contents as manual_text now
        generated_contents: generatedContents.map((gc, idx) => ({ ...gc, account_id: validAccounts[idx]?.id })),
        publish_mode: publishMode,
        schedule_date: scheduleDate,
        schedule_time: scheduleTime,
        use_tethering: useTethering,
        generate_card_news: generateCardNews
      };      const res = await fetchWithAuth("/api/auto_post/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success && data.task_id) {
        setTaskId(data.task_id);
        localStorage.setItem("mbam_auto_post_task_id", data.task_id);
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

  const handleCancelTask = async () => {
    if (!taskId) return;
    if (!window.confirm("정말 진행 중인 작업을 중단하시겠습니까?")) return;
      try {
        const res = await fetchWithAuth(`/api/auto_post/cancel/${taskId}`, { method: "POST" });
        if (!res.ok) {
           throw new Error("서버에서 오류를 반환했습니다. (백엔드 서버가 켜져 있는지 확인해주세요)");
        }
        const data = await res.json();
        if (data.success) {
          setTaskStatus("failed");
          setLoading(false);
        } else {
          alert(data.message || "작업 중지에 실패했습니다.");
        }
      } catch (e) {
        alert("작업 중지 오류: " + e.message);
      }
  };

  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "2rem", minHeight: "100vh", boxSizing: "border-box" }}>
      
      {/* Top Section: Left Control Panel & Right Generated Contents */}
      <div style={{ display: "flex", gap: "2rem", flex: 1, minHeight: 0 }}>
        
        {/* Left Control Panel */}
        <div style={{ flex: 1.5, display: "flex", flexDirection: "column", gap: "1.5rem", paddingRight: "10px" }}>
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "0.5rem" }}>블로그 자동 포스팅</h1>
          <p style={{ color: "#64748b", margin: 0 }}>SEO 분석 및 글감 수집 데이터를 기반으로 다중 계정에 원고를 자동 발행합니다.</p>
        </div>

        {/* 1. Account Settings */}
        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>1. 네이버 다중 계정 설정</h2>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button onClick={loadAccounts} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>📥 불러오기</button>
              <button onClick={saveAccounts} style={{ padding: "0.4rem 0.8rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>💾 계정 저장</button>
              <button onClick={addAccount} style={{ padding: "0.4rem 0.8rem", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "4px", cursor: "pointer" }}>+ 계정 추가</button>
            </div>
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
          <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "1rem", background: "#f8fafc", padding: "1rem", border: "1px solid #e2e8f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <span style={{ fontWeight: "bold", color: "#475569" }}>계정 간 발행 텀 (딜레이):</span>
              <input type="number" value={intervalMins} onChange={e => setIntervalMins(e.target.value)} style={{ width: "60px", padding: "0.4rem", border: "1px solid #cbd5e1", textAlign: "center" }} />
              <span style={{ color: "#64748b" }}>분 대기 후 다음 계정 발행</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: useTethering ? "#3b82f6" : "#64748b" }}>
                <input type="checkbox" checked={useTethering} onChange={e => setUseTethering(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                📱 안드로이드 USB 테더링 (비행기 모드 자동 토글) 사용
              </label>
              <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>* PC와 폰이 USB로 연결되어 있고, USB 테더링이 켜져 있어야 합니다.</span>
            </div>
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
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <input type="text" value={imageFolderPath} onChange={e => setImageFolderPath(e.target.value)} placeholder="예: C:\Users\Images\Cafe (서버 PC 기준 폴더 경로)" style={{ flex: 1, padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                <button type="button" onClick={handleSelectFolder} style={{ padding: "0 1rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>
                  🔍 폴더 찾기
                </button>
              </div>
              <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0.5rem 0 0 0" }}>* 봇이 해당 폴더에서 이미지를 랜덤하게(최대 3장) 골라 업로드합니다.</p>
            </div>
          ) : (
            <textarea value={directImages} onChange={e => setDirectImages(e.target.value)} placeholder="C:\images\img1.jpg (엔터로 구분)" style={{ width: "100%", height: "80px", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box", resize: "vertical" }} />
          )}

          <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#ecfdf5", borderRadius: "8px", border: "1px solid #a7f3d0" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: "#065f46" }}>
              <input type="checkbox" checked={generateCardNews} onChange={e => setGenerateCardNews(e.target.checked)} style={{ transform: "scale(1.2)" }} />
              🎨 업로드할 이미지가 없을 경우 AI 카드뉴스 자동 생성
            </label>
            <p style={{ margin: "0.5rem 0 0 1.5rem", fontSize: "0.85rem", color: "#047857" }}>* 백엔드의 AI 이미지 생성기를 호출하여 원고 내용에 맞는 정보성 카드뉴스를 생성한 후 포스팅에 첨부합니다.</p>
          </div>
        </div>

        {/* 3. Content Settings */}
        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem", color: "#334155" }}>3. 원고 설정 (다중 스핀 지원)</h2>
          
          <div style={{ padding: "1rem", background: "#f8fafc", color: "#334155", fontSize: "0.95rem", border: "1px solid #e2e8f0", marginBottom: "1.5rem" }}>
            SEO 분석기가 타겟 키워드의 상위 노출 승리 공식을 분석하고, 선택하신 <strong>포스팅 목적</strong>과 <strong>홍보 카테고리</strong>에 맞춰 AI가 최적의 원고를 100% 창작하여 포스팅합니다.
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            
            {sourceData && (
              <div style={{ marginBottom: "1rem", padding: "1rem", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <h4 style={{ margin: "0 0 0.5rem 0", color: "#334155" }}>📝 수집된 글감 데이터 (이 데이터로 자동 작성됩니다)</h4>
                <textarea readOnly value={sourceData} style={{ width: "100%", height: "100px", padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "4px", backgroundColor: "#f1f5f9", fontSize: "0.9rem", color: "#475569" }} />
                <button type="button" onClick={() => { setSourceData(""); localStorage.removeItem('autoWriteSourceData'); }} style={{ marginTop: "0.5rem", padding: "0.5rem 1rem", background: "#ef4444", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>글감 데이터 지우기 (직접 입력 모드로 전환)</button>
              </div>
            )}
            <div style={{ display: "flex", gap: "1rem" }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>타겟 키워드 (필수)</label>
                <input type="text" placeholder="예: 강남역 맛집, 서울 카페 추천" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>타겟 상품 URL (선택)</label>
                <input type="text" placeholder="예: https://smartstore.naver.com/..." value={productUrl} onChange={e => setProductUrl(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.5rem", cursor: "pointer", fontSize: "0.85rem", color: extractUrlImages ? "#2563eb" : "#64748b" }}>
                  <input type="checkbox" checked={extractUrlImages} onChange={e => setExtractUrlImages(e.target.checked)} />
                  ✨ 타겟 URL에서 상품 이미지 자동 수집하여 사용하기
                </label>
              </div>
            </div>

              <div>
                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>AI 생성 엔진 선택</label>
                <select value={aiProvider} onChange={e => setAiProvider(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1" }}>
                  <option value="claude">Claude (추천/고품질)</option>
                  <option value="gemini">Gemini (빠름/무료)</option>
                  <option value="openai">ChatGPT (OpenAI)</option>
                </select>
              </div>

            {sourceData ? (
              <div style={{ marginBottom: "1rem", padding: "1.5rem", background: "#f0fdf4", borderRadius: "8px", border: "1px solid #bbf7d0" }}>
                <h4 style={{ margin: "0 0 0.5rem 0", color: "#166534", fontSize: "1.1rem" }}>💡 블로그 지수 향상을 위한 1일 1포스팅 모드 작동 중</h4>
                <p style={{ margin: 0, fontSize: "0.95rem", color: "#15803d", lineHeight: "1.5" }}>
                  현재 수집된 글감 데이터가 존재하여 <strong>[정보성 포스팅]</strong> 모드로 자동 전환되었습니다.<br/>
                  이 모드에서는 상업적인 리뷰나 홍보 목적이 아닌, 블로그 방문자 유입과 지수 상승을 위한 양질의 정보글을 작성하게 됩니다.
                </p>
              </div>
            ) : (
              <>
                <div>
                  <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>포스팅 목적</label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                    <div onClick={() => setPostPurpose("review")} style={{ padding: "1rem", border: postPurpose === "review" ? "2px solid #22c55e" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: postPurpose === "review" ? "#f0fdf4" : "white" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>📝</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem" }}>리뷰용</div>
                      <div style={{ fontSize: "0.8rem", color: "#64748b" }}>방문 후 본인 후기 작성</div>
                    </div>
                    <div onClick={() => setPostPurpose("intro")} style={{ padding: "1rem", border: postPurpose === "intro" ? "2px solid #22c55e" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: postPurpose === "intro" ? "#f0fdf4" : "white" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>📢</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem" }}>홍보용</div>
                      <div style={{ fontSize: "0.8rem", color: "#64748b" }}>방문 없이 매장·상품 소개</div>
                    </div>
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>블로그 홍보 유형</label>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.5rem" }}>
                    <div onClick={() => setPromoType("product")} style={{ padding: "1rem 0.5rem", border: promoType === "product" ? "2px solid #8b5cf6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: promoType === "product" ? "#f5f3ff" : "white", textAlign: "center", wordBreak: "keep-all" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>🎁</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem", fontSize: "0.85rem" }}>상품후기</div>
                      <div style={{ fontSize: "0.7rem", color: "#64748b" }}>제품 리뷰</div>
                    </div>
                    <div onClick={() => setPromoType("hospital")} style={{ padding: "1rem 0.5rem", border: promoType === "hospital" ? "2px solid #8b5cf6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: promoType === "hospital" ? "#f5f3ff" : "white", textAlign: "center", wordBreak: "keep-all" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>🏥</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem", fontSize: "0.85rem" }}>병원운영</div>
                      <div style={{ fontSize: "0.7rem", color: "#64748b" }}>병원·의원 정보</div>
                    </div>
                    <div onClick={() => setPromoType("app")} style={{ padding: "1rem 0.5rem", border: promoType === "app" ? "2px solid #8b5cf6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: promoType === "app" ? "#f5f3ff" : "white", textAlign: "center", wordBreak: "keep-all" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>📱</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem", fontSize: "0.85rem" }}>앱/서비스</div>
                      <div style={{ fontSize: "0.7rem", color: "#64748b" }}>온라인 서비스</div>
                    </div>
                    <div onClick={() => setPromoType("place")} style={{ padding: "1rem 0.5rem", border: promoType === "place" ? "2px solid #8b5cf6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: promoType === "place" ? "#f5f3ff" : "white", textAlign: "center", wordBreak: "keep-all" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>🍽️</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem", fontSize: "0.85rem" }}>맛집후기</div>
                      <div style={{ fontSize: "0.7rem", color: "#64748b" }}>식당 방문기</div>
                    </div>
                    <div onClick={() => setPromoType("service")} style={{ padding: "1rem 0.5rem", border: promoType === "service" ? "2px solid #8b5cf6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: promoType === "service" ? "#f5f3ff" : "white", textAlign: "center", wordBreak: "keep-all" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>💼</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem", fontSize: "0.85rem" }}>서비스업</div>
                      <div style={{ fontSize: "0.7rem", color: "#64748b" }}>오프라인 매장</div>
                    </div>
                  </div>
                </div>
              </>
            )}

            <div>
              <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>배포 방식</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div onClick={() => setDistributionMode("normal")} style={{ padding: "1rem", border: distributionMode === "normal" ? "2px solid #3b82f6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: distributionMode === "normal" ? "#eff6ff" : "white" }}>
                  <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>📝</div>
                  <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem" }}>일반배포</div>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>1500자 이상 · 상세 본문</div>
                </div>
                <div onClick={() => setDistributionMode("quick")} style={{ padding: "1rem", border: distributionMode === "quick" ? "2px solid #3b82f6" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: distributionMode === "quick" ? "#eff6ff" : "white" }}>
                  <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>🚀</div>
                  <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem" }}>막배포</div>
                  <div style={{ fontSize: "0.8rem", color: "#64748b" }}>1500자 이내 · 빠른 배포</div>
                </div>
              </div>
            </div>
            
            <button onClick={handleGenerateContent} disabled={isGenerating} style={{ padding: "1rem", background: "#2563eb", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", borderRadius: "6px", cursor: isGenerating ? "wait" : "pointer", marginTop: "1rem" }}>
              {isGenerating ? "AI가 각 계정별 원고를 창작 중입니다..." : "AI 다중 원고 자동 생성하기"}
            </button>
          </div>
        </div>
        {/* Publish Action */}
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", marginTop: "1rem", padding: "1.5rem", background: "white", border: "1px solid #cbd5e1" }}>
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
          
          {loading && (
            <button
              onClick={handleCancelTask}
              style={{
                padding: "1rem 2rem", background: "#ef4444", color: "white",
                fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer"
              }}>
              ■ 작업 강제 중지
            </button>
          )}
        </div>
      </div>
        
        {/* Right Generated Contents Review Section */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155" }}>✅ 생성된 계정별 원고 검토 및 수정</h3>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button onClick={handleAddBlankManuscript} style={{ padding: '0.4rem 0.8rem', background: '#f59e0b', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                ➕ 직접 추가
              </button>
              <button onClick={() => document.getElementById("localFileInput").click()} style={{ padding: '0.4rem 0.8rem', background: '#8b5cf6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                📁 PC에서 불러오기
              </button>
              <button onClick={openManuscriptModal} style={{ padding: '0.4rem 0.8rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                ☁️ 웹에서 불러오기
              </button>
              <button onClick={handleDownloadAll} style={{ padding: '0.4rem 0.8rem', background: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                ⬇️ 전체 다운로드
              </button>
            </div>
            <input type="file" id="localFileInput" accept=".txt" style={{ display: "none" }} onChange={handleLoadLocalFile} />
          </div>

          {generatedContents.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", overflowY: "auto", flex: 1, paddingRight: "0.5rem" }}>
              {generatedContents.map((gc, idx) => (
                <div key={idx} style={{ background: "#f8fafc", padding: "1rem", border: "1px solid #e2e8f0" }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
                    <div style={{ fontWeight: "bold", color: "#2563eb" }}>▶ [{accounts[idx]?.id || "알 수 없음"}] 에 발행될 원고</div>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <button onClick={() => saveManuscriptToWeb(idx)} style={{ padding: '0.3rem 0.6rem', background: '#e0e7ff', color: '#4338ca', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>
                        ☁️ 웹에 저장
                      </button>
                      <button onClick={() => handleDownloadSingle(idx)} style={{ padding: '0.3rem 0.6rem', background: '#e2e8f0', color: '#475569', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>
                        다운로드
                      </button>
                      <button onClick={() => handleDeleteManuscript(idx)} style={{ padding: '0.3rem 0.6rem', background: '#fee2e2', color: '#ef4444', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>
                        삭제
                      </button>
                    </div>
                  </div>
                  <input type="text" value={gc.title} onChange={(e) => handleUpdateGeneratedContent(idx, "title", e.target.value)} style={{ width: "100%", padding: "0.6rem", border: "1px solid #cbd5e1", boxSizing: "border-box", marginBottom: "0.5rem", fontWeight: "bold" }} />
                  <textarea value={gc.content} onChange={(e) => handleUpdateGeneratedContent(idx, "content", e.target.value)} style={{ width: "100%", height: "250px", padding: "0.6rem", border: "1px solid #cbd5e1", boxSizing: "border-box", resize: "vertical" }} />
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#94a3b8", gap: "1rem" }}>
              <div style={{ fontSize: "3rem" }}>📝</div>
              <p>AI 다중 원고를 생성하거나 상단의 버튼을 통해 원고를 추가해보세요.</p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Monitoring Panel */}
      <div style={{ height: "150px", background: "#1e293b", border: "1px solid #0f172a", display: "flex", flexDirection: "column", color: "#f8fafc" }}>
        <div style={{ padding: "0.8rem 1rem", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1rem", fontWeight: "bold", margin: 0, color: "#f8fafc" }}>실시간 작업 로그</h2>
          {taskStatus === "running" && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>● Running</span>}
          {taskStatus === "completed" && <span style={{ color: "#60a5fa", fontSize: "0.8rem" }}>✓ Completed</span>}
        </div>
        <div style={{ flex: 1, padding: "0.5rem 1rem", overflowY: "auto", fontFamily: "monospace", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
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

      {/* Manuscript Load Modal */}
      {isModalOpen && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 1000 }}>
          <div style={{ background: "white", padding: "2rem", borderRadius: "8px", width: "80%", maxWidth: "800px", maxHeight: "80vh", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "bold" }}>☁️ 웹에서 원고 불러오기</h2>
              <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                {selectedManuscriptIds.length > 0 && (
                  <button onClick={loadSelectedManuscripts} style={{ padding: "0.5rem 1rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>
                    선택된 {selectedManuscriptIds.length}개 한 번에 불러오기
                  </button>
                )}
                <button onClick={() => setIsModalOpen(false)} style={{ background: "transparent", border: "none", fontSize: "1.5rem", cursor: "pointer" }}>×</button>
              </div>
            </div>
            
            <div style={{ overflowY: "auto", flex: 1, border: "1px solid #cbd5e1", padding: "1rem", borderRadius: "4px" }}>
              {isLoadingManuscripts ? (
                <div style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>원고 목록을 불러오는 중...</div>
              ) : savedManuscripts.length === 0 ? (
                <div style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>서버에 저장된 원고가 없습니다.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {savedManuscripts.map(m => (
                    <div key={m.id} style={{ padding: "1rem", border: "1px solid #e2e8f0", background: selectedManuscriptIds.includes(m.id) ? "#eff6ff" : "#f8fafc", borderRadius: "4px", cursor: "pointer" }} onClick={(e) => {
                      if(e.target.tagName !== 'BUTTON' && e.target.type !== 'checkbox') {
                        toggleManuscriptSelection(m.id);
                      }
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <input type="checkbox" checked={selectedManuscriptIds.includes(m.id)} onChange={() => toggleManuscriptSelection(m.id)} style={{ transform: "scale(1.2)" }} />
                          <div style={{ fontWeight: "bold", fontSize: "1.05rem", color: selectedManuscriptIds.includes(m.id) ? "#1d4ed8" : "#0f172a" }}>{m.title}</div>
                        </div>
                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <button onClick={(e) => { e.stopPropagation(); loadManuscriptToWorkspace(m); }} style={{ padding: "0.3rem 0.8rem", background: "#2563eb", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>불러오기</button>
                          <button onClick={(e) => { e.stopPropagation(); deleteManuscriptFromWeb(m.id); }} style={{ padding: "0.3rem 0.8rem", background: "#fee2e2", color: "#ef4444", border: "none", borderRadius: "4px", cursor: "pointer" }}>삭제</button>
                        </div>
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "0.5rem", display: "flex", gap: "1rem" }}>
                        <span>키워드: {m.keyword || "없음"}</span>
                        <span>저장된 계정: {m.account_id || "없음"}</span>
                        <span>저장일시: {new Date(m.created_at).toLocaleString()}</span>
                      </div>
                      <div style={{ fontSize: "0.9rem", color: "#475569", whiteSpace: "pre-wrap", maxHeight: "100px", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {m.content}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}



export default function BlogPostingPage() {
  return <Suspense fallback={<div>Loading...</div>}><BlogPostingContent /></Suspense>;
}
