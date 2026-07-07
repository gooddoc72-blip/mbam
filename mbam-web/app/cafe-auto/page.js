"use client";
import { fetchWithAuth } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";
import { useState, useEffect, useRef } from "react";
import ManuscriptLoaderModal from "../components/ManuscriptLoaderModal";

export default function CafeAutoPage() {
  const [mainTab, setMainTab] = useState("post"); // "post"(즉시+예약 통합), "target"

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
  const [accSearch, setAccSearch] = useState(""); // 발행 계정 검색 필터(계정 多 대비)
  const [targetMultiKeyword, setTargetMultiKeyword] = useState("");
  const [targetMultiLike, setTargetMultiLike] = useState(true); // 댓글과 함께 좋아요
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
  const [newSchPostUrl, setNewSchPostUrl] = useState("");   // 부스트 대상 게시글 URL
  const [newSchInterval, setNewSchInterval] = useState(30); // 방문 간 텀(분)
  const [newSchDoView, setNewSchDoView] = useState(true);   // 조회수(방문)
  const [newSchDoLike, setNewSchDoLike] = useState(true);   // 좋아요
  const [categories, setCategories] = useState([]);
  const [categoryItems, setCategoryItems] = useState([]);
  const [pickCategory, setPickCategory] = useState(""); // 원고용 글감수집 카테고리
  const [pickItems, setPickItems] = useState([]);       // 선택 카테고리의 글감 목록
  const [pickItemId, setPickItemId] = useState("");     // 선택한 글감 id(표시 유지)

  // --- Common ---
  const [loading, setLoading] = usePersistentState("cafe-auto:loading", false);
  const [registeredIds, setRegisteredIds] = useState([]);
  const [promptCategory, setPromptCategory] = useState(null);
  const [includeSourceLink, setIncludeSourceLink] = useState(false); // 본문 끝 출처 링크 (기본 OFF)
  // AI 원고 생성/결과는 전역 보관 — 메뉴 이동해도 생성이 계속되고 돌아오면 결과 유지
  const [isGenerating, setIsGenerating] = usePersistentState("cafe-auto:isGenerating", false); // AI 원고 생성(미리보기) 진행 중
  const [cafeGenerated, setCafeGenerated] = usePersistentState("cafe-auto:cafeGenerated", []); // 계정별 생성 원고 [{account_id,title,content}]
  const [imageFiles, setImageFiles] = useState([]); // 첨부 이미지(글감 생성용)
  const [imageFolder, setImageFolder] = useState(""); // 업로드된 이미지 폴더(발행 시 첨부)
  const [useTethering, setUseTethering] = useState(false); // USB 테더링 IP 우회

  // 이미지 보관함에서 가져오기 (기본 전체 + 골라담기)
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
        setLibSelected(new Set(items.map(i => i.filename)));
      }
    } catch (e) {}
  };
  const toggleLibImage = (fn) => setLibSelected(prev => { const n = new Set(prev); n.has(fn) ? n.delete(fn) : n.add(fn); return n; });
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
        setImageFolder(d.folder);
        setShowLibPicker(false);
        alert(`✅ 보관함에서 ${d.count}장을 발행 이미지로 지정했습니다.`);
      } else alert("이미지 지정에 실패했습니다.");
    } catch (e) { alert("오류: " + e.message); }
    finally { setLibStaging(false); }
  };
  const [accountDelay, setAccountDelay] = useState(5); // 계정 간 발행 텀(분)
  const [accountTargets, setAccountTargets] = useState({}); // 계정별 타겟 {accId: {cafe_url, board_name}}
  const [savedManuscripts, setSavedManuscripts] = useState([]); // 저장된 일괄 원고
  const [batchPosting, setBatchPosting] = usePersistentState("cafe-auto:batchPosting", false);
  const batchCancelRef = useRef(false); // 일괄 발행 강제 중지 플래그
  const [editMs, setEditMs] = useState(null); // 수정 중인 저장 원고

  const loadRegistered = async () => {
    try {
      const res = await fetchWithAuth("/api/auto_post/registered-accounts");
      const data = await res.json();
      if (Array.isArray(data.registered)) setRegisteredIds(data.registered);
    } catch (e) { /* 서버 미기동 시 조용히 무시 */ }
  };
  // 실행 작업 추적(taskId/로그)도 전역 보관 — 이동 후 복귀 시 진행상황 폴링 재개
  const [taskId, setTaskId] = usePersistentState("cafe-auto:taskId", null);
  const [taskKind, setTaskKind] = usePersistentState("cafe-auto:taskKind", "post"); // "post"(포스팅) | "comment"(댓글 작업) — 폴링 엔드포인트 결정
  const [statusLogs, setStatusLogs] = usePersistentState("cafe-auto:statusLogs", []);
  const [taskStatus, setTaskStatus] = usePersistentState("cafe-auto:taskStatus", "");
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    // 계정은 모든 탭에서 필요(포스팅 계정 선택 / 소통·육성 계정 풀). 예약 목록은 소통·육성 탭에서 로드.
    fetchAccounts();
    loadRegistered();
    if (mainTab === "nurture") fetchSchedules();
  }, [mainTab]);

  // 기기 인증 작업이 끝나면 인증 완료 목록 갱신
  useEffect(() => {
    if (taskStatus === "completed") loadRegistered();
  }, [taskStatus]);

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

  // 원고용 글감 목록 로드 (글감수집 카테고리 선택 시)
  useEffect(() => {
    setPickItemId("");
    if (!pickCategory) { setPickItems([]); return; }
    (async () => {
      try {
        const res = await fetchWithAuth(`/api/content/list?category=${encodeURIComponent(pickCategory)}`);
        if (res.ok) { const data = await res.json(); setPickItems(data.items || []); }
      } catch (e) {}
    })();
  }, [pickCategory]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const source = params.get("source_data");
    const kw = params.get("keyword");
    const pc = params.get("prompt_category");
    if (source) {
      // 글감수집에서 새로 넘어온 경우 → 쿼리 우선
      setContent(source);
      if (kw) setTargetKeyword(kw);
      if (pc) setPromptCategory(pc);
    } else {
      // 메뉴 이동 후 복귀 → 저장된 초안 복원
      try {
        const d = JSON.parse(localStorage.getItem("cafe_draft") || "null");
        if (d) {
          if (d.content) setContent(d.content);
          if (d.title) setTitle(d.title);
          if (d.targetKeyword) setTargetKeyword(d.targetKeyword);
          if (Array.isArray(d.generated)) setCafeGenerated(d.generated);
          setPromptCategory(d.promptCategory ?? null);
        }
      } catch (e) {}
    }
    // 진행 중이던 원고 생성 작업이 있으면 폴링 재개 (생성 중 화면으로 복귀)
    try {
      const t = JSON.parse(localStorage.getItem("cafe_gen_task") || "null");
      if (t && t.taskId) pollGeneration(t.taskId);
    } catch (e) {}

    // 진행/완료된 발행 task 복원 (진행중이면 폴링 재개, 완료건은 완료 표시)
    try {
      const pt = JSON.parse(localStorage.getItem("cafe_post_task") || "null");
      if (pt && pt.taskId) {
        setTaskId(pt.taskId);
        setTaskStatus(pt.status || "running");
        if (pt.taskKind) setTaskKind(pt.taskKind);
        if (Array.isArray(pt.logs)) setStatusLogs(pt.logs);
        if (pt.status !== "completed" && pt.status !== "failed") setLoading(true);
      }
    } catch (e) {}

    // 저장된 일괄 발행 원고 불러오기
    fetchManuscripts();
  }, []);

  // 계정 선택이 바뀌면 계정별 타겟(카페/게시판)을 매핑/공통값으로 자동 채움
  useEffect(() => {
    if (selectedAccounts.length > 0 && accounts.length > 0) prefillTargets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccounts, accounts]);

  // 원고/제목 변경 시 초안 자동 저장 (메뉴 이동 후 복원용)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const id = setTimeout(() => saveCafeDraft(), 500);
    return () => clearTimeout(id);
  }, [content, title, targetKeyword, promptCategory]);

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
          // Check which endpoint to poll based on task kind
          const endpoint = taskKind === "comment"
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
  }, [taskId, taskStatus, taskKind]);

  // 발행/작업 task를 브라우저에 저장 (메뉴 이동 후 복귀 시 진행중/완료 그대로 노출)
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      if (taskId) {
        localStorage.setItem("cafe_post_task", JSON.stringify({ taskId, status: taskStatus, taskKind, logs: statusLogs }));
      }
    } catch (e) {}
  }, [taskId, taskStatus, statusLogs, taskKind]);

  // 원고 초안을 브라우저에 저장 (메뉴 이동/복귀 후에도 유지)
  const saveCafeDraft = (over = {}) => {
    try {
      localStorage.setItem("cafe_draft", JSON.stringify({
        content, title, targetKeyword, promptCategory, ...over,
      }));
    } catch (e) {}
  };

  // 생성 작업 폴링 (재개 가능) — taskId 로 결과를 기다려 원고에 반영
  const pollGeneration = async (taskId) => {
    setIsGenerating(true);
    try { localStorage.setItem("cafe_gen_task", JSON.stringify({ taskId })); } catch (e) {}
    try {
      let done = false;
      for (let i = 0; i < 180; i++) {
        await new Promise(r => setTimeout(r, 2000));
        let st;
        try { st = await (await fetchWithAuth(`/api/auto_post/status/${taskId}`)).json(); }
        catch (e) { continue; }
        if (st.status === "completed") {
          const arr = (st.result?.generated_contents || []).filter(g => g && g.content);
          if (arr.length > 0) {
            setCafeGenerated(arr);
            try { addHistory("cafe-auto", { summary: `원고 생성 ${arr.length}건${targetKeyword ? ' · ' + targetKeyword : ''}` }); } catch (e) {}
            // 첫 원고를 단일 필드에도 채워 호환 유지
            setContent(arr[0].content);
            setTitle(prev => prev || arr[0].title || "");
            setPromptCategory(null); // 이후 '작업 시작'은 검토된 원고를 그대로 발행
            saveCafeDraft({ content: arr[0].content, title: (title || arr[0].title || ""), promptCategory: null, generated: arr });
            alert(`✅ ${arr.length}개 원고 생성 완료! 계정별 본문을 검토·수정한 뒤 발행하세요.`);
          } else {
            alert("원고 생성 결과가 비어 있습니다.");
          }
          done = true; break;
        } else if (st.status === "failed") {
          alert("원고 생성 실패: " + (st.error || "알 수 없는 오류")); done = true; break;
        }
      }
      if (!done) alert("원고 생성이 시간 내(6분)에 완료되지 않았습니다.");
    } catch (e) {
      alert("원고 상태 확인 중 오류: " + e.message);
    } finally {
      setIsGenerating(false);
      try { localStorage.removeItem("cafe_gen_task"); } catch (e) {}
    }
  };

  // 글감수집 없이: 첨부 이미지 + 키워드 → AI 비전 분석으로 글감 생성
  const handleDescribeImages = async () => {
    if (!imageFiles || imageFiles.length === 0) return alert("먼저 이미지를 첨부하세요.");
    setIsGenerating(true);
    try {
      const fd = new FormData();
      Array.from(imageFiles).forEach(f => fd.append("images", f));
      fd.append("keyword", targetKeyword || title || "");
      const res = await fetchWithAuth("/api/auto_post/describe-images", { method: "POST", body: fd });
      const data = await res.json();
      if (data.success) {
        setContent(data.source_data);      // 이미지 분석 글감을 원고 소스로
        setImageFolder(data.image_folder || ""); // 발행 시 이 이미지들을 글에 첨부
        setPromptCategory(null);
        alert("✅ 이미지 분석 글감 생성 완료! 이어서 '✨ AI 원고 생성'을 누르면 이미지 내용에 맞춘 원고가 만들어집니다.");
      } else {
        alert(data.detail || "이미지 분석에 실패했습니다.");
      }
    } catch (e) {
      alert("서버 오류: " + e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  // AI 원고 생성(미리보기) 시작 — 발행 전에 실제 원고를 만들어 검토/수정
  const handleGenerateCafe = async () => {
    if (!content.trim() && !targetKeyword.trim()) {
      return alert("키워드 또는 글감(참고 내용)을 먼저 입력/불러오세요.");
    }
    setIsGenerating(true);
    setCafeGenerated([]);
    try {
      // 선택한 계정 수만큼 원고 생성 (블로그와 동일). 선택 없으면 1개 미리보기.
      const chosen = accounts.filter(a => selectedAccounts.includes(a.id));
      const genAccounts = chosen.length > 0
        ? chosen.map(a => ({ id: a.naver_id, checked: true }))
        : [{ id: "preview", checked: true }];
      const payload = {
        accounts: genAccounts,
        target_keyword: targetKeyword || (title || "").slice(0, 20) || "카페글",
        ai_provider: "claude",
        source_data: content,            // 현재 글감/참고 내용을 소스로
        prompt_category: (promptCategory === "content_collect" ? "content_collect_cafe" : promptCategory), // 카페 전용 톤 프롬프트
        include_source_link: includeSourceLink,
        post_purpose: "info",
        target_type: "cafe",
        post_mode: "ai_generate",
      };
      const res = await fetchWithAuth("/api/auto_post/generate-content", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const start = await res.json();
      if (!start.success || !start.task_id) { setIsGenerating(false); return alert("원고 생성 시작에 실패했습니다."); }
      await pollGeneration(start.task_id);
    } catch (e) {
      setIsGenerating(false);
      alert("서버 연결 실패: " + e.message);
    }
  };

  // --- Handlers Tab 1 ---
  // 계정별 타겟(카페/게시판) 매칭
  const setAccTarget = (accId, field, val) =>
    setAccountTargets(prev => ({ ...prev, [accId]: { ...(prev[accId] || {}), [field]: val } }));

  // 가입 카페 매핑 + 공통 입력값으로 계정별 타겟 채우기
  const prefillTargets = () => {
    const next = { ...accountTargets };
    selectedAccounts.forEach(id => {
      const acc = accounts.find(a => a.id === id);
      const mapped = acc && acc.cafes && acc.cafes[0];
      const cur = next[id] || {};
      next[id] = {
        cafe_url: cur.cafe_url || (mapped && mapped.cafe_url) || cafeUrl || "",
        board_name: cur.board_name || (mapped && mapped.board_name) || boardName || "",
      };
    });
    setAccountTargets(next);
  };

  const fetchManuscripts = async () => {
    try {
      const r = await fetchWithAuth("/api/cafe-nurture/manuscripts");
      if (r.ok) setSavedManuscripts(await r.json());
    } catch (e) {}
  };

  // 계정별 (원고 + 카페/게시판) 서버 저장
  const handleSaveManuscripts = async () => {
    const items = [];
    for (const id of selectedAccounts) {
      const acc = accounts.find(a => a.id === id);
      const nid = acc ? acc.naver_id : id;
      const gen = cafeGenerated.find(g => g.account_id === nid);
      const tgt = accountTargets[id] || {};
      const c = (gen && gen.content) ? gen.content : content;
      if (!c || !c.trim()) continue;
      items.push({
        account_id: nid,
        cafe_url: tgt.cafe_url || cafeUrl,
        board_name: tgt.board_name || boardName,
        title: (gen && gen.title) ? gen.title : title,
        content: c,
      });
    }
    if (items.length === 0) return alert("저장할 원고가 없습니다.\n계정 선택 + (AI 원고 생성 또는 본문 입력) 후 저장하세요.");
    if (items.some(it => !it.cafe_url || !it.board_name)) {
      if (!window.confirm("일부 계정의 카페/게시판이 비어 있습니다. 그래도 저장할까요?")) return;
    }
    try {
      const r = await fetchWithAuth("/api/cafe-nurture/manuscripts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items, replace: true }),
      });
      if (r.ok) { alert(`${items.length}개 원고를 저장했습니다.`); fetchManuscripts(); }
      else { const d = await r.json().catch(() => ({})); alert("저장 실패 (" + r.status + "): " + (typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail || d))); }
    } catch (e) { alert("서버 오류: " + e.message); }
  };

  const handleDeleteManuscript = async (id) => {
    try {
      const r = await fetchWithAuth(`/api/cafe-nurture/manuscripts/${id}`, { method: "DELETE" });
      if (r.ok) fetchManuscripts();
    } catch (e) {}
  };

  const handleUpdateManuscript = async () => {
    if (!editMs) return;
    try {
      const r = await fetchWithAuth(`/api/cafe-nurture/manuscripts/${editMs.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cafe_url: editMs.cafe_url, board_name: editMs.board_name, title: editMs.title, content: editMs.content }),
      });
      if (r.ok) { setEditMs(null); fetchManuscripts(); }
      else alert("수정 실패");
    } catch (e) { alert("서버 오류: " + e.message); }
  };

  // 저장된 원고 일괄 발행 (계정별 카페/게시판으로 순차)
  const handleBatchPublish = async () => {
    if (savedManuscripts.length === 0) return alert("저장된 원고가 없습니다. 먼저 '원고 저장'을 하세요.");
    if (!window.confirm(`${savedManuscripts.length}개 저장 원고를 일괄 발행할까요?`)) return;
    batchCancelRef.current = false;  // 취소 플래그 초기화
    setBatchPosting(true); setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null); setTaskKind("post");
    // 취소 가능한 대기 (1초 단위로 플래그 확인)
    const cancellableWait = async (ms) => {
      const end = Date.now() + ms;
      while (Date.now() < end) {
        if (batchCancelRef.current) return;
        await new Promise(r => setTimeout(r, 1000));
      }
    };
    try {
      let last = null, started = 0;
      for (let i = 0; i < savedManuscripts.length; i++) {
        if (batchCancelRef.current) { setStatusLogs(p => [...p, "⏹️ 일괄 발행이 중지되었습니다."]); break; }
        const m = savedManuscripts[i];
        const payload = {
          target_type: "cafe", login_mode: "auto", naver_id: m.account_id, naver_pw: null,
          post_mode: "manual_text", target_keyword: targetKeyword, title: m.title, content: m.content,
          publish_mode: "instant", cafe_url: m.cafe_url, board_name: m.board_name,
          cafe_action_type: "post", source_data: m.content, use_tethering: useTethering,
        };
        const res = await fetchWithAuth("/api/auto_post/", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success && data.task_id) { last = data.task_id; started++; }
        if (i < savedManuscripts.length - 1 && accountDelay > 0) {
          await cancellableWait(accountDelay * 60 * 1000);
        }
      }
      if (batchCancelRef.current) { setTaskStatus("failed"); setLoading(false); }
      else if (last) { setTaskId(last); alert(`${started}개 계정 일괄 발행을 시작했습니다.`); }
      else { alert("발행 시작 실패"); setLoading(false); }
    } catch (e) { alert("서버 오류"); setLoading(false); }
    finally { setBatchPosting(false); }
  };

  const handleStartSingle = async () => {
    const chosen = accounts.filter(a => selectedAccounts.includes(a.id));
    if (chosen.length === 0) return alert("발행할 계정을 선택하세요. (하단 '네이버 아이디 풀'에서 등록·기기 인증 후 위에서 선택)");
    // 계정별 매칭(카페/게시판) 검증
    const missing = chosen.filter(a => { const t = accountTargets[a.id] || {}; return !t.cafe_url || !t.board_name; });
    if (missing.length > 0) return alert("아래 '계정별 타겟 카페·게시판 매칭'에서 카페/게시판을 지정하세요.\n(미지정 계정: " + missing.map(a => a.naver_id).join(", ") + ")");

    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null); setTaskKind("post");
    try {
      // 선택한 계정마다 순차 발행 (기기 인증된 계정은 비밀번호 없이 프로필 자동 로그인)
      let lastTaskId = null, started = 0;
      for (let i = 0; i < chosen.length; i++) {
        const acc = chosen[i];
        // 계정별 생성 원고가 있으면 그 계정 것을, 없으면 공통 본문 사용
        const gen = cafeGenerated.find(g => g.account_id === acc.naver_id);
        const postContent = (gen && gen.content) ? gen.content : content;
        const postTitle = (gen && gen.title) ? gen.title : title;
        const tgt = accountTargets[acc.id] || {};   // 계정별 타겟 카페/게시판
        const payload = {
          target_type: "cafe", login_mode: "auto",
          naver_id: acc.naver_id, naver_pw: null,   // 기기 인증 프로필 자동 로그인
          post_mode: activeTab === "ai" ? "ai_generate" : "manual_text",
          target_keyword: targetKeyword, title: postTitle, content: postContent,
          publish_mode: "instant", cafe_url: tgt.cafe_url, board_name: tgt.board_name,
          images: images, cafe_action_type: actionType, reference_data: referenceData,
          source_data: postContent, prompt_category: (promptCategory === "content_collect" ? "content_collect_cafe" : promptCategory),
          include_source_link: includeSourceLink,
          image_folder_path: imageFolder || null,  // 첨부 이미지 폴더(있으면 글에 첨부)
          use_tethering: useTethering              // USB 테더링 IP 우회(계정 발행 전 IP 회전)
        };
        const res = await fetchWithAuth("/api/auto_post/", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success && data.task_id) { lastTaskId = data.task_id; started++; }
        // 계정 간 발행 텀: 다음 계정 전 대기 (IP 회전/안전 간격 확보)
        if (i < chosen.length - 1 && accountDelay > 0) {
          await new Promise(r => setTimeout(r, accountDelay * 60 * 1000));
        }
      }
      if (lastTaskId) {
        setTaskId(lastTaskId); // 마지막 작업 모니터링
        if (started > 1) alert(`${started}개 계정 발행을 시작했습니다. (모니터링은 마지막 계정 기준)`);
      } else {
        alert("발행 시작에 실패했습니다."); setLoading(false);
      }
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
    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null); setTaskKind("comment");
    try {
      const payload = {
        urls: targetUrls.split("\\n").map(u => u.trim()).filter(u => u),
        account_ids: selectedAccounts,
        keyword: targetMultiKeyword,
        comment_content: targetMultiKeyword,
        delay_min: delayMin,
        delay_max: delayMax,
        use_tethering: useTethering,
        do_like: targetMultiLike
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
    if (!window.confirm("정말 진행 중인 작업을 중단하시겠습니까?")) return;
    batchCancelRef.current = true;   // 일괄 발행 루프 중단
    setBatchPosting(false);
    if (!taskId) { setTaskStatus("failed"); setLoading(false); return; }
    try {
      const endpoint = taskKind === "comment"
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

  const handleDeleteAccount = async (acc) => {
    if (!window.confirm(`'${acc.naver_id}' 계정을 풀에서 삭제할까요?\n매핑된 카페·예약도 함께 정리됩니다.`)) return;
    try {
      const res = await fetchWithAuth(`/api/cafe-nurture/accounts/${acc.id}`, { method: "DELETE" });
      if (res.ok) {
        alert("삭제되었습니다.");
        setSelectedAccounts(prev => prev.filter(id => id !== acc.id));
        fetchAccounts();
      } else {
        const d = await res.json().catch(() => ({}));
        alert("삭제 실패: " + (d.detail || `HTTP ${res.status}`));
      }
    } catch (e) { alert("서버 오류"); }
  };

  const handleAddCafe = async () => {
    if (!newCafeAccId || !newCafeUrl) return alert("계정과 카페 URL을 입력해주세요.");
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/cafes", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: newCafeAccId, cafe_url: newCafeUrl })
      });
      if (res.ok) { alert("카페가 추가되었습니다."); setNewCafeUrl(""); setNewCafeBoard(""); fetchAccounts(); }
      else { const d = await res.json().catch(() => ({})); alert("추가 실패: " + (d.detail || res.status)); }
    } catch (e) { alert("오류"); }
  };

  const handleAddSchedule = async () => {
    if (!newSchAccId || !newSchCafeId || !newSchTime) {
      alert("계정, 매핑된 카페, 예약 시간을 모두 선택해주세요.");
      return;
    }
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/schedules", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
            account_id: newSchAccId,
            cafe_id: newSchCafeId,
            schedule_time: newSchTime,
            content_category: null,
            content_item_id: null,
            content_item_title: null,
            post_count_per_day: Number(newSchCount),
            post_qty_per_time: Number(newSchQty),
            target_post_url: newSchPostUrl.trim() || null,
            do_view: newSchDoView,
            do_like: false,
            visit_interval_min: Number(newSchInterval)
        })
      });
      if (res.ok) {
        alert(`예약이 등록되었습니다. (매일 ${newSchTime})`);
        fetchSchedules();
      } else {
        const d = await res.json().catch(() => ({}));
        alert("예약 등록 실패: " + (d.detail || `HTTP ${res.status}`));
      }
    } catch (e) { alert("오류: 서버 연결 실패"); }
  };

  const handleDeleteSchedule = async (scheduleId) => {
    if (!window.confirm("이 예약을 삭제할까요?")) return;
    try {
      const res = await fetchWithAuth(`/api/cafe-nurture/schedules/${scheduleId}`, { method: "DELETE" });
      if (res.ok) {
        fetchSchedules();
      } else {
        const d = await res.json().catch(() => ({}));
        alert("삭제 실패: " + (d.detail || `HTTP ${res.status}`));
      }
    } catch (e) { alert("오류: 서버 연결 실패"); }
  };

  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "1.5rem", boxSizing: "border-box" }}>
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
                      <div key={img.filename} onClick={() => toggleLibImage(img.filename)} style={{ position: "relative", border: sel ? "3px solid #7c3aed" : "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden", cursor: "pointer", boxSizing: "border-box" }}>
                        <img src={img.base64_data} alt={img.filename} style={{ width: "100%", height: "90px", objectFit: "cover", display: "block", opacity: sel ? 1 : 0.55 }} />
                        {sel && <span style={{ position: "absolute", top: "4px", right: "4px", width: "20px", height: "20px", borderRadius: "50%", background: "#7c3aed", color: "white", fontSize: "0.75rem", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>✓</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <button onClick={useLibImages} disabled={libStaging || libSelected.size === 0} style={{ marginTop: "1rem", padding: "0.9rem", background: (libStaging || libSelected.size === 0) ? "#cbd5e1" : "#7c3aed", color: "white", border: "none", borderRadius: "8px", fontWeight: "bold", fontSize: "1rem", cursor: (libStaging || libSelected.size === 0) ? "not-allowed" : "pointer" }}>
              {libStaging ? "지정 중..." : `선택한 ${libSelected.size}장 발행에 사용`}
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        
        {/* Header Tabs */}
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "1rem" }}>카페 전문 육성 & 자동화</h1>
          <div style={{ display: "flex", gap: "1rem", borderBottom: "2px solid #e2e8f0" }}>
            {[
              { id: "post", label: "카페 포스팅" },
              { id: "nurture", label: "카페 소통·육성" }
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
          
          {/* TAB 1(병합): 즉시 포스팅 + 계정/카페/예약 육성 */}
          {mainTab === "post" && (
            <>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#334155" }}>발행 계정 선택</h2>
                <p style={{ margin: "0 0 0.8rem", fontSize: "0.82rem", color: "#64748b" }}>하단 <b>1. 네이버 아이디 풀</b>에서 등록·기기 인증한 계정 중 발행에 사용할 계정을 고르세요. (인증된 계정은 자동 로그인)</p>
                {/* 계정이 많을 때: 검색 + 전체선택/해제 + 선택 수 */}
                {accounts.length > 0 && (() => {
                  const filtered = accounts.filter(a => a.naver_id.toLowerCase().includes(accSearch.toLowerCase()));
                  const filteredIds = filtered.map(a => a.id);
                  const allSel = filteredIds.length > 0 && filteredIds.every(id => selectedAccounts.includes(id));
                  return (
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.7rem", flexWrap: "wrap" }}>
                      <input type="text" placeholder="🔍 계정 검색" value={accSearch} onChange={e => setAccSearch(e.target.value)} style={{ padding: "0.45rem 0.7rem", border: "1px solid #cbd5e1", borderRadius: "20px", width: "180px" }} />
                      <button onClick={() => setSelectedAccounts(prev => allSel ? prev.filter(id => !filteredIds.includes(id)) : Array.from(new Set([...prev, ...filteredIds])))}
                        style={{ padding: "0.4rem 0.8rem", background: allSel ? "#e2e8f0" : "#2563eb", color: allSel ? "#334155" : "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>
                        {allSel ? "전체 해제" : `전체 선택${accSearch ? " (검색결과)" : ""}`}
                      </button>
                      {selectedAccounts.length > 0 && (
                        <button onClick={() => setSelectedAccounts([])} style={{ padding: "0.4rem 0.8rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem" }}>선택 비우기</button>
                      )}
                      <span style={{ fontSize: "0.85rem", color: "#2563eb", fontWeight: "bold" }}>선택 {selectedAccounts.length} / 전체 {accounts.length}</span>
                    </div>
                  );
                })()}
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", maxHeight: "180px", overflowY: "auto", padding: "0.2rem" }}>
                  {accounts.filter(a => a.naver_id.toLowerCase().includes(accSearch.toLowerCase())).map(acc => (
                    <label key={acc.id} style={{ padding: "0.5rem 1rem", border: "1px solid #cbd5e1", borderRadius: "20px", cursor: "pointer", background: selectedAccounts.includes(acc.id) ? "#2563eb" : "white", color: selectedAccounts.includes(acc.id) ? "white" : "black", fontWeight: "bold" }}>
                      <input type="checkbox" style={{ display: "none" }} checked={selectedAccounts.includes(acc.id)} onChange={() => toggleAccountSelection(acc.id)} />
                      {acc.naver_id}
                    </label>
                  ))}
                  {accounts.length === 0 && <span style={{ color: "#94a3b8" }}>하단 '네이버 아이디 풀 관리'에서 계정을 먼저 등록·인증해주세요.</span>}
                </div>
                {selectedAccounts.length > 1 && (
                  <p style={{ margin: "0.8rem 0 0", fontSize: "0.82rem", color: "#2563eb" }}>* 계정별로 아래에서 카페·게시판을 따로 지정하고, 원고도 따로 생성·저장하여 일괄 발행할 수 있습니다.</p>
                )}
              </div>

              {/* 계정별 타겟 카페·게시판 매칭 */}
              {selectedAccounts.length > 0 && (
                <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
                    <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>계정별 타겟 카페·게시판 매칭</h2>
                    <button onClick={prefillTargets} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>📥 가입 카페 매핑 불러오기</button>
                  </div>

                  {/* 카페 추가(매핑) — 여기서 바로 계정에 카페·게시판 등록 */}
                  <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.8rem", padding: "0.8rem", background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "6px", flexWrap: "wrap", alignItems: "center" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#334155" }}>➕ 카페 추가:</span>
                    <select value={newCafeAccId} onChange={e => setNewCafeAccId(e.target.value)} style={{ padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "4px" }}>
                      <option value="">계정 선택</option>
                      {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                    </select>
                    <input type="text" placeholder="카페 URL (예: https://cafe.naver.com/xxx)" value={newCafeUrl} onChange={e => setNewCafeUrl(e.target.value)} style={{ padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "4px", flex: 1, minWidth: "200px" }} />
                    <button onClick={handleAddCafe} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>등록</button>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                    <thead><tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "120px" }}>발행 계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "230px" }}>가입 카페 매핑에서 선택</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>카페 URL</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "160px" }}>게시판 이름</th>
                      <th style={{ padding: "0.5rem", textAlign: "center", width: "50px" }}>제외</th>
                    </tr></thead>
                    <tbody>
                      {selectedAccounts.map(id => {
                        const acc = accounts.find(a => a.id === id);
                        const t = accountTargets[id] || {};
                        const cafes = (acc && acc.cafes) || [];
                        const selIdx = cafes.findIndex(c => c.cafe_url === t.cafe_url && c.board_name === t.board_name);
                        return (
                          <tr key={id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                            <td style={{ padding: "0.5rem", fontWeight: "bold" }}>{acc ? acc.naver_id : id}</td>
                            <td style={{ padding: "0.5rem" }}>
                              <select value={selIdx >= 0 ? selIdx : ""} onChange={e => { const c = cafes[Number(e.target.value)]; if (c) setAccountTargets(prev => ({ ...prev, [id]: { cafe_url: c.cafe_url, board_name: c.board_name } })); }} style={{ width: "100%", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }}>
                                <option value="">{cafes.length ? "매핑 카페 선택…" : "(매핑 없음 — 소통·육성에서 등록)"}</option>
                                {cafes.map((c, ci) => <option key={ci} value={ci}>{(c.cafe_url || "").replace("https://cafe.naver.com/", "")} / {c.board_name}</option>)}
                              </select>
                            </td>
                            <td style={{ padding: "0.5rem" }}><input type="text" placeholder={cafeUrl || "카페 URL"} value={t.cafe_url || ""} onChange={e => setAccTarget(id, "cafe_url", e.target.value)} style={{ width: "100%", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} /></td>
                            <td style={{ padding: "0.5rem" }}><input type="text" placeholder={boardName || "게시판"} value={t.board_name || ""} onChange={e => setAccTarget(id, "board_name", e.target.value)} style={{ width: "100%", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} /></td>
                            <td style={{ padding: "0.5rem", textAlign: "center" }}>
                              <button onClick={() => toggleAccountSelection(id)} title="이 계정을 발행 대상에서 제외" style={{ padding: "0.3rem 0.55rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>✕</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <p style={{ margin: "0.6rem 0 0", fontSize: "0.8rem", color: "#64748b" }}>* 계정별로 <b>가입 카페 매핑(여러 카페)</b>에서 선택하거나 직접 입력하세요. 매핑 추가/수정은 <b>소통·육성 &gt; 아이디별 가입 카페 매핑</b>에서. 비우면 위 '타겟 카페' 공통값 사용.</p>
                </div>
              )}

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>원고 (키워드)</h2>
                  <button onClick={() => setIsModalOpen(true)} style={{ padding: '0.4rem 0.8rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                    ☁️ 웹에서 불러오기
                  </button>
                </div>
                <input type="text" placeholder="타겟 키워드 (AI 댓글 생성용)" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem" }} />

                {/* 글감수집에서 글감 선택 (제목/본문 자동 채움) */}
                {actionType === "post" && (
                  <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", alignItems: "center", flexWrap: "wrap", padding: "0.7rem", background: "#eff6ff", border: "1px dashed #bfdbfe", borderRadius: "6px" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#1e40af" }}>📚 글감수집에서 선택:</span>
                    <select value={pickCategory} onChange={e => setPickCategory(e.target.value)} style={{ padding: "0.45rem", border: "1px solid #cbd5e1", borderRadius: "4px" }}>
                      <option value="">카테고리 선택</option>
                      {categories.map((c, i) => <option key={i} value={c}>{c}</option>)}
                    </select>
                    <select value={pickItemId} onChange={e => {
                        setPickItemId(e.target.value);
                        const it = pickItems.find(x => String(x.id) === e.target.value);
                        if (it) { setTitle(it.title || ""); setContent(it.content || it.body || ""); setTargetKeyword(prev => prev || it.title || ""); }
                      }} disabled={!pickCategory} style={{ padding: "0.45rem", border: "1px solid #cbd5e1", borderRadius: "4px", flex: 1, minWidth: "220px" }}>
                      <option value="">{pickCategory ? (pickItems.length ? "글감 선택 → 제목·본문 채움" : "글감 없음") : "먼저 카테고리 선택"}</option>
                      {pickItems.map(it => <option key={it.id} value={it.id}>{it.title}</option>)}
                    </select>
                    <span style={{ fontSize: "0.78rem", color: "#64748b" }}>* 선택하면 아래 제목·본문에 채워집니다(이후 AI 원고 생성도 가능).</span>
                  </div>
                )}
                {actionType === "post" && cafeGenerated.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <p style={{ margin: 0, fontSize: "0.85rem", color: "#7c3aed", fontWeight: "bold" }}>✨ 선택한 계정 수만큼 원고를 생성했습니다. 계정별로 검토·수정 후 발행하세요.</p>
                    {cafeGenerated.map((g, idx) => (
                      <div key={idx} style={{ border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1rem", background: "#faf5ff" }}>
                        <div style={{ fontWeight: "bold", color: "#2563eb", marginBottom: "0.5rem" }}>📝 {g.account_id} 계정 원고</div>
                        <input type="text" value={g.title || ""} placeholder="제목"
                          onChange={e => setCafeGenerated(prev => prev.map((x, i) => i === idx ? { ...x, title: e.target.value } : x))}
                          style={{ width: "100%", padding: "0.6rem", marginBottom: "0.5rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                        <textarea value={g.content || ""}
                          onChange={e => setCafeGenerated(prev => prev.map((x, i) => i === idx ? { ...x, content: e.target.value } : x))}
                          style={{ width: "100%", height: "240px", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    {actionType === "post" && <input type="text" placeholder="직접 제목 작성 시" value={title} onChange={e => setTitle(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem" }} />}
                    <textarea placeholder="직접 본문 작성 시 (또는 'AI 원고 생성'으로 미리보기 후 검토)" value={content} onChange={e => setContent(e.target.value)} style={{ width: "100%", height: content ? "260px" : "100px", padding: "0.8rem" }} />
                  </>
                )}
                {actionType === "post" && (
                  <div style={{ marginTop: "0.8rem", padding: "0.8rem", background: "#f0fdf4", border: "1px dashed #86efac", borderRadius: "8px" }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#166534", marginBottom: "0.4rem" }}>🖼️ 글감수집 없이 — 이미지 + 키워드로 글감 만들기</div>
                    <input type="file" accept="image/*" multiple onChange={e => setImageFiles(e.target.files)} style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }} />
                    <button onClick={handleDescribeImages} disabled={isGenerating} style={{ padding: "0.5rem 1rem", background: isGenerating ? "#94a3b8" : "#10b981", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: isGenerating ? "wait" : "pointer", width: "100%" }}>
                      {isGenerating ? "분석 중..." : "🔍 이미지 분석 → 글감 생성"}
                    </button>
                    <button type="button" onClick={openLibPicker} style={{ marginTop: "0.5rem", padding: "0.5rem 1rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", width: "100%" }}>
                      🗂️ 이미지 보관함에서 가져오기
                    </button>
                    {imageFolder && <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#16a34a" }}>✅ 첨부 이미지가 발행 글에도 함께 들어갑니다.</p>}
                    <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#64748b" }}>키워드(위 '타겟 키워드') + 첨부 이미지를 AI가 보고 글감을 만든 뒤, 아래 'AI 원고 생성'으로 원고를 만듭니다.</p>
                  </div>
                )}
                {actionType === "post" && (
                  <button onClick={handleGenerateCafe} disabled={isGenerating} style={{ marginTop: "0.6rem", padding: "0.7rem 1rem", background: isGenerating ? "#94a3b8" : "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: isGenerating ? "wait" : "pointer", width: "100%" }}>
                    {isGenerating ? "AI 원고 생성 중... (최대 1~2분)" : "✨ AI 원고 생성 (미리보기·검토)"}
                  </button>
                )}
                {actionType === "post" && (
                  <p style={{ margin: "0.5rem 0 0", fontSize: "0.82rem", color: "#64748b" }}>
                    * 글감수집에서 넘어온 경우, 위 내용은 <b>참고 글감</b>입니다. <b>AI 원고 생성</b>을 눌러 실제 카페 원고를 만든 뒤 검토·수정하고 발행하세요. (생성 없이 발행하면 발행 시점에 자동 작성됩니다)
                  </p>
                )}
                {content && content.includes("[링크] http") && (
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", marginTop: "0.8rem", fontSize: "0.9rem", color: "#1e40af", fontWeight: "bold" }}>
                    <input type="checkbox" checked={includeSourceLink} onChange={e => setIncludeSourceLink(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                    🔗 글 끝에 출처(원문) 링크 추가
                  </label>
                )}

                {/* 고급: 계정 간 발행 텀 + USB 테더링 */}
                <div style={{ marginTop: "1rem", padding: "1rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.8rem" }}>
                    <span style={{ fontWeight: "bold", color: "#475569" }}>계정 간 발행 텀 (딜레이):</span>
                    <input type="number" min="0" value={accountDelay} onChange={e => setAccountDelay(Number(e.target.value))} style={{ width: "60px", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px", textAlign: "center" }} />
                    <span style={{ color: "#64748b" }}>분 대기 후 다음 계정 발행</span>
                  </div>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: useTethering ? "#3b82f6" : "#64748b" }}>
                    <input type="checkbox" checked={useTethering} onChange={e => setUseTethering(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                    📱 안드로이드 USB 테더링 (비행기 모드 자동 토글) 사용
                    <span style={{ fontSize: "0.8rem", color: "#94a3b8", fontWeight: "normal" }}>* PC와 폰이 USB로 연결되어 있고, USB 테더링이 켜져 있어야 합니다.</span>
                  </label>
                </div>

                {actionType === "post" && (
                  <button onClick={handleSaveManuscripts} style={{ marginTop: "0.8rem", padding: "0.7rem 1rem", background: "#0ea5e9", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", width: "100%" }}>
                    💾 계정별 원고 + 카페/게시판 저장 (일괄 발행 대기열에 등록)
                  </button>
                )}
              </div>

              {/* 저장된 원고 / 일괄 작업 시작 */}
              {actionType === "post" && savedManuscripts.length > 0 && (
                <div style={{ background: "white", padding: "1.5rem", border: "2px solid #0ea5e9", borderRadius: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
                    <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#0c4a6e", margin: 0 }}>📋 저장된 원고 ({savedManuscripts.length}) — 일괄 발행 대기열</h2>
                    <button onClick={handleBatchPublish} disabled={batchPosting || loading} style={{ padding: "0.6rem 1.2rem", background: (batchPosting || loading) ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: (batchPosting || loading) ? "wait" : "pointer" }}>
                      {batchPosting ? "발행 시작 중..." : "🚀 일괄 작업 시작"}
                    </button>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
                    <thead><tr style={{ background: "#f0f9ff", borderBottom: "2px solid #bae6fd" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "120px" }}>계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>카페 / 게시판</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>제목</th>
                      <th style={{ padding: "0.5rem", textAlign: "center", width: "110px" }}>관리</th>
                    </tr></thead>
                    <tbody>
                      {savedManuscripts.map(m => (
                        <tr key={m.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                          <td style={{ padding: "0.5rem", fontWeight: "bold" }}>{m.account_id}</td>
                          <td style={{ padding: "0.5rem", fontSize: "0.8rem", color: "#475569", wordBreak: "break-all" }}>{m.cafe_url || "(공통)"}<br/>{m.board_name}</td>
                          <td style={{ padding: "0.5rem" }}>{m.title || "(자동)"}</td>
                          <td style={{ padding: "0.5rem", textAlign: "center", whiteSpace: "nowrap" }}>
                            <button onClick={() => setEditMs({ ...m })} style={{ padding: "0.25rem 0.5rem", background: "white", color: "#2563eb", border: "1px solid #2563eb", borderRadius: "4px", cursor: "pointer", marginRight: "0.3rem" }}>수정</button>
                            <button onClick={() => handleDeleteManuscript(m.id)} style={{ padding: "0.25rem 0.5rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer" }}>삭제</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p style={{ margin: "0.6rem 0 0", fontSize: "0.8rem", color: "#64748b" }}>* 각 계정의 저장된 카페·게시판으로 순차 발행됩니다(계정 간 {accountDelay}분 텀{useTethering ? ", 테더링 IP 회전" : ""}).</p>
                </div>
              )}

              {/* 저장 원고 수정 모달 */}
              {editMs && (
                <div onClick={() => setEditMs(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
                  <div onClick={e => e.stopPropagation()} style={{ background: "white", borderRadius: "10px", padding: "1.5rem", width: "min(700px, 92vw)", maxHeight: "88vh", overflowY: "auto" }}>
                    <h3 style={{ margin: "0 0 1rem", fontSize: "1.15rem" }}>✏️ 저장 원고 수정 — <span style={{ color: "#2563eb" }}>{editMs.account_id}</span></h3>
                    <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem" }}>
                      <input type="text" placeholder="카페 URL" value={editMs.cafe_url || ""} onChange={e => setEditMs({ ...editMs, cafe_url: e.target.value })} style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                      <input type="text" placeholder="게시판" value={editMs.board_name || ""} onChange={e => setEditMs({ ...editMs, board_name: e.target.value })} style={{ width: "180px", padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                    </div>
                    <input type="text" placeholder="제목" value={editMs.title || ""} onChange={e => setEditMs({ ...editMs, title: e.target.value })} style={{ width: "100%", padding: "0.6rem", marginBottom: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px", boxSizing: "border-box" }} />
                    <textarea value={editMs.content || ""} onChange={e => setEditMs({ ...editMs, content: e.target.value })} style={{ width: "100%", height: "320px", padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "4px", boxSizing: "border-box" }} />
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1rem" }}>
                      <button onClick={() => setEditMs(null)} style={{ padding: "0.6rem 1.2rem", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer" }}>취소</button>
                      <button onClick={handleUpdateManuscript} style={{ padding: "0.6rem 1.2rem", background: "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>저장</button>
                    </div>
                  </div>
                </div>
              )}

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
          {mainTab === "nurture" && (
            <>
              <div style={{ padding: "1rem", background: "#eff6ff", color: "#1e3a8a", border: "1px solid #bfdbfe", borderRadius: "8px" }}>
                💬 <b>댓글 작업(여론 형성·품앗이)</b>: 입력된 게시글 URL들을 선택한 여러 네이버 아이디로 차례대로 방문하여, 지정된 키워드의 뉘앙스로 자연스러운 호응 댓글을 작성합니다. <span style={{ color: "#64748b" }}>(아래에 좋아요·조회수 부스트 / 가입 카페 매핑 / 예약 육성도 함께 있습니다)</span>
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
                  {accounts.length === 0 && <span style={{ color: "#94a3b8" }}>'아이디 육성' 탭(또는 설정 &gt; 계정관리)에서 아이디를 먼저 등록해주세요.</span>}
                </div>
              </div>

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>2. 타겟 게시글 URL 입력</h2>
                <textarea placeholder="댓글을 달 게시글 URL을 한 줄에 하나씩 입력하세요." value={targetUrls} onChange={e => setTargetUrls(e.target.value)} style={{ width: "100%", height: "120px", padding: "0.8rem", border: "1px solid #cbd5e1" }} />
              </div>

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "0.5rem" }}>3. 댓글 내용 (직접 입력)</h2>
                <p style={{ margin: "0 0 0.6rem", fontSize: "0.85rem", color: "#64748b" }}>달 댓글을 직접 입력하세요. <b>한 줄에 하나씩 여러 개</b>를 넣으면 게시글마다 <b>무작위로 하나</b>를 골라 자연스럽게 답니다. (비워두면 AI가 자동 생성)</p>
                <textarea placeholder={"예시(한 줄에 하나씩):\n너무 맛있어 보이네요 저도 가보고 싶어요\n사진만 봐도 군침 도네요 ㅎㅎ\n정보 감사합니다 꼭 가볼게요"} value={targetMultiKeyword} onChange={e => setTargetMultiKeyword(e.target.value)} style={{ width: "100%", height: "110px", padding: "0.8rem", marginBottom: "1rem", border: "1px solid #cbd5e1", borderRadius: "4px", fontFamily: "inherit" }} />
                
                <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                  <span>게시글 간 대기시간 (초):</span>
                  <input type="number" value={delayMin} onChange={e => setDelayMin(e.target.value)} style={{ width: "80px", padding: "0.5rem" }} />
                  <span>~</span>
                  <input type="number" value={delayMax} onChange={e => setDelayMax(e.target.value)} style={{ width: "80px", padding: "0.5rem" }} />
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem", cursor: "pointer", fontWeight: "bold", color: targetMultiLike ? "#e11d48" : "#64748b" }}>
                  <input type="checkbox" checked={targetMultiLike} onChange={e => setTargetMultiLike(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                  ❤️ 댓글과 함께 좋아요 누르기 (게시글에 공감 + 댓글)
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.6rem", cursor: "pointer", fontWeight: "bold", color: useTethering ? "#3b82f6" : "#64748b" }}>
                  <input type="checkbox" checked={useTethering} onChange={e => setUseTethering(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                  📶 USB 테더링 IP 우회 (계정마다 비행기모드 토글로 새 IP 할당 — ADB 연결된 폰 필요)
                </label>
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

          {/* 아이디 육성: 계정 풀/가입 카페 매핑 + 일일 자동 방문(육성) 스케줄 */}
          {mainTab === "nurture" && (
            <>
              <div style={{ padding: "1rem", background: "#fdf2f8", color: "#831843", border: "1px solid #fbcfe8", borderRadius: "8px" }}>
⚙️ <b>육성 설정 & 예약</b>: 아래에서 네이버 아이디 풀을 관리하고 가입 카페를 매핑한 뒤, 예약을 등록하면 백그라운드 서버가 매일 자동으로 게시글 방문(조회수)·좋아요 등 육성 작업을 수행합니다.
              </div>

              {/* 1. Account Management */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0 }}>1. 네이버 아이디 풀 관리</h2>
                  <button onClick={fetchAccounts} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>📥 계정관리에서 불러오기</button>
                </div>
                <p style={{ margin: "0 0 0.8rem", fontSize: "0.82rem", color: "#64748b" }}>여기 목록은 <b>계정관리(전체 계정)</b>와 동일합니다. 여기서 추가/삭제하면 계정관리에도 반영됩니다.</p>
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
                      <th style={{ padding: "0.5rem", textAlign: "center" }}>관리</th>
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
                          {registeredIds.includes(acc.naver_id) ? (
                            <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="기기 인증 완료됨. 다시 인증하려면 클릭하세요." style={{ padding: "0.3rem 0.6rem", background: "#dcfce7", color: "#166534", border: "1px solid #86efac", borderRadius: "4px", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap", fontWeight: "bold" }}>✅ 인증완료</button>
                          ) : (
                            <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="최초 1회 수동 로그인+2단계 인증으로 기기를 등록하면 이후 자동 로그인됩니다." style={{ padding: "0.3rem 0.6rem", background: "#fef3c7", color: "#b45309", border: "1px solid #fcd34d", borderRadius: "4px", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap" }}>🔐 기기 인증</button>
                          )}
                        </td>
                        <td style={{ padding: "0.5rem", textAlign: "center" }}>
                          <button onClick={() => handleDeleteAccount(acc)} title="계정을 풀에서 삭제" style={{ padding: "0.3rem 0.6rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer", whiteSpace: "nowrap" }}>삭제</button>
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
                  <button onClick={handleAddCafe} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none" }}>등록</button>
                </div>
                <ul style={{ paddingLeft: "1.5rem", margin: 0, fontSize: "0.9rem" }}>
                  {accounts.map(acc => (
                    acc.cafes && acc.cafes.map(cafe => (
                      <li key={cafe.id} style={{ marginBottom: "0.3rem" }}>
                        <strong>{acc.naver_id}</strong> ➔ {cafe.cafe_url}
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
                      <option key={cafe.id} value={cafe.id}>{cafe.cafe_url}</option>
                    ))}
                  </select>

                  <input type="time" value={newSchTime} onChange={e => setNewSchTime(e.target.value)} style={{ padding: "0.5rem" }} />
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem", alignItems: "center" }}>
                  <input type="text" placeholder="대상 게시글 URL (비우면 카페 방문만 = 방문횟수 증가)" value={newSchPostUrl} onChange={e => setNewSchPostUrl(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} />
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.2rem'}}>
                    <span style={{fontSize: '0.9rem'}}>일일 방문수</span>
                    <input type="number" min="1" value={newSchCount} onChange={e => setNewSchCount(e.target.value)} style={{ padding: "0.5rem", width: "60px" }} />
                  </div>
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.2rem'}}>
                    <span style={{fontSize: '0.9rem'}}>방문 간격</span>
                    <input type="number" min="0" value={newSchInterval} onChange={e => setNewSchInterval(e.target.value)} style={{ padding: "0.5rem", width: "60px" }} />
                    <span style={{fontSize: '0.9rem'}}>분</span>
                  </div>
                  <button onClick={handleAddSchedule} style={{ padding: "0.5rem 1rem", background: "#0f172a", color: "white", border: "none" }}>예약</button>
                </div>
                <div style={{ display: "flex", gap: "1.2rem", marginBottom: "1rem", alignItems: "center", fontSize: "0.9rem", color: "#475569" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", fontWeight: "bold" }}>
                    <input type="checkbox" checked={newSchDoView} onChange={e => setNewSchDoView(e.target.checked)} /> 👁️ 조회수 올리기(방문)
                  </label>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>* URL이 있으면 그 글을 방문(조회수). 없으면 카페만 방문(육성). 좋아요는 댓글 작업에서 처리됩니다.</span>
                </div>
                
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>실행 시간</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>대상 계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>대상 카페</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>작업 내용</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>상태</th>
                      <th style={{ padding: "0.5rem", textAlign: "center" }}>관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedules.map(sch => (
                      <tr key={sch.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                        <td style={{ padding: "0.5rem", fontWeight: "bold" }}>매일 {sch.schedule_time}</td>
                        <td style={{ padding: "0.5rem" }}>{sch.naver_id}</td>
                        <td style={{ padding: "0.5rem" }}>{sch.cafe_url}{sch.board_name ? ` (${sch.board_name})` : ""}</td>
                        <td style={{ padding: "0.5rem", fontSize: "0.85rem", color: "#475569" }}>
                          {sch.target_post_url
                            ? <span>🎯 게시글 부스트 (방문 {sch.post_count_per_day}회/{sch.visit_interval_min ?? 30}분 간격{sch.do_view ? ", 조회수" : ""}{sch.do_like ? ", ❤️좋아요" : ""})<br/><span style={{ color: "#2563eb", fontSize: "0.78rem", wordBreak: "break-all" }}>{sch.target_post_url}</span></span>
                            : (sch.content_category
                                ? `${sch.content_category}${sch.content_item_title ? ` - ${sch.content_item_title}` : ''} (${sch.post_count_per_day}회)`
                                : `🚶 일반 육성 (카페 방문 ${sch.post_count_per_day}회/${sch.visit_interval_min ?? 30}분 간격)`)}
                        </td>
                        <td style={{ padding: "0.5rem" }}>
                          <span style={{ background: sch.is_active ? "#dcfce7" : "#f1f5f9", color: sch.is_active ? "#166534" : "#64748b", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
                            {sch.is_active ? "활성화" : "정지"}
                          </span>
                        </td>
                        <td style={{ padding: "0.5rem", textAlign: "center" }}>
                          <button onClick={() => handleDeleteSchedule(sch.id)} title="예약 삭제" style={{ padding: "0.3rem 0.6rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer", whiteSpace: "nowrap" }}>삭제</button>
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

      <div style={{ width: "100%", height: "320px", background: "#1e293b", border: "1px solid #0f172a", display: "flex", flexDirection: "column", color: "#f8fafc", borderRadius: "8px", overflow: "hidden" }}>
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
      <WorkHistory menuKey="cafe-auto" />
    </div>
  );
}