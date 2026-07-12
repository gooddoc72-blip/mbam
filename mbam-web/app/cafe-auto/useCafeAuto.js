"use client";
// 카페 포스팅/소통·육성 전체 상태·핸들러 훅 — page.js(렌더)와 분리(모듈화).
// page.js 및 하위 섹션 컴포넌트들이 이 훅 하나로 상태를 공유한다.
import { fetchWithAuth } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import { useState, useEffect, useRef } from "react";

export function useCafeAuto() {
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
  const [sourceMode, setSourceMode] = useState("collect"); // 글감 소스: collect(글감수집) | write(직접작성) | image(이미지)
  const [showAdvanced, setShowAdvanced] = useState(false);  // 고급 설정(발행 텀·테더링) 접기
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
  const [cafeCardNews, setCafeCardNews] = useState(true); // 첨부 이미지 없을 때 AI 카드뉴스 자동 생성
  const [cafeCardCount, setCafeCardCount] = useState(3);  // 카드뉴스 장수
  const [cafeTrackRank, setCafeTrackRank] = useState(true); // 발행 후 통검 순위 추적 자동 등록
  const [placeUrl, setPlaceUrl] = useState("");             // 맛집 포스팅: 플레이스 URL
  const [collectingMatjip, setCollectingMatjip] = useState(false);

  // 이미지 보관함에서 가져오기 (기본 전체 + 골라담기)
  const [showLibPicker, setShowLibPicker] = useState(false);
  // 이미지 보관함 선택은 공용 컴포넌트 LibraryPickerModal 로 분리됨(상태/로직 내장)
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
  // 맛집 포스팅: 플레이스 리뷰 + 블로그 후기를 수집해 원고 소재(content)로 채운다.
  const collectMatjipSource = async () => {
    if (!placeUrl.trim() && !targetKeyword.trim()) { alert("플레이스 URL 또는 맛집 키워드를 입력하세요."); return; }
    setCollectingMatjip(true);
    setStatusLogs(p => [...p, "🍜 맛집 소재 수집 시작... (에이전트가 플레이스 리뷰·블로그 후기를 수집)"]);
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/matjip-collect", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ place_url: placeUrl, keyword: targetKeyword }),
      });
      const data = await res.json();
      if (!res.ok) { alert("수집 실패: " + (data.detail || res.status)); return; }
      // 이전 정보성/글감수집에서 남은 제목·키워드를 비운다(맛집 주제는 리뷰 소스 기반으로 AI가 작성)
      const applySource = (sd) => { setTitle(""); setTargetKeyword(""); setContent(sd || ""); setSourceMode("write"); setPromptCategory("cafe_matjip"); };
      if (data.mode === "inline") {
        applySource(data.source_data);
        setStatusLogs(p => [...p, "✅ 맛집 소재 수집 완료. 'AI 원고 생성'을 눌러 원고를 만드세요."]);
      } else if (data.mode === "job" && data.job_id) {
        let done = false;
        for (let i = 0; i < 80 && !done; i++) {
          await new Promise(r => setTimeout(r, 3000));
          const jr = await fetchWithAuth(`/api/agent/jobs/${data.job_id}`);
          const jd = await jr.json().catch(() => ({}));
          if (jd.status === "done") {
            applySource((jd.result && jd.result.source_data) || "");
            setStatusLogs(p => [...p, "✅ 맛집 소재 수집 완료. 'AI 원고 생성'을 눌러 원고를 만드세요."]);
            done = true;
          } else if (jd.status === "error") { alert("수집 실패: " + (jd.error || "오류")); done = true; }
        }
        if (!done) alert("수집이 지연됩니다. 로컬 에이전트가 켜져 있는지 확인 후 잠시 뒤 다시 시도하세요.");
      }
    } catch (e) { alert("오류: " + e.message); }
    finally { setCollectingMatjip(false); }
  };

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
      // 맛집 모드: 수집한 방문자 리뷰를 근거로 '내돈내산 후기'로 작성 (정보성 프롬프트 X)
      // 주제 키워드는 수집 소스의 '[가게 이름]'에서 뽑아 정확한 제목이 나오게 함(잔여 정보성 키워드 미사용).
      const isMatjip = mainTab === "matjip";
      const matjipName = (content.match(/\[가게 이름\]\s*(.+)/) || [])[1];
      const matjipKeyword = matjipName ? `${matjipName.trim()} 후기` : "맛집 방문 후기";
      const payload = {
        accounts: genAccounts,
        target_keyword: isMatjip
          ? matjipKeyword
          : (targetKeyword || (title || "").slice(0, 20) || "카페글"),
        ai_provider: "claude",
        source_data: content,            // 현재 글감/참고 내용을 소스로
        prompt_category: (promptCategory === "content_collect" ? "content_collect_cafe" : promptCategory), // 카페 전용 톤 프롬프트
        include_source_link: includeSourceLink,
        post_purpose: isMatjip ? "review" : "info",   // 맛집=후기 톤, 정보성=info
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
          generate_card_news: cafeCardNews, card_count: Number(cafeCardCount) || 3,
          image_folder_path: imageFolder || null,  // 지정한 이미지 폴더(발행 PC=에이전트 기준). 있으면 카드뉴스 대신 사용
        };
        const res = await fetchWithAuth("/api/auto_post/", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        const data = await res.json();
        // 클라우드 모드는 에이전트 잡으로 적재되어 {mode:'agent', job_id} 를 반환 → 이것도 '시작 성공'으로 인정
        if ((data.success && data.task_id) || data.job_id) { last = data.task_id || data.job_id; started++; }
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
          use_tethering: useTethering,             // USB 테더링 IP 우회(계정 발행 전 IP 회전)
          generate_card_news: cafeCardNews,        // 첨부 이미지 없을 때 카드뉴스 자동 생성 여부
          card_count: Number(cafeCardCount) || 3,  // 카드뉴스 장수
          track_rank: cafeTrackRank                // 발행 후 통검 순위 추적 자동 등록
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

  return {
    mainTab,
    setMainTab,
    activeTab,
    setActiveTab,
    loginMode,
    setLoginMode,
    naverId,
    setNaverId,
    naverPw,
    setNaverPw,
    cafeUrl,
    setCafeUrl,
    boardName,
    setBoardName,
    actionType,
    setActionType,
    targetKeyword,
    setTargetKeyword,
    title,
    setTitle,
    content,
    setContent,
    sourceMode,
    setSourceMode,
    showAdvanced,
    setShowAdvanced,
    images,
    setImages,
    referenceData,
    setReferenceData,
    targetUrls,
    setTargetUrls,
    selectedAccounts,
    setSelectedAccounts,
    accSearch,
    setAccSearch,
    targetMultiKeyword,
    setTargetMultiKeyword,
    targetMultiLike,
    setTargetMultiLike,
    delayMin,
    setDelayMin,
    delayMax,
    setDelayMax,
    accounts,
    setAccounts,
    schedules,
    setSchedules,
    newAccId,
    setNewAccId,
    newAccPw,
    setNewAccPw,
    newCafeAccId,
    setNewCafeAccId,
    newCafeUrl,
    setNewCafeUrl,
    newCafeBoard,
    setNewCafeBoard,
    newSchAccId,
    setNewSchAccId,
    newSchCafeId,
    setNewSchCafeId,
    newSchTime,
    setNewSchTime,
    newSchCategory,
    setNewSchCategory,
    newSchContentItem,
    setNewSchContentItem,
    newSchContentItemTitle,
    setNewSchContentItemTitle,
    newSchCount,
    setNewSchCount,
    newSchQty,
    setNewSchQty,
    newSchPostUrl,
    setNewSchPostUrl,
    newSchInterval,
    setNewSchInterval,
    newSchDoView,
    setNewSchDoView,
    newSchDoLike,
    setNewSchDoLike,
    categories,
    setCategories,
    categoryItems,
    setCategoryItems,
    pickCategory,
    setPickCategory,
    pickItems,
    setPickItems,
    pickItemId,
    setPickItemId,
    loading,
    setLoading,
    registeredIds,
    setRegisteredIds,
    promptCategory,
    setPromptCategory,
    includeSourceLink,
    setIncludeSourceLink,
    isGenerating,
    setIsGenerating,
    cafeGenerated,
    setCafeGenerated,
    imageFiles,
    setImageFiles,
    imageFolder,
    setImageFolder,
    useTethering,
    setUseTethering,
    cafeCardNews,
    setCafeCardNews,
    cafeCardCount,
    setCafeCardCount,
    cafeTrackRank,
    setCafeTrackRank,
    placeUrl,
    setPlaceUrl,
    collectingMatjip,
    collectMatjipSource,
    showLibPicker,
    setShowLibPicker,
    accountDelay,
    setAccountDelay,
    accountTargets,
    setAccountTargets,
    savedManuscripts,
    setSavedManuscripts,
    batchPosting,
    setBatchPosting,
    batchCancelRef,
    editMs,
    setEditMs,
    loadRegistered,
    taskId,
    setTaskId,
    taskKind,
    setTaskKind,
    statusLogs,
    setStatusLogs,
    taskStatus,
    setTaskStatus,
    isModalOpen,
    setIsModalOpen,
    fetchAccounts,
    fetchSchedules,
    saveCafeDraft,
    pollGeneration,
    handleDescribeImages,
    handleGenerateCafe,
    setAccTarget,
    prefillTargets,
    fetchManuscripts,
    handleSaveManuscripts,
    handleDeleteManuscript,
    handleUpdateManuscript,
    handleBatchPublish,
    handleStartSingle,
    handleLoadManuscript,
    handleStartTargetMulti,
    handleCancelTask,
    toggleAccountSelection,
    handleRegisterAccount,
    handleAddAccount,
    handleDeleteAccount,
    handleAddCafe,
    handleAddSchedule,
    handleDeleteSchedule,
  };
}
