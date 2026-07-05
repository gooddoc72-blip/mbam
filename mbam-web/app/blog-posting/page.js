"use client";
import { fetchWithAuth } from "../utils/api";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams, usePathname } from "next/navigation";
import Link from "next/link";

function BlogPostingContent() {

  // 1. Account Settings
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const isHospital = pathname === "/hospital-blog";  // 병원 블로그 전용 메뉴로 진입 시 병원 카테고리 고정
  const [generateCardNews, setGenerateCardNews] = useState(isHospital ? false : true);  // 병원: 카드뉴스 대신 나노바나나 AI 이미지
  const [sourceData, setSourceData] = useState("");
  const [promptCategory, setPromptCategory] = useState(null);
  const [includeSourceLink, setIncludeSourceLink] = useState(false); // 본문 끝 출처 링크 (기본 OFF)

  const [accounts, setAccounts] = useState([{ id: "", pw: "", blogAddr: "", checked: true }]);
  const [intervalMins, setIntervalMins] = useState(5);
  const [useTethering, setUseTethering] = useState(false);
  const [registeredIds, setRegisteredIds] = useState([]);

  // 계정관리(중앙 저장소)에서 선택 불러오기
  const [showAcctPicker, setShowAcctPicker] = useState(false);
  const [storeAccts, setStoreAccts] = useState([]);
  const [pickedIds, setPickedIds] = useState([]);

  const openAccountPicker = async () => {
    try {
      const res = await fetchWithAuth("/api/accounts");
      if (!res.ok) return alert("계정 목록을 불러오지 못했습니다.");
      const data = await res.json();
      const list = data.accounts || [];
      if (list.length === 0) return alert("계정 관리에 저장된 계정이 없습니다.\n(멀티 계정 실행 > 네이버 계정 관리에서 추가하세요)");
      setStoreAccts(list);
      setPickedIds(list.map((a) => a.naver_id)); // 기본 전체 선택
      setShowAcctPicker(true);
    } catch {
      alert("서버 연결에 실패했습니다.");
    }
  };
  const togglePick = (id) => setPickedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  const applyPickedAccounts = () => {
    const chosen = storeAccts.filter((a) => pickedIds.includes(a.naver_id));
    if (chosen.length === 0) return alert("최소 1개 계정을 선택하세요.");
    setAccounts(chosen.map((a) => ({ id: a.naver_id, pw: "", blogAddr: a.blog_addr || "", checked: true })));
    setShowAcctPicker(false);
  };

  const loadRegistered = async () => {
    try {
      const res = await fetchWithAuth("/api/auto_post/registered-accounts");
      const data = await res.json();
      if (Array.isArray(data.registered)) setRegisteredIds(data.registered);
    } catch (e) { /* 서버 미기동 시 조용히 무시 */ }
  };

  const addAccount = () => setAccounts([...accounts, { id: "", pw: "", blogAddr: "", checked: true }]);
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
  const [subKeywords, setSubKeywords] = useState([]);   // 서브(연관) 키워드 최대 5개
  const [subKwInput, setSubKwInput] = useState("");
  const [productUrl, setProductUrl] = useState("");

  const addSubKeyword = () => {
    const v = (subKwInput || "").trim().replace(/,$/, "").trim();
    if (!v) return;
    if (subKeywords.length >= 5) { alert("서브 키워드는 최대 5개까지 추가할 수 있습니다."); return; }
    if (subKeywords.includes(v)) { setSubKwInput(""); return; }
    setSubKeywords([...subKeywords, v]);
    setSubKwInput("");
  };
  const removeSubKeyword = (kw) => setSubKeywords(subKeywords.filter(k => k !== kw));
  const [extractUrlImages, setExtractUrlImages] = useState(false);
  const [descImageFiles, setDescImageFiles] = useState([]); // 첨부 이미지(글감 생성용)
  const [aiProvider, setAiProvider] = useState("claude");
  const [postPurpose, setPostPurpose] = useState(isHospital ? "info" : "review");  // 병원: 진료일기(정보성) 고정
  const [promoType, setPromoType] = useState(isHospital ? "hospital" : "product");
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
  const [insertMap, setInsertMap] = useState(false);   // 네이버 장소(지도) 삽입
  const [mapQuery, setMapQuery] = useState("");         // 삽입할 장소명/주소

  // 이미지 보관함에서 가져오기 (기본 전체 선택 + 골라담기)
  const [showLibPicker, setShowLibPicker] = useState(false);
  const [libImages, setLibImages] = useState([]);
  const [libSelected, setLibSelected] = useState(() => new Set());
  const [libStaging, setLibStaging] = useState(false);

  const openLibPicker = async () => {
    setShowLibPicker(true);
    try {
      const res = await fetchWithAuth("/api/settings/wash-library");
      if (res.ok) {
        const d = await res.json();
        const items = d.items || [];
        setLibImages(items);
        setLibSelected(new Set(items.map(i => i.filename))); // 기본 전체 선택
      }
    } catch (e) {}
  };
  const toggleLibImage = (fn) => {
    setLibSelected(prev => { const n = new Set(prev); n.has(fn) ? n.delete(fn) : n.add(fn); return n; });
  };
  const useLibImages = async () => {
    const picked = Array.from(libSelected);
    if (picked.length === 0) { alert("사용할 이미지를 1장 이상 선택하세요."); return; }
    setLibStaging(true);
    try {
      const res = await fetchWithAuth("/api/settings/wash-library/stage", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filenames: picked })
      });
      const d = await res.json();
      if (res.ok && d.success && d.folder) {
        setImageUploadMode("folder");
        setImageFolderPath(d.folder);
        setShowLibPicker(false);
        alert(`✅ 보관함에서 ${d.count}장을 발행 이미지로 지정했습니다.`);
      } else alert("이미지 지정에 실패했습니다.");
    } catch (e) { alert("오류: " + e.message); }
    finally { setLibStaging(false); }
  };

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
    // 글감수집에서 넘어온 경우 전용 프롬프트 카테고리 + 키워드 적용
    if (searchParams) {
      const pc = searchParams.get("prompt_category");
      if (pc) setPromptCategory(pc);
      const kw = searchParams.get("keyword");
      if (kw) setTargetKeyword(kw);
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

    loadRegistered();
  }, []);

  // 작업(기기 인증 포함)이 끝나면 인증 완료 목록 갱신
  useEffect(() => {
    if (taskStatus === "completed") loadRegistered();
  }, [taskStatus]);


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
              // 완료/실패 결과는 다른 메뉴 갔다 와도 보이도록 taskId 보관.
              // 서버 재시작(not_found)으로 결과가 사라진 경우에만 정리.
              if (data.status === "not_found") {
                localStorage.removeItem("mbam_auto_post_task_id");
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

  // 글감수집 없이: 첨부 이미지 + 키워드 → AI 비전 분석으로 글감 생성
  const handleDescribeImagesBlog = async () => {
    if (!descImageFiles || descImageFiles.length === 0) return alert("먼저 이미지를 첨부하세요.");
    setIsGenerating(true);
    try {
      const fd = new FormData();
      Array.from(descImageFiles).forEach(f => fd.append("images", f));
      fd.append("keyword", targetKeyword || "");
      const res = await fetchWithAuth("/api/auto_post/describe-images", { method: "POST", body: fd });
      const data = await res.json();
      if (data.success) {
        setSourceData(data.source_data);
        try { localStorage.setItem('autoWriteSourceData', data.source_data); } catch (e) {}
        if (data.image_folder) { setImageUploadMode("folder"); setImageFolderPath(data.image_folder); }
        alert("✅ 이미지 분석 글감 생성 완료! '원고 생성'을 누르면 이미지 내용에 맞춘 원고가 만들어집니다.");
      } else {
        alert(data.detail || "이미지 분석에 실패했습니다.");
      }
    } catch (e) {
      alert("서버 오류: " + e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateContent = async () => {
    if (!targetKeyword) {
      alert("타겟 키워드를 입력해주세요.");
      return;
    }
    const validAccounts = accounts.filter(a => a.id.trim() !== "" && a.checked !== false);
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
        sub_keywords: subKeywords,
        product_url: productUrl,
        extract_url_images: extractUrlImages,
        ai_provider: aiProvider,
        post_purpose: postPurpose,
        promo_type: promoType,
        distribution_mode: distributionMode,

        reference_data: referenceData,
        generate_card_news: generateCardNews,
        source_data: sourceData,
        prompt_category: promptCategory,
        include_source_link: includeSourceLink,
        post_mode: "ai_generate",

        login_mode: "manual",
        publish_mode: "instant",
        target_type: "blog",
        cafe_action_type: "post"
      };
      const res = await fetchWithAuth("/api/auto_post/generate-content", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errText = await res.text();
        alert(`서버 응답 오류: ${res.status} - ${errText}`);
        return;
      }
      const start = await res.json();
      if (!start.success || !start.task_id) {
        alert("원고 생성 시작에 실패했습니다: " + JSON.stringify(start));
        return;
      }
      // 원고 생성은 30초 이상 걸릴 수 있어 백그라운드로 처리됨 → 상태 폴링(최대 5분)
      const taskId = start.task_id;
      let done = false;
      for (let i = 0; i < 150; i++) {
        await new Promise(r => setTimeout(r, 2000));
        let st;
        try {
          const sres = await fetchWithAuth(`/api/auto_post/status/${taskId}`);
          st = await sres.json();
        } catch (e) { continue; }
        if (st.status === "completed") {
          const data = st.result || {};
          if (data.success) {
            setGeneratedContents(data.generated_contents || []);
            try { addHistory("blog-posting", { summary: `원고 생성 ${(data.generated_contents || []).length}건${targetKeyword ? ' · ' + targetKeyword : ''}` }); } catch (e) {}
            if (data.scraped_image_folder) {
              setImageUploadMode("folder");
              setImageFolderPath(data.scraped_image_folder);
              alert("✅ 원고 생성 완료! 타겟 URL에서 이미지 수집도 성공하여 이미지 폴더가 자동 지정되었습니다.");
            }
          } else {
            alert("원고 생성에 실패했습니다: " + JSON.stringify(data));
          }
          done = true;
          break;
        } else if (st.status === "failed") {
          alert("원고 생성 실패: " + (st.error || "알 수 없는 오류"));
          done = true;
          break;
        }
      }
      if (!done) alert("원고 생성이 시간 내(5분)에 완료되지 않았습니다. 계정 수를 줄이거나 잠시 후 다시 시도해주세요.");
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
    const validAccounts = accounts.filter(a => a.id.trim() !== "" && a.checked !== false);
    if (validAccounts.length === 0) {
      alert("계정을 1개 이상 입력해주세요.");
      return;
    }

    // 사용 계정을 계정 관리(중앙 저장소)에 동기화 (best-effort)
    validAccounts.forEach(a => {
      fetchWithAuth("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ naver_id: a.id, naver_pw: a.pw || null, blog_addr: a.blogAddr || null }),
      }).catch(() => {});
    });

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
        image_folder_path: imageFolderPath || null,
        insert_map: insertMap,
        map_query: mapQuery,
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

  const handleRegisterAccount = async (acc) => {
    if (!acc.id || !acc.id.trim()) { alert("네이버 아이디를 먼저 입력해주세요."); return; }
    if (!window.confirm(`'${acc.id}' 계정의 기기 인증을 시작합니다.\n잠시 후 열리는 브라우저 창에서 로그인 + 2단계 인증을 완료해주세요.\n(최초 1회만 하면 이후에는 자동 로그인됩니다)`)) return;
    try {
      setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null);
      const res = await fetchWithAuth("/api/auto_post/register-account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ naver_id: acc.id, naver_pw: acc.pw || null })
      });
      const data = await res.json();
      if (data.success && data.task_id) {
        setTaskId(data.task_id);
        // 계정 관리(중앙 저장소)에도 등록 (best-effort)
        fetchWithAuth("/api/accounts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ naver_id: acc.id, naver_pw: acc.pw || null, blog_addr: acc.blogAddr || null }),
        }).catch(() => {});
      } else {
        alert("기기 인증 시작에 실패했습니다.");
        setLoading(false);
      }
    } catch (e) {
      console.error(e);
      alert("서버 연결에 실패했습니다. (백엔드 서버가 켜져 있는지 확인해주세요)");
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

      {/* 발행 모드 탭 */}
      <div style={{ display: "flex", gap: "0.5rem", borderBottom: "2px solid #e2e8f0", marginBottom: "-1rem" }}>
        {[
          { href: "/blog-posting", label: "✍️ 블로그 발행 (수동·예약)" },
          { href: "/hospital-blog", label: "🏥 병원 블로그" },
          { href: "/blog-schedule", label: "🗓️ 매일 자동 포스팅" },
        ].map(t => {
          const active = pathname === t.href;
          return (
            <Link key={t.href} href={t.href} style={{ padding: "0.7rem 1.2rem", textDecoration: "none", color: active ? "#2563eb" : "#64748b", fontWeight: "bold", borderBottom: active ? "3px solid #2563eb" : "3px solid transparent", marginBottom: "-2px" }}>{t.label}</Link>
          );
        })}
      </div>

      {/* 이미지 보관함 선택 모달 */}
      {showLibPicker && (
        <div onClick={() => setShowLibPicker(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "white", borderRadius: "12px", padding: "1.5rem", width: "640px", maxWidth: "92vw", maxHeight: "82vh", display: "flex", flexDirection: "column", boxShadow: "0 10px 40px rgba(0,0,0,0.25)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.15rem", color: "#1e293b" }}>🗂️ 보관함에서 이미지 선택 <span style={{ fontSize: "0.85rem", color: "#94a3b8", fontWeight: "normal" }}>(선택 {libSelected.size}/{libImages.length})</span></h3>
              <button onClick={() => setShowLibPicker(false)} style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#94a3b8" }}>✕</button>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.8rem" }}>
              <button onClick={() => setLibSelected(new Set(libImages.map(i => i.filename)))} style={{ fontSize: "0.82rem", padding: "0.35rem 0.8rem", background: "#eff6ff", color: "#2563eb", border: "1px solid #bfdbfe", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>전체 선택</button>
              <button onClick={() => setLibSelected(new Set())} style={{ fontSize: "0.82rem", padding: "0.35rem 0.8rem", background: "#f8fafc", color: "#64748b", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>전체 해제</button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "0.8rem" }}>
              {libImages.length === 0 ? (
                <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8", fontSize: "0.9rem" }}>보관함이 비어 있습니다. 이미지 세탁소에서 세탁 후 “💾 보관함에 저장”을 먼저 해주세요.</div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))", gap: "0.6rem" }}>
                  {libImages.map((img) => {
                    const sel = libSelected.has(img.filename);
                    return (
                      <div key={img.filename} onClick={() => toggleLibImage(img.filename)} style={{ position: "relative", border: sel ? "3px solid #2563eb" : "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden", cursor: "pointer", boxSizing: "border-box" }}>
                        <img src={img.base64_data} alt={img.filename} style={{ width: "100%", height: "90px", objectFit: "cover", display: "block", opacity: sel ? 1 : 0.55 }} />
                        {sel && <span style={{ position: "absolute", top: "4px", right: "4px", width: "20px", height: "20px", borderRadius: "50%", background: "#2563eb", color: "white", fontSize: "0.75rem", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>✓</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <button onClick={useLibImages} disabled={libStaging || libSelected.size === 0} style={{ marginTop: "1rem", padding: "0.9rem", background: (libStaging || libSelected.size === 0) ? "#cbd5e1" : "#2563eb", color: "white", border: "none", borderRadius: "8px", fontWeight: "bold", fontSize: "1rem", cursor: (libStaging || libSelected.size === 0) ? "not-allowed" : "pointer" }}>
              {libStaging ? "지정 중..." : `선택한 ${libSelected.size}장 발행에 사용`}
            </button>
          </div>
        </div>
      )}

      {/* 계정관리에서 선택 불러오기 모달 */}
      {showAcctPicker && (
        <div onClick={() => setShowAcctPicker(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "white", borderRadius: "12px", padding: "1.5rem", width: "480px", maxHeight: "70vh", overflowY: "auto", boxShadow: "0 10px 40px rgba(0,0,0,0.25)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.15rem", color: "#1e293b" }}>📥 계정관리에서 불러오기</h3>
              <button onClick={() => setShowAcctPicker(false)} style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#94a3b8" }}>✕</button>
            </div>
            <p style={{ margin: "0 0 0.8rem", fontSize: "0.85rem", color: "#64748b" }}>발행에 사용할 계정을 선택하세요.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {storeAccts.map((a) => (
                <label key={a.id} style={{ display: "flex", alignItems: "center", gap: "0.6rem", padding: "0.6rem 0.8rem", border: "1px solid #e2e8f0", borderRadius: "8px", cursor: "pointer", background: pickedIds.includes(a.naver_id) ? "#eff6ff" : "white" }}>
                  <input type="checkbox" checked={pickedIds.includes(a.naver_id)} onChange={() => togglePick(a.naver_id)} style={{ width: "18px", height: "18px" }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: "bold", color: "#1e293b" }}>{a.naver_id}</div>
                    <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>
                      {a.blog_addr ? `블로그: ${a.blog_addr}` : "블로그: (아이디와 동일)"}
                      {" · "}
                      {a.registered ? "✅ 인증완료" : "⚠️ 미인증"}
                    </div>
                  </div>
                </label>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.2rem" }}>
              <button onClick={() => setShowAcctPicker(false)} style={{ padding: "0.5rem 1rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", color: "#64748b" }}>취소</button>
              <button onClick={applyPickedAccounts} style={{ padding: "0.5rem 1.2rem", background: "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>선택 계정 불러오기 ({pickedIds.length})</button>
            </div>
          </div>
        </div>
      )}

      {/* Top Section: Left Control Panel & Right Generated Contents */}
      <div style={{ display: "flex", gap: "2rem", flex: 1, minHeight: 0 }}>
        
        {/* Left Control Panel */}
        <div style={{ flex: 1.5, display: "flex", flexDirection: "column", gap: "1.5rem", paddingRight: "10px" }}>
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "0.5rem" }}>{isHospital ? "🏥 병원 블로그 자동 포스팅" : "블로그 자동 포스팅"}</h1>
          <p style={{ color: "#64748b", margin: 0 }}>{isHospital ? "병원·의원 전용 — 의료법 준수 원고 + 나노바나나 AI 이미지 자동 생성·삽입." : "SEO 분석 및 글감 수집 데이터를 기반으로 다중 계정에 원고를 자동 발행합니다."}</p>
        </div>

        {/* 1. Account Settings */}
        <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>1. 네이버 다중 계정 설정</h2>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button onClick={openAccountPicker} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>📥 계정관리에서 불러오기</button>
              <button onClick={addAccount} style={{ padding: "0.4rem 0.8rem", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "4px", cursor: "pointer" }}>+ 직접 추가</button>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
            {accounts.map((acc, idx) => (
              <div key={idx} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input type="checkbox" checked={acc.checked !== false} onChange={(e) => updateAccount(idx, "checked", e.target.checked)} title="이 계정으로 발행" style={{ width: "18px", height: "18px", cursor: "pointer" }} />
                <span style={{ width: "20px", fontWeight: "bold", color: "#64748b" }}>{idx+1}.</span>
                <input type="text" placeholder="네이버 아이디" value={acc.id} onChange={(e) => updateAccount(idx, "id", e.target.value)} style={{ padding: "0.6rem", border: "1px solid #cbd5e1", flex: 1 }} />
                <input type="password" placeholder="비밀번호" value={acc.pw} onChange={(e) => updateAccount(idx, "pw", e.target.value)} style={{ padding: "0.6rem", border: "1px solid #cbd5e1", flex: 1 }} />
                <input type="text" placeholder="블로그 주소(선택, 예: bonetacasa)" title="로그인 아이디와 블로그 주소가 다른 경우만 입력 (blog.naver.com/[여기]). 비우면 자동 감지." value={acc.blogAddr || ""} onChange={(e) => updateAccount(idx, "blogAddr", e.target.value)} style={{ padding: "0.6rem", border: "1px solid #cbd5e1", flex: 1 }} />
                {registeredIds.includes(acc.id) ? (
                  <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="기기 인증 완료됨. 다시 인증하려면 클릭하세요." style={{ padding: "0.6rem", background: "#dcfce7", color: "#166534", border: "1px solid #86efac", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap", fontWeight: "bold" }}>✅ 인증완료</button>
                ) : (
                  <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="최초 1회 수동 로그인+2단계 인증으로 기기를 등록하면 이후 자동 로그인됩니다." style={{ padding: "0.6rem", background: "#fef3c7", color: "#b45309", border: "1px solid #fcd34d", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap" }}>🔐 기기 인증</button>
                )}
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
          <div>
            <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#334155" }}>발행에 넣을 이미지</label>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input type="text" value={imageFolderPath} onChange={e => setImageFolderPath(e.target.value)} placeholder="‘폴더 찾기’ 또는 ‘보관함에서 가져오기’로 이미지를 등록하세요" style={{ flex: 1, padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
              <button type="button" onClick={handleSelectFolder} style={{ padding: "0 1rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>
                🔍 폴더 찾기
              </button>
              <button type="button" onClick={openLibPicker} style={{ padding: "0 1rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>
                🗂️ 보관함에서 가져오기
              </button>
            </div>
            <p style={{ fontSize: "0.8rem", color: "#64748b", margin: "0.5rem 0 0 0" }}>* 등록한 이미지를 <b>계정마다 자동 세탁(서로 다른 버전)</b>해서 발행합니다. (계정당 최대 3장 사용)</p>
          </div>

          {isHospital ? (
            <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#fef9c3", borderRadius: "8px", border: "1px solid #fde68a" }}>
              <div style={{ fontWeight: "bold", color: "#92400e" }}>🍌 나노바나나 AI 이미지 자동 생성·삽입</div>
              <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.85rem", color: "#a16207" }}>* 업로드 이미지가 없으면 진료일기에 맞는 의료 이미지(썸네일·해부학·관리법·상담·마무리)를 AI가 자동 생성해 삽입합니다. (카드뉴스 미사용)</p>
            </div>
          ) : (
          <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#ecfdf5", borderRadius: "8px", border: "1px solid #a7f3d0" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: "#065f46" }}>
              <input type="checkbox" checked={generateCardNews} onChange={e => setGenerateCardNews(e.target.checked)} style={{ transform: "scale(1.2)" }} />
              🎨 업로드할 이미지가 없을 경우 AI 카드뉴스 자동 생성
            </label>
            <p style={{ margin: "0.5rem 0 0 1.5rem", fontSize: "0.85rem", color: "#047857" }}>* 백엔드의 AI 이미지 생성기를 호출하여 원고 내용에 맞는 정보성 카드뉴스를 생성한 후 포스팅에 첨부합니다.</p>
          </div>
          )}

          {/* 지도(장소) 삽입 */}
          <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#eff6ff", borderRadius: "8px", border: "1px solid #bfdbfe" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: insertMap ? "#1d4ed8" : "#334155" }}>
              <input type="checkbox" checked={insertMap} onChange={e => setInsertMap(e.target.checked)} style={{ transform: "scale(1.2)" }} />
              🗺️ 글 하단에 네이버 지도(장소) 삽입
            </label>
            {insertMap && (
              <div style={{ marginTop: "0.7rem" }}>
                <input type="text" value={mapQuery} onChange={e => setMapQuery(e.target.value)} placeholder="삽입할 장소명 또는 주소 (예: 스타벅스 서면전포역점)" style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                <p style={{ margin: "0.4rem 0 0", fontSize: "0.82rem", color: "#3b82f6" }}>* 발행 시 에디터에서 해당 장소를 검색해 <b>첫 번째 결과</b>의 지도를 글 맨 아래에 자동 삽입합니다. (매장 위치 안내·지역 SEO에 유용)</p>
              </div>
            )}
          </div>

          {sourceData && sourceData.includes("[링크] http") && (
            <div style={{ marginTop: "1rem", padding: "1rem", background: "#eff6ff", borderRadius: "8px", border: "1px solid #bfdbfe" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: "#1e40af" }}>
                <input type="checkbox" checked={includeSourceLink} onChange={e => setIncludeSourceLink(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                🔗 글 끝에 출처(원문) 링크 추가
              </label>
              <p style={{ margin: "0.5rem 0 0 1.5rem", fontSize: "0.85rem", color: "#3b82f6" }}>* 글감에 원문 링크가 있을 때만 본문 맨 끝에 “▶ 자세히 보기: 링크”를 덧붙입니다. (네이버 블로그는 외부링크가 노출에 불리할 수 있어 기본 꺼짐)</p>
            </div>
          )}
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

                <div style={{ marginTop: "0.8rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                    <label style={{ fontSize: "0.9rem", fontWeight: "bold" }}>서브 키워드 <span style={{ fontWeight: "normal", color: "#94a3b8", fontSize: "0.8rem" }}>(선택 · 최대 5개)</span></label>
                    <button type="button" onClick={addSubKeyword} disabled={subKeywords.length >= 5} style={{ padding: "0.35rem 0.8rem", background: subKeywords.length >= 5 ? "#cbd5e1" : "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", fontSize: "0.82rem", cursor: subKeywords.length >= 5 ? "not-allowed" : "pointer", whiteSpace: "nowrap" }}>+ 추가</button>
                  </div>
                  <input type="text" value={subKwInput} onChange={e => setSubKwInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addSubKeyword(); } }} disabled={subKeywords.length >= 5} placeholder={subKeywords.length >= 5 ? "최대 5개까지 추가됨" : "예: 분위기 좋은 카페 (입력 후 Enter)"} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                  {subKeywords.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginTop: "0.6rem" }}>
                      {subKeywords.map((kw, i) => (
                        <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.3rem 0.7rem", background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe", borderRadius: "999px", fontSize: "0.85rem", fontWeight: "bold" }}>{kw}<span onClick={() => removeSubKeyword(kw)} style={{ cursor: "pointer", color: "#60a5fa", fontWeight: "bold" }}>×</span></span>
                      ))}
                      <span style={{ alignSelf: "center", fontSize: "0.78rem", color: "#94a3b8" }}>{subKeywords.length}/5</span>
                    </div>
                  )}
                </div>
              </div>
              <div style={{ flex: 1 }}>
                {!isHospital && (<>
                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>타겟 상품 URL (선택)</label>
                <input type="text" placeholder="예: https://smartstore.naver.com/..." value={productUrl} onChange={e => setProductUrl(e.target.value)} style={{ width: "100%", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.5rem", cursor: "pointer", fontSize: "0.85rem", color: extractUrlImages ? "#2563eb" : "#64748b" }}>
                  <input type="checkbox" checked={extractUrlImages} onChange={e => setExtractUrlImages(e.target.checked)} />
                  ✨ 타겟 URL에서 상품 이미지 자동 수집하여 사용하기
                </label>
                </>)}

                <div style={{ marginTop: "0.8rem", padding: "0.8rem", background: "#f0fdf4", border: "1px dashed #86efac", borderRadius: "8px" }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#166534", marginBottom: "0.4rem" }}>🖼️ 글감수집 없이 — 이미지 + 키워드로 글감 만들기</div>
                  <input type="file" accept="image/*" multiple onChange={e => setDescImageFiles(e.target.files)} style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }} />
                  <button type="button" onClick={handleDescribeImagesBlog} disabled={isGenerating} style={{ padding: "0.5rem 1rem", background: isGenerating ? "#94a3b8" : "#10b981", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: isGenerating ? "wait" : "pointer", width: "100%" }}>
                    {isGenerating ? "분석 중..." : "🔍 이미지 분석 → 글감 생성"}
                  </button>
                  <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#64748b" }}>타겟 키워드 + 첨부 이미지를 AI가 보고 글감을 만든 뒤, '원고 생성'으로 원고를 만듭니다. 첨부 이미지는 발행 글에도 함께 들어갑니다.</p>
                </div>
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

            {sourceData && (
              <div style={{ marginBottom: "1rem", padding: "1rem 1.2rem", background: "#f0fdf4", borderRadius: "8px", border: "1px solid #bbf7d0" }}>
                <p style={{ margin: 0, fontSize: "0.9rem", color: "#15803d", lineHeight: "1.5" }}>
                  💡 <strong>분석/글감 데이터가 반영됩니다.</strong> 아래에서 <strong>포스팅 목적</strong>(리뷰/홍보/정보성)과 <strong>유형</strong>(맛집·업체 등)을 골라 그 성격으로 작성하세요.
                </p>
              </div>
            )}
              <>
                {isHospital ? (
                  <div style={{ padding: "1rem", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "8px" }}>
                    <div style={{ fontWeight: "bold", color: "#1e40af" }}>🏥 진료일기 형식 · 병원운영 (자동)</div>
                    <p style={{ margin: "0.4rem 0 0", fontSize: "0.85rem", color: "#3b82f6" }}>병원 블로그는 리뷰가 아닌 <strong>진료일기(정보성)</strong> 형식으로 의료법 준수 원고를 자동 작성합니다.</p>
                  </div>
                ) : (<>
                <div>
                  <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "bold", marginBottom: "0.5rem" }}>포스팅 목적</label>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
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
                    <div onClick={() => setPostPurpose("info")} style={{ padding: "1rem", border: postPurpose === "info" ? "2px solid #22c55e" : "1px solid #cbd5e1", borderRadius: "8px", cursor: "pointer", background: postPurpose === "info" ? "#f0fdf4" : "white" }}>
                      <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>📚</div>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.2rem" }}>정보성</div>
                      <div style={{ fontSize: "0.8rem", color: "#64748b" }}>지수용 정보글(비홍보)</div>
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
                </>)}
              </>

            {!isHospital && (
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
            )}

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
          
          {(loading || taskStatus === "running" || taskId) && (
            <button
              onClick={handleCancelTask}
              style={{
                padding: "1rem 2rem", background: "#ef4444", color: "white",
                fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer", whiteSpace: "nowrap"
              }}>
              ■ 작업 강제 중지
            </button>
          )}
        </div>
      </div>
        
        {/* Right Generated Contents Review Section */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>✅ 생성된 계정별 원고 검토 및 수정</h3>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button onClick={handleAddBlankManuscript} style={{ padding: '0.4rem 0.8rem', background: '#f59e0b', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                ➕ 직접 추가
              </button>
              <button onClick={() => document.getElementById("localFileInput").click()} style={{ padding: '0.4rem 0.8rem', background: '#8b5cf6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                📁 PC에서 불러오기
              </button>
              <button onClick={openManuscriptModal} style={{ padding: '0.4rem 0.8rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                ☁️ 웹에서 불러오기
              </button>
              <button onClick={handleDownloadAll} style={{ padding: '0.4rem 0.8rem', background: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
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

      <WorkHistory menuKey="blog-posting" />
    </div>
  );
}



export default function BlogPostingPage() {
  return <Suspense fallback={<div>Loading...</div>}><BlogPostingContent /></Suspense>;
}
