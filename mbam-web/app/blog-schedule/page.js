"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";
import Link from "next/link";

export default function BlogSchedulePage() {
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(false);

  // form state
  const [accountId, setAccountId] = useState("");
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
  const [libImages, setLibImages] = useState([]);
  const [libSelected, setLibSelected] = useState(() => new Set());
  const [libStaging, setLibStaging] = useState(false);

  const loadAll = async () => {
    try {
      const [accRes, catRes, schRes, resvRes] = await Promise.all([
        fetchWithAuth("/api/cafe-nurture/accounts"),
        fetchWithAuth("/api/content/categories"),
        fetchWithAuth("/api/blog-schedule/schedules"),
        fetchWithAuth("/api/blog-schedule/reservations"),
      ]);
      const accData = accRes.ok ? await accRes.json() : [];
      const catData = catRes.ok ? await catRes.json() : {};
      const schData = schRes.ok ? await schRes.json() : [];
      const resvData = resvRes.ok ? await resvRes.json() : [];
      setAccounts(accData || []);
      setCategories(catData.categories || []);
      setSchedules(schData || []);
      setReservations(resvData || []);
      if (!accountId && accData && accData.length > 0) setAccountId(accData[0].id);
      if (!rAccountId && accData && accData.length > 0) setRAccountId(accData[0].id);
      if (!category && catData.categories && catData.categories.length > 0) setCategory(catData.categories[0]);
    } catch (e) {
      console.error(e);
    }
  };

  const openLibPicker = async () => {
    setShowLibPicker(true);
    try {
      const res = await fetchWithAuth("/api/settings/wash-library");
      if (res.ok) { const d = await res.json(); const items = d.items || []; setLibImages(items); setLibSelected(new Set(items.map(i => i.filename))); }
    } catch (e) {}
  };
  const toggleLibImage = (fn) => setLibSelected(prev => { const n = new Set(prev); n.has(fn) ? n.delete(fn) : n.add(fn); return n; });
  const useLibImages = async () => {
    const picked = Array.from(libSelected);
    if (picked.length === 0) { alert("사용할 이미지를 1장 이상 선택하세요."); return; }
    setLibStaging(true);
    try {
      const res = await fetchWithAuth("/api/settings/wash-library/stage", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filenames: picked }) });
      const d = await res.json();
      if (res.ok && d.success && d.folder) { setRImageFolder(d.folder); setRImageCount(d.count); setShowLibPicker(false); }
      else alert("이미지 지정 실패");
    } catch (e) { alert("오류: " + e.message); } finally { setLibStaging(false); }
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

  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, []);

  const handleAdd = async () => {
    if (!accountId) { alert("발행할 네이버 계정을 선택하세요. (계정관리에서 기기 인증된 계정이 필요합니다)"); return; }
    if (!category) { alert("글감 카테고리를 선택하세요. (글감 수집 메뉴에서 먼저 수집해야 글감이 생깁니다)"); return; }
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/blog-schedule/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: accountId,
          schedule_time: scheduleTime,
          content_category: category,
          post_count_per_day: Number(count) || 1,
          ai_provider: aiProvider,
          distribution_mode: distMode,
          generate_card_news: cardNews,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        alert("✅ 매일 자동발행 예약이 등록되었습니다!\n매일 " + scheduleTime + "에 '" + category + "' 글감으로 자동 발행됩니다.");
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
      const res = await fetchWithAuth(`/api/blog-schedule/schedules/${id}`, { method: "DELETE" });
      if (res.ok) loadAll();
    } catch (e) {
      alert("삭제 중 오류: " + e.message);
    }
  };

  const labelStyle = { display: "block", fontSize: "0.85rem", fontWeight: "bold", marginBottom: "0.4rem", color: "#334155" };
  const inputStyle = { width: "100%", padding: "0.7rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box" };

  return (
    <div style={{ maxWidth: "920px", margin: "0 auto", padding: "2rem 1rem" }}>
      {/* 발행 모드 탭 */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", borderBottom: "2px solid #e2e8f0" }}>
        <Link href="/blog-posting" style={{ padding: "0.7rem 1.2rem", textDecoration: "none", color: "#64748b", fontWeight: "bold", borderBottom: "3px solid transparent", marginBottom: "-2px" }}>✍️ 블로그 발행 (수동·예약)</Link>
        <Link href="/blog-schedule" style={{ padding: "0.7rem 1.2rem", textDecoration: "none", color: "#2563eb", fontWeight: "bold", borderBottom: "3px solid #2563eb", marginBottom: "-2px" }}>🗓️ 매일 자동 포스팅</Link>
      </div>
      <h1 style={{ fontSize: "1.6rem", color: "#1e293b", marginBottom: "0.6rem" }}>🗓️ 블로그 매일 포스팅</h1>

      {/* 서브탭: 매일 자동발행 / 예약 포스팅 */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.2rem" }}>
        {[["daily", "📆 매일 자동발행"], ["reservation", "📌 예약 포스팅"]].map(([k, label]) => (
          <button key={k} onClick={() => setSubTab(k)} style={{ padding: "0.55rem 1.1rem", borderRadius: "999px", border: subTab === k ? "1px solid #2563eb" : "1px solid #cbd5e1", background: subTab === k ? "#2563eb" : "white", color: subTab === k ? "white" : "#475569", fontWeight: "bold", cursor: "pointer", fontSize: "0.9rem" }}>{label}</button>
        ))}
      </div>

      {subTab === "daily" && (
      <>
      <p style={{ color: "#64748b", margin: "0 0 1.5rem" }}>
        글감 수집 카테고리에서 매일 같은 시각에 글감을 자동으로 뽑아 블로그에 발행합니다.
        매일 다른 글감이 순서대로 사용되며, 하루 1회만 발행됩니다.
      </p>

      {/* 안내 박스 */}
      <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: "8px", padding: "0.9rem 1.1rem", marginBottom: "1.5rem", fontSize: "0.85rem", color: "#92400e" }}>
        ⚠️ 예약 시각에 발행되려면 <b>백엔드 서버(8000)가 켜져 있어야</b> 합니다. PC를 껐다 켜면 시작하기.bat으로 서버를 다시 띄워주세요.
        또한 해당 계정은 <b>계정관리에서 기기 인증(1회 수동 로그인)</b>이 되어 있어야 자동 로그인됩니다.
      </div>

      {/* 등록 폼 */}
      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.5rem", marginBottom: "2rem" }}>
        <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1.2rem" }}>새 예약 추가</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.1rem" }}>
          <div>
            <label style={labelStyle}>발행 계정</label>
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)} style={inputStyle}>
              <option value="">계정 선택</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.naver_id}</option>
              ))}
            </select>
          </div>
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
          <div>
            <label style={labelStyle}>배포 방식</label>
            <select value={distMode} onChange={(e) => setDistMode(e.target.value)} style={inputStyle}>
              <option value="normal">일반배포 (1500자 이상)</option>
              <option value="quick">막배포 (1500자 이내)</option>
            </select>
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem", cursor: "pointer", fontSize: "0.9rem", color: cardNews ? "#2563eb" : "#64748b" }}>
          <input type="checkbox" checked={cardNews} onChange={(e) => setCardNews(e.target.checked)} style={{ width: 18, height: 18 }} />
          🎨 첨부 이미지가 없을 때 AI 카드뉴스 이미지 5장 자동 생성 (글 제목·소제목 기반)
        </label>
        <button
          onClick={handleAdd}
          disabled={loading}
          style={{ marginTop: "1.3rem", width: "100%", padding: "0.9rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", fontWeight: "bold", fontSize: "1rem", border: "none", borderRadius: "6px", cursor: loading ? "wait" : "pointer" }}>
          {loading ? "등록 중..." : "＋ 매일 자동발행 예약 추가"}
        </button>
      </div>

      {/* 예약 목록 */}
      <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1rem" }}>등록된 예약 ({schedules.length})</h2>
      {schedules.length === 0 ? (
        <div style={{ background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "8px", padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
          아직 등록된 예약이 없습니다. 위에서 첫 예약을 추가해 보세요.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
          {schedules.map((s) => (
            <div key={s.id} style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1rem 1.2rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.3rem" }}>
                  ⏰ 매일 {s.schedule_time} · {s.naver_id}
                </div>
                <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
                  카테고리: <b>{s.content_category || "—"}</b> · 1일 {s.post_count_per_day}개 · {s.ai_provider} · {s.distribution_mode === "quick" ? "막배포" : "일반배포"} · {s.generate_card_news ? "🎨 카드뉴스 ON" : "카드뉴스 OFF"}
                  {s.last_run_date ? <span style={{ marginLeft: "0.6rem", color: "#16a34a" }}>최근 발행: {s.last_run_date}</span> : <span style={{ marginLeft: "0.6rem", color: "#f59e0b" }}>아직 발행 전</span>}
                </div>
              </div>
              <button
                onClick={() => handleDelete(s.id)}
                style={{ padding: "0.5rem 1rem", background: "#ef4444", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>
                삭제
              </button>
            </div>
          ))}
        </div>
      )}
      </>
      )}

      {subTab === "reservation" && (
      <>
        <p style={{ color: "#64748b", margin: "0 0 1.5rem" }}>
          계정·글감·사진을 지정해 <b>원하는 날짜·시간에 1회</b> 자동 발행합니다. (예약 시각에 서버가 켜져 있어야 합니다)
        </p>

        <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.5rem", marginBottom: "2rem" }}>
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
            <button type="button" onClick={openLibPicker} style={{ padding: "0.6rem 1.1rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>🗂️ 보관함에서 사진 선택</button>
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

        <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: "0 0 1rem" }}>예약된 포스팅 ({reservations.length})</h2>
        {reservations.length === 0 ? (
          <div style={{ background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "8px", padding: "2rem", textAlign: "center", color: "#94a3b8" }}>아직 예약된 포스팅이 없습니다.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
            {reservations.map((r) => {
              const st = r.status === "done" ? { t: "발행완료", c: "#16a34a", bg: "#dcfce7" } : r.status === "failed" ? { t: "실패", c: "#b91c1c", bg: "#fee2e2" } : { t: "대기중", c: "#b45309", bg: "#fef3c7" };
              return (
                <div key={r.id} style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1rem 1.2rem", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
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

      {/* 보관함 사진 선택 모달 */}
      {showLibPicker && (
        <div onClick={() => setShowLibPicker(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "white", borderRadius: "12px", padding: "1.5rem", width: "640px", maxWidth: "92vw", maxHeight: "82vh", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b" }}>🗂️ 보관함에서 사진 선택 <span style={{ fontSize: "0.85rem", color: "#94a3b8", fontWeight: "normal" }}>(선택 {libSelected.size}/{libImages.length})</span></h3>
              <button onClick={() => setShowLibPicker(false)} style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#94a3b8" }}>✕</button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "0.8rem" }}>
              {libImages.length === 0 ? (
                <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8", fontSize: "0.9rem" }}>보관함이 비어 있습니다. 이미지 세탁소에서 저장 후 이용하세요.</div>
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
              {libStaging ? "지정 중..." : `선택한 ${libSelected.size}장 사용`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
