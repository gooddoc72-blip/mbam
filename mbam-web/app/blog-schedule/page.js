"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";
import Link from "next/link";
import { usePathname } from "next/navigation";
import LibraryPickerModal from "../components/LibraryPickerModal";

export default function BlogSchedulePage() {
  const pathname = usePathname();
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(false);

  // 플랫폼: 네이버(스크래핑·에이전트) / 블로그스팟(Blogger API·클라우드 직접발행) / 티스토리(브라우저 자동화·에이전트)
  const [platform, setPlatform] = useState("naver");
  const [bsAccounts, setBsAccounts] = useState([]);   // 블로그스팟 계정
  const [bsSchedules, setBsSchedules] = useState([]); // 블로그스팟 예약
  const [tsAccounts, setTsAccounts] = useState([]);   // 티스토리 계정
  const [tsSchedules, setTsSchedules] = useState([]); // 티스토리 예약
  const [tsKakaoId, setTsKakaoId] = useState("");     // 티스토리 계정 추가 폼
  const [tsBlogName, setTsBlogName] = useState("");

  // form state
  const [accountId, setAccountId] = useState("");        // (레거시) 예약 포스팅 서브탭에서 사용
  const [selectedAccIds, setSelectedAccIds] = useState(() => new Set());  // 매일 자동발행: 다중 계정
  const [scheduleTime, setScheduleTime] = useState("09:00");
  const [category, setCategory] = useState("");
  const [count, setCount] = useState(1);
  const [aiProvider, setAiProvider] = useState("claude");
  const [distMode, setDistMode] = useState("normal");
  const [cardNews, setCardNews] = useState(true);

  // 서브탭: 매일 자동발행 / 예약 포스팅
  const [subTab, setSubTab] = useState("daily");

  // 예약 포스팅 폼 + 목록
  const [reservations, setReservations] = useState([]);
  const [rAccountId, setRAccountId] = useState("");
  const [rKeyword, setRKeyword] = useState("");
  const [rSource, setRSource] = useState("");
  const [rDate, setRDate] = useState("");
  const [rTime, setRTime] = useState("09:00");
  const [rAi, setRAi] = useState("claude");
  const [rDist, setRDist] = useState("normal");
  const [rCard, setRCard] = useState(true);
  const [rImageFolder, setRImageFolder] = useState("");
  const [rImageCount, setRImageCount] = useState(0);
  const [rLoading, setRLoading] = useState(false);

  // 사진(보관함) 선택
  const [showLibPicker, setShowLibPicker] = useState(false);
  // 이미지 보관함 선택은 공용 LibraryPickerModal 컴포넌트로 분리됨

  const loadAll = async () => {
    try {
      const [accRes, catRes, schRes, resvRes, bsAccRes, bsSchRes, tsAccRes, tsSchRes] = await Promise.all([
        fetchWithAuth("/api/cafe-nurture/accounts"),
        fetchWithAuth("/api/content/categories"),
        fetchWithAuth("/api/blog-schedule/schedules"),
        fetchWithAuth("/api/blog-schedule/reservations"),
        fetchWithAuth("/api/blogspot/accounts"),
        fetchWithAuth("/api/blogspot/schedules"),
        fetchWithAuth("/api/tistory/accounts"),
        fetchWithAuth("/api/tistory/schedules"),
      ]);
      const accData = accRes.ok ? await accRes.json() : [];
      const catData = catRes.ok ? await catRes.json() : {};
      const schData = schRes.ok ? await schRes.json() : [];
      const resvData = resvRes.ok ? await resvRes.json() : [];
      // 블로그스팟 계정: {success, accounts:[{id, account_name, blog_id}]} → 공용 칩 UI용으로 naver_id 별칭 부여
      const bsAccJson = bsAccRes.ok ? await bsAccRes.json() : {};
      const bsAccList = (bsAccJson.accounts || []).map(a => ({ id: a.id, naver_id: a.account_name, blog_addr: a.blog_id }));
      const bsSchData = bsSchRes.ok ? await bsSchRes.json() : [];
      setBsAccounts(bsAccList);
      setBsSchedules(bsSchData || []);
      // 티스토리 계정: {success, accounts:[{id, kakao_id, blog_name, status}]} → 공용 칩 UI용 naver_id 별칭
      const tsAccJson = tsAccRes.ok ? await tsAccRes.json() : {};
      const tsAccList = (tsAccJson.accounts || []).map(a => ({ id: a.id, naver_id: (a.blog_name ? a.blog_name + ".tistory.com" : a.kakao_id), blog_addr: a.blog_name, kakao_id: a.kakao_id, status: a.status }));
      const tsSchData = tsSchRes.ok ? await tsSchRes.json() : [];
      setTsAccounts(tsAccList);
      setTsSchedules(tsSchData || []);
      setAccounts(accData || []);
      setCategories(catData.categories || []);
      setSchedules(schData || []);
      setReservations(resvData || []);
      if (!accountId && accData && accData.length > 0) setAccountId(accData[0].id);
      if (!rAccountId && accData && accData.length > 0) setRAccountId(accData[0].id);
      // 매일 자동발행: 첫 로드 시 등록 계정을 전체 선택(원하면 해제)
      setSelectedAccIds(prev => prev.size === 0 ? new Set((accData || []).map(a => a.id)) : prev);
      if (!category && catData.categories && catData.categories.length > 0) setCategory(catData.categories[0]);
    } catch (e) {
      console.error(e);
    }
  };


  const handleAddReservation = async () => {
    if (!rAccountId) { alert("발행 계정을 선택하세요."); return; }
    if (!rKeyword.trim()) { alert("타겟 키워드를 입력하세요."); return; }
    if (!rDate || !rTime) { alert("예약 날짜와 시간을 입력하세요."); return; }
    setRLoading(true);
    try {
      const res = await fetchWithAuth("/api/blog-schedule/reservations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: rAccountId, run_at: `${rDate} ${rTime}`, keyword: rKeyword,
          source_data: rSource || null, image_folder: rImageFolder || null,
          ai_provider: rAi, distribution_mode: rDist, generate_card_news: rCard,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ ${rDate} ${rTime}에 '${rKeyword}' 예약 포스팅이 등록되었습니다.`);
        setRKeyword(""); setRSource(""); setRImageFolder(""); setRImageCount(0);
        loadAll();
      } else alert("등록 실패: " + (data.detail || data.message || "오류"));
    } catch (e) { alert("등록 중 오류: " + e.message); } finally { setRLoading(false); }
  };

  const handleDeleteReservation = async (id) => {
    if (!confirm("이 예약을 삭제할까요?")) return;
    try { const res = await fetchWithAuth(`/api/blog-schedule/reservations/${id}`, { method: "DELETE" }); if (res.ok) loadAll(); } catch (e) {}
  };

  useEffect(() => {
    loadAll();
    // 사이드바에서 ?platform=tistory 등으로 들어오면 해당 플랫폼을 자동 선택
    try {
      const p = new URLSearchParams(window.location.search).get("platform");
      if (["naver", "blogspot", "tistory"].includes(p)) { setSubTab("daily"); setPlatform(p); }
    } catch (e) {}
    /* eslint-disable-next-line */
  }, []);

  const toggleAcc = (id) => setSelectedAccIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const handleAdd = async () => {
    const label = isBlogspot ? "블로그스팟" : isTistory ? "티스토리" : "네이버";
    const accIds = Array.from(selectedAccIds);
    if (accIds.length === 0) {
      alert(isNaver ? "발행할 네이버 계정을 1개 이상 선택하세요. (계정관리에서 기기 인증된 계정이 필요합니다)" : `발행할 ${label} 계정을 1개 이상 선택하세요.`);
      return;
    }
    if (!category) { alert("글감 카테고리를 선택하세요. (글감 수집 메뉴에서 먼저 수집해야 글감이 생깁니다)"); return; }
    setLoading(true);
    try {
      const body = isNaver
        ? { account_ids: accIds, schedule_time: scheduleTime, content_category: category, post_count_per_day: Number(count) || 1, ai_provider: aiProvider, distribution_mode: distMode, generate_card_news: cardNews }
        : { account_ids: accIds, schedule_time: scheduleTime, content_category: category, post_count_per_day: Number(count) || 1, ai_provider: aiProvider };
      const res = await fetchWithAuth(scheduleBase, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ ${accIds.length}개 계정에 ${isNaver ? "" : label + " "}매일 자동발행 예약이 등록되었습니다!\n매일 ${scheduleTime}에 '${category}' 글감으로 자동 발행됩니다.`);
        loadAll();
      } else {
        alert("등록 실패: " + (data.detail || data.message || "알 수 없는 오류"));
      }
    } catch (e) {
      alert("등록 중 오류: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("이 예약을 삭제할까요?")) return;
    try {
      const res = await fetchWithAuth(`${scheduleBase}/${id}`, { method: "DELETE" });
      if (res.ok) loadAll();
    } catch (e) {
      alert("삭제 중 오류: " + e.message);
    }
  };

  // 매일 자동발행 일시정지/재개 (삭제하지 않고 껐다 켜기)
  const handleToggle = async (id) => {
    try {
      const res = await fetchWithAuth(`${scheduleBase}/${id}/toggle`, { method: "POST" });
      if (res.ok) loadAll();
      else alert("상태 변경 실패");
    } catch (e) {
      alert("오류: " + e.message);
    }
  };

  const labelStyle = { display: "block", fontSize: "0.85rem", fontWeight: "bold", marginBottom: "0.4rem", color: "#334155" };
  const inputStyle = { width: "100%", padding: "0.7rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box" };

  // 플랫폼에 따라 계정·예약 목록 소스 전환
  const isBlogspot = platform === "blogspot";
  const isTistory = platform === "tistory";
  const isNaver = platform === "naver";  // 카드뉴스·배포방식은 네이버 전용
  const activeAccounts = isBlogspot ? bsAccounts : isTistory ? tsAccounts : accounts;
  const activeSchedules = isBlogspot ? bsSchedules : isTistory ? tsSchedules : schedules;
  const switchPlatform = (p) => { setPlatform(p); setSelectedAccIds(new Set()); };

  const scheduleBase = isBlogspot ? "/api/blogspot/schedules" : isTistory ? "/api/tistory/schedules" : "/api/blog-schedule/schedules";

  // 티스토리 계정 추가 / 기기 인증
  const addTistoryAccount = async () => {
    if (!tsKakaoId.trim() || !tsBlogName.trim()) { alert("카카오 아이디와 블로그 주소(xxx)를 입력하세요."); return; }
    try {
      const res = await fetchWithAuth("/api/tistory/accounts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kakao_id: tsKakaoId, blog_name: tsBlogName }),
      });
      if (res.ok) { setTsKakaoId(""); setTsBlogName(""); loadAll(); alert("티스토리 계정이 추가되었습니다. 이제 '기기 인증'을 눌러 카카오 로그인을 완료하세요."); }
      else { const d = await res.json().catch(() => ({})); alert("추가 실패: " + (d.detail || res.status)); }
    } catch (e) { alert("오류: " + e.message); }
  };
  const registerTistoryAccount = async (id) => {
    try {
      const res = await fetchWithAuth(`/api/tistory/accounts/${id}/register`, { method: "POST" });
      const d = await res.json().catch(() => ({}));
      alert(res.ok ? (d.message || "PC 에이전트에서 로그인 창이 열립니다. 카카오 로그인을 완료하세요.") : ("기기 인증 요청 실패: " + (d.detail || res.status)));
    } catch (e) { alert("오류: " + e.message); }
  };
  const deleteTistoryAccount = async (id) => {
    if (!confirm("이 티스토리 계정을 삭제할까요?")) return;
    try { const res = await fetchWithAuth(`/api/tistory/accounts/${id}`, { method: "DELETE" }); if (res.ok) loadAll(); } catch (e) {}
  };

  return (
    <div style={{ padding: "2rem", boxSizing: "border-box" }}>
      {/* 발행 모드 탭 (블로그 발행 페이지와 동일 구성) */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", borderBottom: "2px solid #e2e8f0" }}>
        {[
          { href: "/blog-posting", label: "✍️ 블로그 발행 (수동·예약)" },
          { href: "/shopping-partners-blog", label: "🛍 쇼핑파트너스 블로그" },
          { href: "/hospital-blog", label: "🏥 병원 블로그" },
          { href: "/blog-schedule", label: "🗓️ 매일 자동 포스팅" },
        ].map(t => {
          const active = pathname === t.href;
          return (
            <Link key={t.href} href={t.href} style={{ padding: "0.7rem 1.2rem", textDecoration: "none", color: active ? "#2563eb" : "#64748b", fontWeight: "bold", borderBottom: active ? "3px solid #2563eb" : "3px solid transparent", marginBottom: "-2px" }}>{t.label}</Link>
          );
        })}
      </div>
      <h1 style={{ fontSize: "1.6rem", color: "#1e293b", marginBottom: "0.6rem" }}>🗓️ 블로그 매일 포스팅</h1>

      {/* 서브탭: 매일 자동발행 / 예약 포스팅 */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.2rem" }}>
        {[["daily", "📆 매일 자동발행"], ["reservation", "📌 예약 포스팅"]].map(([k, label]) => (
          <button key={k} onClick={() => setSubTab(k)} style={{ padding: "0.55rem 1.1rem", borderRadius: "999px", border: subTab === k ? "1px solid #2563eb" : "1px solid #cbd5e1", background: subTab === k ? "#2563eb" : "white", color: subTab === k ? "white" : "#475569", fontWeight: "bold", cursor: "pointer", fontSize: "0.9rem" }}>{label}</button>
        ))}
      </div>

      {/* 블로그 발행과 동일한 2단 레이아웃: 좌측 = 설정/폼, 우측 = 등록 목록(원고 검토·수정 위치) */}
      <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start", flexWrap: "wrap" }}>

        {/* ── 좌측: 설정 패널 ── */}
        <div style={{ flex: "1.5 1 420px", minWidth: 0, display: "flex", flexDirection: "column", gap: "1.5rem" }}>

          {subTab === "daily" && (
          <>
          {/* 플랫폼 선택: 네이버 / 블로그스팟 / 티스토리 */}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {[["naver", "N 네이버 블로그"], ["blogspot", "🅑 블로그스팟"], ["tistory", "🅣 티스토리"]].map(([k, label]) => (
              <button key={k} onClick={() => switchPlatform(k)} style={{ padding: "0.55rem 1.1rem", borderRadius: "8px", border: platform === k ? "2px solid #16a34a" : "1px solid #cbd5e1", background: platform === k ? "#f0fdf4" : "white", color: platform === k ? "#15803d" : "#475569", fontWeight: "bold", cursor: "pointer", fontSize: "0.9rem" }}>{label}</button>
            ))}
          </div>

          <p style={{ color: "#64748b", margin: 0 }}>
            글감 수집 카테고리에서 매일 같은 시각에 글감을 자동으로 뽑아 블로그에 발행합니다.
            매일 다른 글감이 순서대로 사용되며, 하루 1회만 발행됩니다.
          </p>

          {/* 안내 박스 — 플랫폼별 */}
          {isBlogspot && (
            <div style={{ background: "#eff6ff", border: "1px solid #93c5fd", borderRadius: "8px", padding: "0.9rem 1.1rem", fontSize: "0.85rem", color: "#1e40af" }}>
              ℹ️ 블로그스팟은 Blogger API로 <b>클라우드에서 자동 발행</b>됩니다(PC·에이전트 불필요). 계정은 <b>블로그스팟 메뉴</b>에서 먼저 등록하세요.
              원고 스타일은 <b>관리자 → 프롬프트 → 블로그스팟 자동배포(HTML)</b> 탭에서 설정합니다.
            </div>
          )}
          {isTistory && (
            <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: "8px", padding: "0.9rem 1.1rem", fontSize: "0.85rem", color: "#166534" }}>
              ℹ️ 티스토리는 API가 없어 <b>로컬 에이전트(집 PC)</b>가 브라우저로 발행합니다. 계정 추가 후 <b>기기 인증</b>(1회 카카오 수동 로그인)이 필요합니다. 원고 스타일은 <b>관리자 → 프롬프트 → 티스토리 자동배포</b> 탭에서 설정합니다.
            </div>
          )}
          {isNaver && (
            <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: "8px", padding: "0.9rem 1.1rem", fontSize: "0.85rem", color: "#92400e" }}>
              ⚠️ 예약 시각에 발행되려면 <b>백엔드 서버(8000)가 켜져 있어야</b> 합니다. PC를 껐다 켜면 시작하기.bat으로 서버를 다시 띄워주세요.
              또한 해당 계정은 <b>계정관리에서 기기 인증(1회 수동 로그인)</b>이 되어 있어야 자동 로그인됩니다.
            </div>
          )}
          {/* 티스토리 계정 관리(추가 + 기기 인증) */}
          {isTistory && (
            <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "10px", padding: "1.1rem 1.2rem" }}>
              <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.7rem" }}>티스토리 계정 관리</div>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
                <input value={tsKakaoId} onChange={(e) => setTsKakaoId(e.target.value)} placeholder="카카오 아이디(이메일)" style={{ ...inputStyle, width: "auto", flex: "1 1 180px" }} />
                <input value={tsBlogName} onChange={(e) => setTsBlogName(e.target.value)} placeholder="블로그 주소 (예: myblog → myblog.tistory.com)" style={{ ...inputStyle, width: "auto", flex: "1 1 220px" }} />
                <button onClick={addTistoryAccount} style={{ padding: "0.6rem 1rem", background: "#16a34a", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", whiteSpace: "nowrap" }}>＋ 계정 추가</button>
              </div>
              {tsAccounts.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {tsAccounts.map(a => (
                    <div key={a.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem", fontSize: "0.85rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "6px", padding: "0.4rem 0.7rem" }}>
                      <span><b>{a.blog_addr}</b>.tistory.com · {a.kakao_id}</span>
                      <span style={{ display: "flex", gap: "0.4rem" }}>
                        <button onClick={() => registerTistoryAccount(a.id)} style={{ padding: "0.3rem 0.7rem", background: "#2563eb", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", fontWeight: "bold" }}>기기 인증</button>
                        <button onClick={() => deleteTistoryAccount(a.id)} style={{ padding: "0.3rem 0.7rem", background: "#ef4444", color: "white", border: "none", borderRadius: "5px", cursor: "pointer" }}>삭제</button>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 등록 폼 */}
          <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "10px", padding: "1.5rem" }}>
            <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1.2rem" }}>새 예약 추가</h2>
            <div style={{ marginBottom: "1.1rem" }}>
              <label style={labelStyle}>발행 계정 <span style={{ fontWeight: "normal", color: "#94a3b8", fontSize: "0.8rem" }}>(여러 개 선택 가능 · 계정마다 다른 인기 글감으로 발행)</span></label>
              {activeAccounts.length === 0 ? (
                <div style={{ padding: "0.9rem", background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "6px", color: "#94a3b8", fontSize: "0.88rem" }}>
                  {isBlogspot ? "등록된 블로그스팟 계정이 없습니다. 블로그스팟 메뉴에서 먼저 등록하세요." : isTistory ? "등록된 티스토리 계정이 없습니다. 위 '티스토리 계정 관리'에서 추가 후 기기 인증하세요." : "등록된 네이버 계정이 없습니다. 계정관리에서 기기 인증 후 이용하세요."}
                </div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  {activeAccounts.map((a) => {
                    const on = selectedAccIds.has(a.id);
                    return (
                      <button key={a.id} type="button" onClick={() => toggleAcc(a.id)}
                        style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.5rem 0.9rem", borderRadius: "999px", border: on ? "1px solid #2563eb" : "1px solid #cbd5e1", background: on ? "#eff6ff" : "white", color: on ? "#1d4ed8" : "#475569", fontWeight: "bold", fontSize: "0.88rem", cursor: "pointer" }}>
                        <span style={{ width: 16, height: 16, borderRadius: 4, border: on ? "none" : "1px solid #cbd5e1", background: on ? "#2563eb" : "white", color: "white", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem" }}>{on ? "✓" : ""}</span>
                        {a.naver_id}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.1rem" }}>
              <div>
                <label style={labelStyle}>발행 시각 (매일)</label>
                <input type="time" value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>글감 카테고리</label>
                <select value={category} onChange={(e) => setCategory(e.target.value)} style={inputStyle}>
                  <option value="">카테고리 선택</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={labelStyle}>1일 발행 개수</label>
                <input type="number" min="1" max="10" value={count} onChange={(e) => setCount(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>AI 엔진</label>
                <select value={aiProvider} onChange={(e) => setAiProvider(e.target.value)} style={inputStyle}>
                  <option value="claude">Claude</option>
                  <option value="gemini">Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
              {isNaver && (
              <div>
                <label style={labelStyle}>배포 방식</label>
                <select value={distMode} onChange={(e) => setDistMode(e.target.value)} style={inputStyle}>
                  <option value="normal">일반배포 (1500자 이상)</option>
                  <option value="quick">막배포 (1500자 이내)</option>
                </select>
              </div>
              )}
            </div>
            {isNaver && (
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem", cursor: "pointer", fontSize: "0.9rem", color: cardNews ? "#2563eb" : "#64748b" }}>
              <input type="checkbox" checked={cardNews} onChange={(e) => setCardNews(e.target.checked)} style={{ width: 18, height: 18 }} />
              🎨 첨부 이미지가 없을 때 AI 카드뉴스 이미지 5장 자동 생성 (글 제목·소제목 기반)
            </label>
            )}
            <button
              onClick={handleAdd}
              disabled={loading}
              style={{ marginTop: "1.3rem", width: "100%", padding: "0.9rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", fontWeight: "bold", fontSize: "1rem", border: "none", borderRadius: "6px", cursor: loading ? "wait" : "pointer" }}>
              {loading ? "등록 중..." : "＋ 매일 자동발행 예약 추가"}
            </button>
          </div>
          </>
          )}

          {subTab === "reservation" && (
          <>
            <p style={{ color: "#64748b", margin: 0 }}>
              계정·글감·사진을 지정해 <b>원하는 날짜·시간에 1회</b> 자동 발행합니다. (예약 시각에 서버가 켜져 있어야 합니다)
            </p>

            <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "10px", padding: "1.5rem" }}>
              <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1.2rem" }}>새 예약 포스팅 추가</h2>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.1rem" }}>
                <div>
                  <label style={labelStyle}>발행 계정</label>
                  <select value={rAccountId} onChange={(e) => setRAccountId(e.target.value)} style={inputStyle}>
                    <option value="">계정 선택</option>
                    {accounts.map((a) => (<option key={a.id} value={a.id}>{a.naver_id}</option>))}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>타겟 키워드 (필수)</label>
                  <input type="text" value={rKeyword} onChange={(e) => setRKeyword(e.target.value)} placeholder="예: 전포동 맛집" style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>예약 날짜</label>
                  <input type="date" value={rDate} onChange={(e) => setRDate(e.target.value)} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>예약 시간</label>
                  <input type="time" value={rTime} onChange={(e) => setRTime(e.target.value)} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>AI 엔진</label>
                  <select value={rAi} onChange={(e) => setRAi(e.target.value)} style={inputStyle}>
                    <option value="claude">Claude</option><option value="gemini">Gemini</option><option value="openai">OpenAI</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>배포 방식</label>
                  <select value={rDist} onChange={(e) => setRDist(e.target.value)} style={inputStyle}>
                    <option value="normal">일반배포 (1500자 이상)</option><option value="quick">막배포 (1500자 이내)</option>
                  </select>
                </div>
              </div>
              <div style={{ marginTop: "1.1rem" }}>
                <label style={labelStyle}>글감 (선택 — 비우면 키워드만으로 작성)</label>
                <textarea value={rSource} onChange={(e) => setRSource(e.target.value)} rows={4} placeholder="발행할 글의 주제/내용/참고자료를 자유롭게 입력 (글감 수집·분석 내용을 붙여넣어도 됩니다)" style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }} />
              </div>
              <div style={{ marginTop: "1.1rem", display: "flex", alignItems: "center", gap: "0.8rem", flexWrap: "wrap" }}>
                <button type="button" onClick={() => setShowLibPicker(true)} style={{ padding: "0.6rem 1.1rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>🗂️ 보관함에서 사진 선택</button>
                {rImageFolder ? <span style={{ color: "#16a34a", fontWeight: "bold", fontSize: "0.9rem" }}>✅ 사진 {rImageCount}장 지정됨</span> : <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>사진 미지정 시 카드뉴스가 자동 생성됩니다(아래 옵션)</span>}
              </div>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem", cursor: "pointer", fontSize: "0.9rem", color: rCard ? "#2563eb" : "#64748b" }}>
                <input type="checkbox" checked={rCard} onChange={(e) => setRCard(e.target.checked)} style={{ width: 18, height: 18 }} />
                🎨 첨부 이미지가 없을 때 AI 카드뉴스 5장 자동 생성
              </label>
              <button onClick={handleAddReservation} disabled={rLoading} style={{ marginTop: "1.3rem", width: "100%", padding: "0.9rem", background: rLoading ? "#94a3b8" : "#2563eb", color: "white", fontWeight: "bold", fontSize: "1rem", border: "none", borderRadius: "6px", cursor: rLoading ? "wait" : "pointer" }}>
                {rLoading ? "등록 중..." : "＋ 예약 포스팅 추가"}
              </button>
            </div>
          </>
          )}
        </div>

        {/* ── 우측: 등록 목록 (블로그 발행의 '원고 검토·수정' 위치) ── */}
        <div style={{ flex: "1 1 340px", minWidth: 0, background: "white", border: "1px solid #cbd5e1", borderRadius: "10px", padding: "1.5rem", alignSelf: "stretch" }}>
          {subTab === "daily" ? (
          <>
            <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1rem" }}>등록된 예약 ({activeSchedules.length}) {isBlogspot ? "· 블로그스팟" : isTistory ? "· 티스토리" : "· 네이버"}</h2>
            {activeSchedules.length === 0 ? (
              <div style={{ background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "8px", padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                아직 등록된 예약이 없습니다. 왼쪽에서 첫 예약을 추가해 보세요.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                {activeSchedules.map((s) => (
                  <div key={s.id} style={{ background: s.is_active ? "#f8fafc" : "#fef2f2", border: s.is_active ? "1px solid #e2e8f0" : "1px solid #fecaca", borderRadius: "8px", padding: "1rem 1.2rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", opacity: s.is_active ? 1 : 0.75 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.3rem" }}>
                        ⏰ 매일 {s.schedule_time} · {s.naver_id}
                        {!s.is_active && <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", background: "#f59e0b", color: "white", padding: "0.1rem 0.5rem", borderRadius: "999px", fontWeight: "bold" }}>⏸ 일시정지</span>}
                      </div>
                      <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
                        카테고리: <b>{s.content_category || "—"}</b> · 1일 {s.post_count_per_day}개 · {s.ai_provider} · {s.distribution_mode === "quick" ? "막배포" : "일반배포"} · {s.generate_card_news ? "🎨 카드뉴스 ON" : "카드뉴스 OFF"}
                        {s.last_run_date ? <span style={{ marginLeft: "0.6rem", color: "#16a34a" }}>최근 발행: {s.last_run_date}</span> : <span style={{ marginLeft: "0.6rem", color: "#f59e0b" }}>아직 발행 전</span>}
                      </div>
                      {s.last_run_url && (
                        <div style={{ fontSize: "0.85rem", marginTop: "0.4rem" }}>
                          📄 <a href={s.last_run_url} target="_blank" rel="noreferrer" style={{ color: "#2563eb", fontWeight: "bold", textDecoration: "none" }}>
                            {s.last_run_title || "발행된 글 보기"}
                          </a>
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
                      <button
                        onClick={() => handleToggle(s.id)}
                        style={{ padding: "0.5rem 1rem", background: s.is_active ? "#f59e0b" : "#16a34a", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>
                        {s.is_active ? "⏸ 일시정지" : "▶ 재개"}
                      </button>
                      <button
                        onClick={() => handleDelete(s.id)}
                        style={{ padding: "0.5rem 1rem", background: "#ef4444", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>
                        삭제
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
          ) : (
          <>
            <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1rem" }}>예약된 포스팅 ({reservations.length})</h2>
            {reservations.length === 0 ? (
              <div style={{ background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "8px", padding: "2rem", textAlign: "center", color: "#94a3b8" }}>아직 예약된 포스팅이 없습니다.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                {reservations.map((r) => {
                  const st = r.status === "done" ? { t: "발행완료", c: "#16a34a", bg: "#dcfce7" } : r.status === "failed" ? { t: "실패", c: "#b91c1c", bg: "#fee2e2" } : { t: "대기중", c: "#b45309", bg: "#fef3c7" };
                  return (
                    <div key={r.id} style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1rem 1.2rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.3rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ fontSize: "0.72rem", padding: "0.12rem 0.5rem", borderRadius: "999px", background: st.bg, color: st.c, fontWeight: "bold" }}>{st.t}</span>
                          📌 {r.run_at} · {r.naver_id}
                        </div>
                        <div style={{ fontSize: "0.85rem", color: "#64748b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          키워드: <b>{r.keyword}</b> · {r.ai_provider} · {r.distribution_mode === "quick" ? "막배포" : "일반배포"} · {r.has_image ? "🖼️ 사진" : (r.generate_card_news ? "🎨 카드뉴스" : "이미지 없음")}
                          {r.result_url && <a href={r.result_url} target="_blank" rel="noreferrer" style={{ marginLeft: "0.5rem", color: "#2563eb" }}>결과 보기</a>}
                        </div>
                      </div>
                      <button onClick={() => handleDeleteReservation(r.id)} style={{ padding: "0.5rem 1rem", background: "#ef4444", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>삭제</button>
                    </div>
                  );
                })}
              </div>
            )}
          </>
          )}
        </div>
      </div>

      {/* 보관함 사진 선택 모달 (공용 컴포넌트) */}
      <LibraryPickerModal
        open={showLibPicker}
        onClose={() => setShowLibPicker(false)}
        onUse={(folder, count) => { setRImageFolder(folder); setRImageCount(count); setShowLibPicker(false); }}
      />
    </div>
  );
}
