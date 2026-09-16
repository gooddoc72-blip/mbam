"use client";
// 카페 포스팅/소통·육성 전체 상태·핸들러 훅 — page.js(렌더)와 분리(모듈화).
// page.js 및 하위 섹션 컴포넌트들이 이 훅 하나로 상태를 공유한다.
import { fetchWithAuth } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import { useState, useEffect, useRef } from "react";

// 댓글 텀은 5초 단위로만 다룬다 — 1초씩 올리내리는 건 실제로 의미가 없고 조작만 번거롭다.
export const DELAY_STEP = 5;

// 화면 입력값(문자열·빈값)을 서버가 받는 숫자로 바꾼다. 비었거나 이상하면 기본값.
// 직접 타이핑해 5의 배수가 아닌 값이 들어와도 여기서 가장 가까운 5초로 맞춘다.
function numOr(v, fallback, step = DELAY_STEP) {
  const n = parseInt(v, 10);
  if (!Number.isFinite(n) || n < 0) return fallback;
  return Math.round(n / step) * step;
}

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
  // 글감 소스: collect(글감수집) | write(직접작성) | image(이미지)
  // 카페 전용판에는 글감수집이 없으므로 '직접 작성'으로 시작한다.
  const [sourceMode, setSourceMode] = useState(
    process.env.NEXT_PUBLIC_PRODUCT === "cafe" ? "write" : "collect"
  );
  const [showAdvanced, setShowAdvanced] = useState(false);  // 고급 설정(발행 텀·테더링) 접기
  // 업로드한 원고 [{filename,title,content,image_markers}] — AI 생성과 별개 경로
  const [uploadedManuscripts, setUploadedManuscripts] = useState([]);
  const [uploadingManuscript, setUploadingManuscript] = useState(false);
  // 어느 발행 대상(계정+카페)에 어느 원고를 쓸지. { "계정id:행번호": 원고번호 }
  // 처음엔 순서대로 배정하고, 사용자가 표에서 바꿀 수 있다.
  const [msAssign, setMsAssign] = useState({});
  const [images, setImages] = useState([]);
  const [referenceData, setReferenceData] = useState(null);

  // --- Tab 2: Target Multi ---
  const [targetUrls, setTargetUrls] = useState("");
  const [selectedAccounts, setSelectedAccounts] = useState([]);
  const [accSearch, setAccSearch] = useState(""); // 발행 계정 검색 필터(계정 多 대비)
  const [targetMultiKeyword, setTargetMultiKeyword] = useState("");
  // AI 댓글의 '메인 키워드'. 예전에는 댓글 입력칸 내용을 그대로 키워드로 보냈는데,
  // 댓글을 직접 써 넣으면 그 문장 전체가 키워드가 되어 AI 가 엉뚱한 방향으로 썼다.
  const [commentKeyword, setCommentKeyword] = useState("");
  // AI 댓글 미리보기 — 실행 전에 확인·수정하기 위한 것.
  // [{url, title, used_keyword, content_preview, comments:[문장,...]}]
  const [previewItems, setPreviewItems] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [targetMultiLike, setTargetMultiLike] = useState(true); // 댓글과 함께 좋아요
  // 등록된 프록시 풀로 계정마다 IP를 바꿔가며 댓글/공감 (기본 ON — 등록된 프록시가
  // 없으면 서버가 알아서 직접 연결로 진행하므로 켜 두어도 안전하다)
  const [targetMultiProxy, setTargetMultiProxy] = useState(true);
  // 댓글 작성 텀 — 게시글 간 / 계정 전환 두 구간을 각각 조정한다.
  // 짧게 두면 같은 계정·같은 IP 에서 연속 등록으로 잡히므로 기본값을 넉넉히 준다.
  const [delayMin, setDelayMin] = useState(30);
  const [delayMax, setDelayMax] = useState(60);
  const [accountDelayMin, setAccountDelayMin] = useState(10);
  const [accountDelayMax, setAccountDelayMax] = useState(30);

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
  const [cafeInsertMap, setCafeInsertMap] = useState(false); // 본문 하단에 네이버 장소(지도) 삽입
  const [cafeMapQuery, setCafeMapQuery] = useState("");      // 삽입할 장소명/주소
  const [subKeywords, setSubKeywords] = useState("");        // 서브(연관) 키워드 — 쉼표 구분, 최대 5개

  // 이미지 보관함에서 가져오기 (기본 전체 + 골라담기)
  const [showLibPicker, setShowLibPicker] = useState(false);
  // 이미지 보관함 선택은 공용 컴포넌트 LibraryPickerModal 로 분리됨(상태/로직 내장)
  const [accountDelay, setAccountDelay] = useState(5); // 계정 간 발행 텀(분)
  // 계정별 타겟 {accId: [{cafe_url, board_name}, ...]} — 계정 하나가 여러 카페에 올릴 수 있다.
  // (예전 형태인 {accId: {cafe_url, board_name}} 도 asTargetList 가 받아준다)
  const [accountTargets, setAccountTargets] = useState({});
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

  // [카페 전용판] 글감수집 기능을 뺐으므로 /api/content 를 부르지 않는다.
  // (풀버전에서는 여기서 카테고리·글감 목록을 불러와 제목·본문을 채운다)
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_PRODUCT === "cafe") return;

    (async () => {
      try {
        const res = await fetchWithAuth("/api/content/categories");
        if (res.ok) {
          const data = await res.json();
          setCategories(data.categories || []);
        }
      } catch (err) {}
    })();
  }, []);

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_PRODUCT === "cafe") return;

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
    if (process.env.NEXT_PUBLIC_PRODUCT === "cafe") return;

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
  // 이미지 분석 → 글감 생성. silent=true면 원고 생성과 연속 수행되는 중이라 자체 알림/로딩토글을 생략하고 결과만 반환.
  const handleDescribeImages = async ({ silent = false } = {}) => {
    if (!imageFiles || imageFiles.length === 0) { if (!silent) alert("먼저 이미지를 첨부하세요."); return null; }
    if (!silent) setIsGenerating(true);
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
        if (!silent) alert("✅ 이미지 분석 글감 생성 완료! 이어서 '✨ AI 원고 생성'을 누르면 이미지 내용에 맞춘 원고가 만들어집니다.");
        return { source_data: data.source_data, image_folder: data.image_folder || "" };
      }
      alert(data.detail || "이미지 분석에 실패했습니다.");
      return null;
    } catch (e) {
      alert("서버 오류: " + e.message);
      return null;
    } finally {
      if (!silent) setIsGenerating(false);
    }
  };

  // AI 원고 생성(미리보기) 시작 — 발행 전에 실제 원고를 만들어 검토/수정
  // 내 PC 에이전트에 네이티브 폴더 선택창을 띄워 사진 폴더 경로를 받아온다(웹은 로컬 경로를 직접 못 얻으므로).
  const handlePickFolder = async () => {
    try {
      const res = await fetchWithAuth("/api/agent/pick-folder", { method: "POST" });
      const data = await res.json();
      // 설치형(로컬)은 백엔드가 이 PC에서 바로 창을 띄우고 경로를 돌려준다 — 폴링 불필요.
      if (data.path !== undefined) {
        if (data.path) { setImageFolder(data.path); alert(`✅ 선택한 폴더:\n${data.path}`); }
        else alert("폴더 선택이 취소되었습니다.");
        return;
      }
      if (!data.job_id) { alert("폴더 선택 요청 실패 — 내 PC 에이전트가 켜져 있는지 확인하세요."); return; }
      alert("내 PC에 '폴더 선택' 창이 곧 뜹니다. 사진이 든 폴더를 고르세요.\n(에이전트가 실행 중이어야 합니다)");
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const jr = await fetchWithAuth(`/api/agent/jobs/${data.job_id}`);
        const jd = await jr.json().catch(() => ({}));
        if (jd.status === "done") {
          const path = (jd.result && jd.result.path) || "";
          if (path) { setImageFolder(path); alert(`✅ 선택한 폴더:\n${path}`); }
          else alert("폴더 선택이 취소되었습니다.");
          return;
        }
        if (jd.status === "error") { alert("폴더 선택 실패: " + (jd.error || "오류")); return; }
      }
      alert("시간 초과 — 에이전트가 켜져 있는지 확인 후 다시 시도하세요.");
    } catch (e) { alert("오류: " + e.message); }
  };

  // 이미 써 둔 원고 파일을 올려서 그대로 발행한다 (AI 생성과 별개 경로).
  // 파일 여러 개를 올리면 선택한 계정 순서대로 하나씩 배정된다 — 계정마다 다른 글이 올라가야
  // 같은 글이 여러 카페에 도배되는 걸 피할 수 있다.
  const handleUploadManuscripts = async (fileList) => {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;
    setUploadingManuscript(true);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append("files", f));
      const res = await fetchWithAuth("/api/cafe-nurture/parse-manuscript", { method: "POST", body: fd });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) { alert("원고를 읽지 못했습니다: " + (d.detail || `HTTP ${res.status}`)); return; }
      const items = d.items || [];
      if (items.length === 0) { alert("읽을 수 있는 원고가 없습니다."); return; }
      // 이어서 올리면 기존 목록 뒤에 쌓는다 (한 번에 다 고르지 않아도 되도록).
      const merged = [...uploadedManuscripts, ...items];
      setUploadedManuscripts(merged);
      // 발행 대상(계정 × 카페)에 원고를 순서대로 배정한다. 이미 지정해 둔 칸은 건드리지 않는다.
      const rows = [];
      selectedAccounts.forEach(id => targetsOf(id).forEach((_, ti) => rows.push(`${id}:${ti}`)));
      setMsAssign(prev => {
        const next = { ...prev };
        let n = 0;
        rows.forEach(k => { if (next[k] === undefined) { next[k] = n % merged.length; } n++; });
        return next;
      });
      const warn = (d.errors || []).length ? `\n\n건너뛴 파일:\n` + d.errors.map(e => `- ${e.filename}: ${e.error}`).join("\n") : "";
      const markers = items.reduce((m, it) => m + (it.image_markers || 0), 0);
      alert(`원고 ${items.length}개를 읽었습니다. (총 ${merged.length}개)` +
            (markers ? `\n사진 자리 [이미지] 가 ${markers}개 있습니다 — '사진 폴더'를 지정하면 순서대로 들어갑니다.` : "") +
            (rows.length > merged.length ? `\n\n※ 발행 대상(${rows.length})이 원고(${merged.length})보다 많아 같은 원고가 반복 배정됐습니다.\n표의 '원고' 칸에서 대상마다 직접 지정하세요.` : "") +
            warn);
    } catch (e) {
      alert("오류: " + e.message);
    } finally {
      setUploadingManuscript(false);
    }
  };

  // 올린 원고를 그 자리에서 고친다 (파일을 다시 만들지 않아도 되도록)
  const editManuscript = (idx, field, val) =>
    setUploadedManuscripts(prev => prev.map((m, i) => i === idx ? { ...m, [field]: val } : m));

  // 원고 목록에서 하나 빼기 — 뒤 번호가 당겨지므로 배정도 같이 손본다.
  const removeManuscript = (idx) => {
    setUploadedManuscripts(prev => prev.filter((_, i) => i !== idx));
    setMsAssign(prev => {
      const next = {};
      Object.entries(prev).forEach(([k, v]) => {
        if (v === idx) return;              // 지운 원고를 쓰던 대상은 '미지정'으로 둔다
        next[k] = v > idx ? v - 1 : v;
      });
      return next;
    });
  };

  // 발행 대상(계정+카페)에 쓸 원고 지정
  const assignManuscript = (key, msIdx) =>
    setMsAssign(prev => ({ ...prev, [key]: msIdx }));

  // 맛집: 폴더 사진 + 리뷰 → 에이전트가 사진을 클라우드로 전송 → Claude가 사진 보고 원고 작성(사진 자리에 [이미지])
  const generateMatjipWithPhotos = async () => {
    setIsGenerating(true); setCafeGenerated([]);
    try {
      const matjipName = (content.match(/\[가게 이름\]\s*(.+)/) || [])[1] || "";
      const subKwArr = (subKeywords || "").split(/[,\n]/).map(s => s.trim()).filter(Boolean).slice(0, 5);
      const res = await fetchWithAuth("/api/cafe-nurture/matjip-generate-job", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_folder: imageFolder, source_data: content, place_name: matjipName,
                               keyword: (targetKeyword || "").trim(), sub_keywords: subKwArr,
                               post_type: mainTab === "matjip" ? "matjip" : "keyword" }),
      });
      const d = await res.json();
      if (!d.job_id) { setIsGenerating(false); return alert("생성 요청 실패 — 잠시 후 다시 시도하세요."); }
      alert("폴더 사진을 분석해 원고를 만듭니다. (사진 장수에 따라 최대 1~2분)");
      for (let i = 0; i < 90; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const jr = await fetchWithAuth(`/api/agent/jobs/${d.job_id}`);
        const jd = await jr.json().catch(() => ({}));
        if (jd.status === "done") {
          const rr = jd.result || {};
          if (rr.success && rr.content) {
            setTitle(rr.title || "");
            setContent(rr.content);
            setCafeGenerated([{ account_id: "preview", title: rr.title || "", content: rr.content }]);
          } else {
            alert("원고 생성 실패: " + (rr.error || "결과 없음"));
          }
          setIsGenerating(false); return;
        }
        if (jd.status === "error") { alert("생성 실패: " + (jd.error || "오류")); setIsGenerating(false); return; }
      }
      alert("시간 초과 — 에이전트 실행 확인 후 다시 시도하세요."); setIsGenerating(false);
    } catch (e) { setIsGenerating(false); alert("오류: " + e.message); }
  };

  const handleGenerateCafe = async () => {
    // 사진 폴더를 지정했으면 '사진을 보고 쓰는' 경로로 간다 — 맛집·일키 모두 같다.
    // (사진을 직접 본 모델이 글까지 쓰므로 사진↔문단이 어긋나지 않는다)
    if ((imageFolder || "").trim()) {
      if (!content.trim() && !targetKeyword.trim()) return alert("키워드 또는 글감(참고 내용)을 먼저 입력/불러오세요.");
      return await generateMatjipWithPhotos();
    }
    setIsGenerating(true);
    // 이미지 모드: 첨부 이미지가 있으면 '원고 생성' 버튼 하나로 이미지 분석→글감 생성까지 먼저 자동 수행한 뒤 이어서 원고 생성
    let sourceOverride = null;
    if (sourceMode === "image" && imageFiles && imageFiles.length > 0) {
      const described = await handleDescribeImages({ silent: true });
      if (!described) { setIsGenerating(false); return; }  // 분석 실패 안내는 handleDescribeImages 내부에서 처리
      sourceOverride = described.source_data;
    }
    const effectiveSource = sourceOverride || content;
    if (!effectiveSource.trim() && !targetKeyword.trim()) {
      setIsGenerating(false);
      return alert("키워드 또는 글감(참고 내용)을 먼저 입력/불러오세요.");
    }
    setCafeGenerated([]);
    try {
      // 선택한 계정 수만큼 원고 생성 (블로그와 동일). 선택 없으면 1개 미리보기.
      const chosen = accounts.filter(a => selectedAccounts.includes(a.id));
      const genAccounts = chosen.length > 0
        ? chosen.map(a => ({ id: a.naver_id, checked: true }))
        : [{ id: "preview", checked: true }];
      // 맛집 모드: 방문 리뷰를 근거로 '내돈내산 후기' 톤. 일키는 일반 카페글 톤.
      // 맛집은 소스의 '[가게 이름]'에서 주제를 뽑아 제목이 정확히 나오게 한다.
      const isMatjip = mainTab === "matjip";
      const matjipName = (content.match(/\[가게 이름\]\s*(.+)/) || [])[1];
      const matjipKeyword = matjipName ? `${matjipName.trim()} 후기` : "맛집 방문 후기";
      // 사용자가 입력한 메인 키워드를 최우선 사용. 맛집도 입력이 있으면 그것으로(없을 때만 가게 이름에서 파생)
      const mainKeyword = (targetKeyword || "").trim()
        || (isMatjip ? matjipKeyword : ((title || "").slice(0, 20) || "카페글"));
      const subKwArr = (subKeywords || "").split(/[,\n]/).map(s => s.trim()).filter(Boolean).slice(0, 5);
      const payload = {
        accounts: genAccounts,
        target_keyword: mainKeyword,
        sub_keywords: subKwArr,          // 서브(연관) 키워드 — 본문에 자연스럽게 녹임
        ai_provider: "claude",
        source_data: effectiveSource,    // 현재 글감/참고 내용(이미지 모드는 방금 분석한 글감)을 소스로
        prompt_category: (promptCategory === "content_collect" ? "content_collect_cafe" : promptCategory), // 카페 전용 톤 프롬프트
        include_source_link: includeSourceLink,
        post_purpose: isMatjip ? "review" : "info",   // 맛집=후기 톤, 일키=info
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
  // 계정별 타겟(카페/게시판) 매칭 — 계정 하나가 여러 카페에 올릴 수 있으므로 '목록'이다.
  // 예전에는 {accId: {cafe_url, board_name}} 한 개였다. 저장돼 있던 값이 그 모양이면 감싸서 읽는다.
  const asTargetList = (v) => {
    if (Array.isArray(v)) return v;
    if (v && (v.cafe_url || v.board_name)) return [v];
    return [];
  };
  // 화면·발행에서 쓰는 정규화된 목록. 비어 있으면 빈 행 하나를 보여준다.
  const targetsOf = (accId) => {
    const list = asTargetList(accountTargets[accId]);
    return list.length ? list : [{ cafe_url: "", board_name: "" }];
  };

  const setAccTarget = (accId, idx, field, val) =>
    setAccountTargets(prev => {
      const list = asTargetList(prev[accId]);
      const next = list.length ? [...list] : [{ cafe_url: "", board_name: "" }];
      next[idx] = { ...(next[idx] || {}), [field]: val };
      return { ...prev, [accId]: next };
    });

  // 이 계정이 올릴 카페를 한 곳 더 추가
  const addAccTarget = (accId) =>
    setAccountTargets(prev => {
      const list = asTargetList(prev[accId]);
      return { ...prev, [accId]: [...(list.length ? list : [{ cafe_url: "", board_name: "" }]), { cafe_url: "", board_name: "" }] };
    });

  const removeAccTarget = (accId, idx) =>
    setAccountTargets(prev => {
      const list = asTargetList(prev[accId]);
      const next = list.filter((_, i) => i !== idx);
      return { ...prev, [accId]: next.length ? next : [{ cafe_url: "", board_name: "" }] };
    });

  // 가입 카페 매핑 + 공통 입력값으로 계정별 타겟 채우기.
  // 이미 채워둔 행은 건드리지 않고, 비어 있는 계정만 '가입 카페 전부'로 펼친다.
  const prefillTargets = () => {
    const next = { ...accountTargets };
    selectedAccounts.forEach(id => {
      const acc = accounts.find(a => a.id === id);
      const cur = asTargetList(next[id]).filter(t => (t.cafe_url || "").trim());
      if (cur.length > 0) { next[id] = cur; return; }
      const mapped = (acc && acc.cafes) || [];
      next[id] = mapped.length
        ? mapped.map(c => ({ cafe_url: c.cafe_url || "", board_name: c.board_name || boardName || "" }))
        : [{ cafe_url: cafeUrl || "", board_name: boardName || "" }];
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
      const c = (gen && gen.content) ? gen.content : content;
      if (!c || !c.trim()) continue;
      // 계정이 여러 카페에 올리면 카페마다 한 건씩 저장한다.
      for (const tgt of targetsOf(id)) {
        items.push({
          account_id: nid,
          cafe_url: tgt.cafe_url || cafeUrl,
          board_name: tgt.board_name || boardName,
          title: (gen && gen.title) ? gen.title : title,
          content: c,
        });
      }
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
          post_mode: "manual_text", target_keyword: targetKeyword,
          sub_keywords: (subKeywords || "").split(/[,\n]/).map(s => s.trim()).filter(Boolean).slice(0, 5),
          title: m.title, content: m.content,
          publish_mode: "instant", cafe_url: m.cafe_url, board_name: m.board_name,
          cafe_action_type: "post", source_data: m.content, use_tethering: useTethering,
          generate_card_news: cafeCardNews, card_count: Number(cafeCardCount) || 3,
          insert_map: cafeInsertMap, map_query: cafeMapQuery,  // 본문 하단 네이버 장소(지도) 삽입
          image_folder_path: imageFolder || null,  // 지정한 이미지 폴더(발행 PC=에이전트 기준). 있으면 카드뉴스 대신 사용
          // 업로드 원고를 대기열에 넣어 일괄 발행할 때도 [이미지] 자리를 그대로 지킨다.
          keep_image_markers: sourceMode === "upload",
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
    // 발행 대상 = (계정 × 그 계정이 올릴 카페) 조합을 한 줄씩 펼친 것.
    // 계정 하나가 여러 카페에 올릴 수 있으므로 계정 수보다 많을 수 있다.
    const isUpload = sourceMode === "upload";
    const jobs = [];
    const missing = [];
    for (const acc of chosen) {
      // targetsOf 의 원래 순서를 지켜야 표에서 지정한 원고(msAssign 의 행번호)와 어긋나지 않는다.
      targetsOf(acc.id).forEach((t, ti) => {
        if (!(t.cafe_url || "").trim() || !(t.board_name || "").trim()) return;
        jobs.push({ acc, tgt: t, key: `${acc.id}:${ti}` });
      });
      if (!jobs.some(j => j.acc.id === acc.id)) missing.push(acc.naver_id);
    }
    if (missing.length > 0) return alert("아래 '계정별 타겟 카페·게시판 매칭'에서 카페/게시판을 지정하세요.\n(미지정 계정: " + missing.join(", ") + ")");
    if (isUpload) {
      if (uploadedManuscripts.length === 0) return alert("발행할 원고 파일을 먼저 올리세요.");
      const noMs = jobs.filter(j => !uploadedManuscripts[msAssign[j.key]]);
      if (noMs.length > 0) return alert("원고가 지정되지 않은 발행 대상이 있습니다.\n표의 '원고' 칸에서 지정하세요.\n(" + noMs.map(j => j.acc.naver_id).join(", ") + ")");
    }

    const multi = jobs.length > chosen.length;
    if (multi && !window.confirm(
        `계정 ${chosen.length}개 → 카페 ${jobs.length}곳에 발행합니다.\n\n` +
        `같은 글이 여러 카페에 올라가면 중복 문서로 잡힐 수 있습니다.\n` +
        `카페마다 다른 글이 필요하면 '원고 업로드'로 카페 수만큼 준비하세요.\n\n계속할까요?`)) return;

    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null); setTaskKind("post");
    try {
      // 대상마다 순차 발행 (기기 인증된 계정은 비밀번호 없이 프로필 자동 로그인)
      let lastTaskId = null, started = 0;
      for (let i = 0; i < jobs.length; i++) {
        const { acc, tgt, key } = jobs[i];
        // 업로드 모드면 이 대상에 지정한 원고를, 아니면 계정별 생성 원고(없으면 공통 본문)를 쓴다.
        const ms = isUpload ? uploadedManuscripts[msAssign[key]] : null;
        const gen = cafeGenerated.find(g => g.account_id === acc.naver_id);
        const postContent = ms ? ms.content : ((gen && gen.content) ? gen.content : content);
        const postTitle = ms ? ms.title : ((gen && gen.title) ? gen.title : title);
        const payload = {
          target_type: "cafe", login_mode: "auto",
          naver_id: acc.naver_id, naver_pw: null,   // 기기 인증 프로필 자동 로그인
          post_mode: activeTab === "ai" ? "ai_generate" : "manual_text",
          target_keyword: targetKeyword,
          sub_keywords: (subKeywords || "").split(/[,\n]/).map(s => s.trim()).filter(Boolean).slice(0, 5),
          title: postTitle, content: postContent,
          publish_mode: "instant", cafe_url: tgt.cafe_url, board_name: tgt.board_name,
          images: images, cafe_action_type: actionType, reference_data: referenceData,
          source_data: postContent,
          // 업로드 원고는 '그대로 발행'이 목적이라 프롬프트를 실으면 안 된다.
          // prompt_category 가 실려 있으면 발행 직전에 AI 가 원고를 다시 써버린다.
          prompt_category: isUpload ? null
            : (promptCategory === "content_collect" ? "content_collect_cafe" : promptCategory),
          keep_image_markers: isUpload,            // 원고에 찍어둔 [이미지] 자리를 그대로 사용
          include_source_link: includeSourceLink,
          image_folder_path: imageFolder || null,  // 첨부 이미지 폴더(있으면 글에 첨부)
          use_tethering: useTethering,             // USB 테더링 IP 우회(계정 발행 전 IP 회전)
          generate_card_news: cafeCardNews,        // 첨부 이미지 없을 때 카드뉴스 자동 생성 여부
          card_count: Number(cafeCardCount) || 3,  // 카드뉴스 장수
          track_rank: cafeTrackRank,               // 발행 후 통검 순위 추적 자동 등록
          insert_map: cafeInsertMap,               // 본문 하단 네이버 장소(지도) 삽입
          map_query: cafeMapQuery                  // 삽입할 장소명/주소
        };
        const res = await fetchWithAuth("/api/auto_post/", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        const data = await res.json();
        // 클라우드 모드는 발행을 로컬 에이전트 잡으로 적재하고 {mode:'agent', job_id}만 반환 → 이것도 '시작 성공'으로 인정
        if ((data.success && data.task_id) || data.job_id) { lastTaskId = data.task_id || data.job_id; started++; }
        // 발행 텀: 다음 대상 전 대기 (IP 회전/안전 간격 확보)
        if (i < jobs.length - 1 && accountDelay > 0) {
          await new Promise(r => setTimeout(r, accountDelay * 60 * 1000));
        }
      }
      if (lastTaskId) {
        setTaskId(lastTaskId); // 마지막 작업 모니터링
        if (started > 1) alert(`${started}건 발행을 시작했습니다. (모니터링은 마지막 건 기준)`);
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
  // 실행 전에 AI 댓글을 만들어 보여준다. 실제로 달지는 않는다.
  // 게시글 본문만 읽어 후보를 만들므로 계정 브라우저를 띄우지 않는다(로그인 세션 안 건드림).
  const handlePreviewComments = async () => {
    const urls = targetUrls.split("\n").map(u => u.trim()).filter(u => u);
    if (urls.length === 0) return alert("먼저 '2. 타겟 게시글 URL'을 입력하세요.");
    setPreviewLoading(true);
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/preview-comments", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          urls,
          // 키워드 칸이 비어 있으면 예전처럼 댓글 입력칸 내용을 쓴다(하위 호환).
          keyword: commentKeyword.trim() || targetMultiKeyword,
          // 선택한 계정 수만큼 만든다. 서버가 중복을 걸러내고 부족하면 더 뽑아
          // '계정 수만큼 서로 다른 댓글'을 채워서 돌려준다.
          count: Math.min(Math.max(selectedAccounts.length || 3, 1), 20),
        }),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) return alert("미리보기 실패: " + (d.detail || `HTTP ${res.status}`));
      setPreviewItems(d.items || []);
      if ((d.errors || []).length > 0) {
        alert("일부 게시글은 본문을 읽지 못했습니다:\n" +
          d.errors.map(e => `· ${e.url}\n   ${e.error}`).join("\n"));
      }
      if ((d.items || []).length === 0) alert("생성된 댓글이 없습니다.");
    } catch (e) { alert("서버 오류 (백엔드 서버가 켜져 있는지 확인해주세요)"); }
    finally { setPreviewLoading(false); }
  };

  const updatePreviewComment = (ui, ci, value) => {
    setPreviewItems(prev => prev.map((it, i) => i !== ui ? it
      : { ...it, comments: it.comments.map((c, j) => (j === ci ? value : c)) }));
  };
  const removePreviewComment = (ui, ci) => {
    setPreviewItems(prev => prev.map((it, i) => i !== ui ? it
      : { ...it, comments: it.comments.filter((_, j) => j !== ci) }));
  };
  const clearPreview = () => setPreviewItems([]);

  const handleStartTargetMulti = async () => {
    // 미리보기에서 확인·수정한 댓글 {URL: [문장,...]} — 빈 줄은 버린다.
    const approved = {};
    previewItems.forEach(it => {
      const list = (it.comments || []).map(c => (c || "").trim()).filter(c => c);
      if (list.length) approved[it.url] = list;
    });
    const hasApproved = Object.keys(approved).length > 0;

    if (!targetUrls || selectedAccounts.length === 0 || (!targetMultiKeyword && !hasApproved)) {
      return alert("URL 목록과 계정을 선택하고, 댓글을 입력하거나 [AI 댓글 미리 만들기]로 생성해주세요.");
    }
    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null); setTaskKind("comment");
    try {
      const payload = {
        urls: targetUrls.split("\n").map(u => u.trim()).filter(u => u),
        account_ids: selectedAccounts,
        // AI 자동 생성 시 이 키워드를 기준으로 쓴다.
        keyword: commentKeyword.trim() || targetMultiKeyword,
        // 미리보기로 확인한 게 있으면 그 문장을 쓴다(AI 재생성 없음).
        comment_content: hasApproved ? "" : targetMultiKeyword,
        comments_by_url: hasApproved ? approved : null,
        // input 값은 문자열이고 지우면 "" 가 된다 — 그대로 보내면 서버가 422 로 튕긴다.
        delay_min: numOr(delayMin, 30),
        delay_max: numOr(delayMax, 60),
        account_delay_min: numOr(accountDelayMin, 10),
        account_delay_max: numOr(accountDelayMax, 30),
        use_tethering: useTethering,
        do_like: targetMultiLike,
        use_proxy: targetMultiProxy
      };
      const res = await fetchWithAuth("/api/cafe-nurture/trigger-targeted", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        setTaskId(data.task_id);
        // 프록시를 켰는데 배정된 게 0개면 전부 같은 IP로 나간다 → 먼저 알려준다.
        if (targetMultiProxy && !data.proxy_count) {
          setStatusLogs((prev) => [...prev,
            "⚠️ 등록된 프록시가 없어 직접 연결(현재 PC IP)로 진행합니다. [프록시 IP] 메뉴에서 등록하세요."]);
        }
      }
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

  // 통합 저장소(/api/accounts, upsert)로 보낸다 — 엑셀 일괄등록도 같은 경로를 쓴다.
  // 구버전 /api/cafe-nurture/accounts 는 이미 있는 아이디를 400 으로 거부해서,
  // 비밀번호를 고치려면 계정을 지웠다 다시 넣는 수밖에 없었다.
  const handleAddAccount = async () => {
    const nid = (newAccId || "").trim();
    const pw = (newAccPw || "").trim();
    if (!nid || !pw) return alert("네이버 아이디와 비밀번호를 모두 입력하세요.");
    try {
      const res = await fetchWithAuth("/api/accounts", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ naver_id: nid, naver_pw: pw })
      });
      const d = await res.json().catch(() => ({}));
      if (res.ok) {
        alert(d.created === false ? `'${nid}' 계정의 비밀번호를 갱신했습니다.` : "추가 완료");
        setNewAccId(""); setNewAccPw(""); fetchAccounts();
      } else {
        alert("추가 실패: " + (d.detail || `HTTP ${res.status}`));
      }
    } catch (e) { alert("서버 오류 (백엔드 서버가 켜져 있는지 확인해주세요)"); }
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

  // 엑셀/CSV 일괄등록 — A열: 네이버 아이디, B열: 카페 URL, C열(선택): 게시판, D열(선택): 비밀번호.
  // 계정 풀에 없는 아이디는 자동 생성하고, 비밀번호가 있으면 계정 비번도 함께 저장한다.
  const importCafeExcel = async (file) => {
    if (!file) return;
    try {
      const { parseSpreadsheet } = await import("../utils/spreadsheet");
      const rows = await parseSpreadsheet(file);
      const body = rows.map(r => ({ nid: (r[0] || "").trim(), url: (r[1] || "").trim(), board: (r[2] || "").trim(), pw: (r[3] || "").trim() }))
                       .filter(x => x.nid && x.url);
      if (!body.length) { alert("등록할 행이 없습니다.\n형식 — A열: 네이버 아이디, B열: 카페 URL, C열(선택): 게시판, D열(선택): 비밀번호"); return; }
      const fetchMap = async () => {
        const res = await fetchWithAuth("/api/cafe-nurture/accounts");
        const list = res.ok ? await res.json() : [];
        const m = {};
        (list || []).forEach(a => { m[(a.naver_id || "").trim().toLowerCase()] = a.id; });
        return m;
      };
      let idMap = await fetchMap();
      // 아이디별 비밀번호(마지막 비어있지 않은 값)
      const pwByNid = {};
      body.forEach(x => { if (x.pw) pwByNid[x.nid.toLowerCase()] = x.pw; });
      // 신규 계정 생성 + (비번이 있으면) 비번 저장 — 아이디+비번 한 번에
      let created = 0, pwSet = 0;
      for (const nid of [...new Set(body.map(x => x.nid))]) {
        const wasNew = !idMap[nid.toLowerCase()];
        const pw = pwByNid[nid.toLowerCase()];
        if (!wasNew && !pw) continue;  // 기존 계정 + 비번 없음 → 건너뜀
        try {
          const payload = pw ? { naver_id: nid, naver_pw: pw } : { naver_id: nid };
          const r = await fetchWithAuth("/api/accounts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
          if (r.ok) { if (wasNew) created++; if (pw) pwSet++; }
        } catch (e) { /* ignore */ }
      }
      if (created) idMap = await fetchMap();
      let ok = 0, fail = 0; const skipped = [];
      for (const x of body) {
        const accId = idMap[x.nid.toLowerCase()];
        if (!accId) { skipped.push(x.nid); continue; }
        try {
          const res = await fetchWithAuth("/api/cafe-nurture/cafes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: accId, cafe_url: x.url, board_name: x.board }) });
          if (res.ok) ok++; else fail++;
        } catch (e) { fail++; }
      }
      await fetchAccounts();
      let msg = `✅ 카페 매핑 ${ok}건 등록` + (created ? ` · 신규 아이디 ${created}개 생성` : "") + (pwSet ? ` · 비번 ${pwSet}개 저장` : "") + (fail ? ` · 실패 ${fail}건` : "");
      if (skipped.length) msg += `\n건너뜀 ${skipped.length}건: ${skipped.slice(0, 8).join(", ")}${skipped.length > 8 ? " …" : ""}`;
      alert(msg);
    } catch (e) { alert("엑셀 처리 오류: " + e.message); }
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
    targetMultiProxy,
    setTargetMultiProxy,
    delayMin,
    setDelayMin,
    delayMax,
    setDelayMax,
    accountDelayMin,
    setAccountDelayMin,
    accountDelayMax,
    setAccountDelayMax,
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
    cafeInsertMap,
    setCafeInsertMap,
    cafeMapQuery,
    setCafeMapQuery,
    subKeywords,
    setSubKeywords,
    handlePickFolder,
    uploadedManuscripts, setUploadedManuscripts,
    uploadingManuscript, handleUploadManuscripts,
    msAssign, assignManuscript, editManuscript, removeManuscript,
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
    targetsOf, addAccTarget, removeAccTarget,
    prefillTargets,
    fetchManuscripts,
    handleSaveManuscripts,
    handleDeleteManuscript,
    handleUpdateManuscript,
    handleBatchPublish,
    handleStartSingle,
    handleLoadManuscript,
    handleStartTargetMulti,
    commentKeyword,
    setCommentKeyword,
    previewItems,
    previewLoading,
    handlePreviewComments,
    updatePreviewComment,
    removePreviewComment,
    clearPreview,
    handleCancelTask,
    toggleAccountSelection,
    handleRegisterAccount,
    handleAddAccount,
    handleDeleteAccount,
    handleAddCafe,
    importCafeExcel,
    handleAddSchedule,
    handleDeleteSchedule,
  };
}
