"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";

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

  const loadAll = async () => {
    try {
      const [accRes, catRes, schRes] = await Promise.all([
        fetchWithAuth("/api/cafe-nurture/accounts"),
        fetchWithAuth("/api/content/categories"),
        fetchWithAuth("/api/blog-schedule/schedules"),
      ]);
      const accData = accRes.ok ? await accRes.json() : [];
      const catData = catRes.ok ? await catRes.json() : {};
      const schData = schRes.ok ? await schRes.json() : [];
      setAccounts(accData || []);
      setCategories(catData.categories || []);
      setSchedules(schData || []);
      if (!accountId && accData && accData.length > 0) setAccountId(accData[0].id);
      if (!category && catData.categories && catData.categories.length > 0) setCategory(catData.categories[0]);
    } catch (e) {
      console.error(e);
    }
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
      <h1 style={{ fontSize: "1.6rem", color: "#1e293b", marginBottom: "0.3rem" }}>🗓️ 블로그 매일 자동발행</h1>
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
    </div>
  );
}
