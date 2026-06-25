"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect } from "react";

// 네이버 계정 관리 (설정 페이지에 인라인으로 바로 노출)
export default function AccountManager() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  const [form, setForm] = useState({ naver_id: "", naver_pw: "", blog_addr: "" });
  const [aiKeys, setAiKeys] = useState({ claude: "", gemini: "", openai: "", has: {} });
  const [aiInput, setAiInput] = useState({ claude_key: "", gemini_key: "", openai_key: "" });
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState({ blog_addr: "", naver_pw: "" });
  const [authState, setAuthState] = useState({}); // accountId -> { status, message }

  const notify = (type, text) => { setMsg({ type, text }); setTimeout(() => setMsg(null), 3000); };

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/accounts");
      if (res.ok) setAccounts((await res.json()).accounts || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const loadAiKeys = async () => {
    try {
      const res = await fetchWithAuth("/api/accounts/ai-keys");
      if (res.ok) setAiKeys(await res.json());
    } catch (e) { /* ignore */ }
  };

  const saveAiKeys = async () => {
    const body = {};
    if (aiInput.claude_key.trim()) body.claude_key = aiInput.claude_key.trim();
    if (aiInput.gemini_key.trim()) body.gemini_key = aiInput.gemini_key.trim();
    if (aiInput.openai_key.trim()) body.openai_key = aiInput.openai_key.trim();
    if (Object.keys(body).length === 0) return notify("error", "입력된 키가 없습니다. (삭제는 '-' 입력)");
    try {
      const res = await fetchWithAuth("/api/accounts/ai-keys", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "저장 실패");
      notify("success", data.message || "AI 키가 저장되었습니다.");
      setAiInput({ claude_key: "", gemini_key: "", openai_key: "" });
      loadAiKeys();
    } catch (e) { notify("error", e.message); }
  };

  useEffect(() => { load(); loadAiKeys(); }, []);

  const addAccount = async () => {
    if (!form.naver_id.trim()) return notify("error", "네이버 아이디를 입력하세요.");
    try {
      const res = await fetchWithAuth("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "추가 실패");
      notify("success", data.message || "추가되었습니다.");
      setForm({ naver_id: "", naver_pw: "", blog_addr: "" });
      load();
    } catch (e) {
      notify("error", e.message);
    }
  };

  const startEdit = (a) => { setEditId(a.id); setEditForm({ blog_addr: a.blog_addr || "", naver_pw: "" }); };

  const saveEdit = async (id) => {
    try {
      const body = { blog_addr: editForm.blog_addr };
      if (editForm.naver_pw) body.naver_pw = editForm.naver_pw;
      const res = await fetchWithAuth(`/api/accounts/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "수정 실패");
      notify("success", "수정되었습니다.");
      setEditId(null);
      load();
    } catch (e) {
      notify("error", e.message);
    }
  };

  const removeAccount = async (a) => {
    if (!window.confirm(`'${a.naver_id}' 계정을 삭제할까요?\n디바이스 인증(자동 로그인) 프로필도 함께 제거됩니다.`)) return;
    try {
      const res = await fetchWithAuth(`/api/accounts/${a.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error((await res.json()).detail || "삭제 실패");
      notify("success", "삭제되었습니다.");
      load();
    } catch (e) {
      notify("error", e.message);
    }
  };

  const startDeviceAuth = async (a) => {
    setAuthState((s) => ({ ...s, [a.id]: { status: "running", message: "브라우저 실행 중..." } }));
    try {
      const res = await fetchWithAuth(`/api/accounts/${a.id}/register-device`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "기기 인증 시작 실패");
      notify("success", data.message || "기기 인증을 시작했습니다.");

      let attempts = 0;
      const poll = async () => {
        if (attempts++ > 180) { // 약 6분 안전 한도
          setAuthState((s) => ({ ...s, [a.id]: { status: "failed", message: "시간이 초과되었습니다." } }));
          return;
        }
        try {
          const r = await fetchWithAuth(`/api/accounts/${a.id}/register-device/status`);
          if (r.ok) {
            const st = await r.json();
            setAuthState((s) => ({ ...s, [a.id]: { status: st.status, message: st.message } }));
            if (st.status === "running") { setTimeout(poll, 2000); return; }
            if (st.status === "completed") { notify("success", st.message || "기기 인증 완료"); load(); return; }
            if (st.status === "failed") { notify("error", st.message || "기기 인증 실패"); return; }
          }
        } catch (e) {
          // 일시적 통신 오류는 재시도
        }
        setTimeout(poll, 2000);
      };
      setTimeout(poll, 2000);
    } catch (e) {
      setAuthState((s) => ({ ...s, [a.id]: { status: "failed", message: e.message } }));
      notify("error", e.message);
    }
  };

  const fmtDate = (iso) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" }); }
    catch { return iso; }
  };

  const th = { padding: "0.7rem 0.8rem", textAlign: "left", fontSize: "0.85rem", color: "#475569", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" };
  const td = { padding: "0.7rem 0.8rem", borderBottom: "1px solid #f1f5f9", fontSize: "0.9rem", color: "#1e293b" };
  const inp = { padding: "0.55rem", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.9rem" };

  return (
    <div>
      {msg && (
        <div style={{ padding: "0.8rem 1rem", marginBottom: "1rem", borderRadius: "8px",
          background: msg.type === "success" ? "#f0fdf4" : "#fef2f2",
          color: msg.type === "success" ? "#166534" : "#991b1b",
          border: `1px solid ${msg.type === "success" ? "#bbf7d0" : "#fecaca"}` }}>{msg.text}</div>
      )}

      {/* BYOK: 내 AI 키 (설치형 고객) */}
      <div style={{ border: "1px solid #e2e8f0", borderRadius: "10px", padding: "1.2rem", marginBottom: "1.5rem", background: "#fafafa" }}>
        <div style={{ fontWeight: "bold", color: "#1e293b", marginBottom: "0.3rem" }}>🔑 내 AI 키 (글감/원고 생성용)</div>
        <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: 0, marginBottom: "0.8rem" }}>
          본인 Claude/Gemini 키를 입력하면 <b>글 생성 비용이 본인 계정에 청구</b>됩니다(설치형). 비워두면 서버 기본 키가 사용됩니다.
          현재: Claude {aiKeys.has?.claude ? `✅ ${aiKeys.claude}` : "미설정"} · Gemini {aiKeys.has?.gemini ? `✅ ${aiKeys.gemini}` : "미설정"} · OpenAI {aiKeys.has?.openai ? `✅ ${aiKeys.openai}` : "미설정"}
        </p>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
          <input style={{ ...inp, flex: 1, minWidth: "180px" }} type="password" placeholder="Claude(Anthropic) 키" value={aiInput.claude_key} onChange={(e) => setAiInput({ ...aiInput, claude_key: e.target.value })} />
          <input style={{ ...inp, flex: 1, minWidth: "180px" }} type="password" placeholder="Gemini 키" value={aiInput.gemini_key} onChange={(e) => setAiInput({ ...aiInput, gemini_key: e.target.value })} />
          <input style={{ ...inp, flex: 1, minWidth: "180px" }} type="password" placeholder="OpenAI 키(선택)" value={aiInput.openai_key} onChange={(e) => setAiInput({ ...aiInput, openai_key: e.target.value })} />
          <button onClick={saveAiKeys} style={{ padding: "0.6rem 1.2rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>키 저장</button>
        </div>
        <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "0.5rem" }}>* 삭제하려면 해당 칸에 <b>-</b> 입력 후 저장. 키는 마스킹되어 표시됩니다.</div>
      </div>

      {/* 추가 폼 */}
      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center", marginBottom: "1.2rem" }}>
        <input style={{ ...inp, flex: 1, minWidth: "140px" }} placeholder="네이버 아이디" value={form.naver_id} onChange={(e) => setForm({ ...form, naver_id: e.target.value })} />
        <input style={{ ...inp, flex: 1, minWidth: "140px" }} type="password" placeholder="비밀번호(선택)" value={form.naver_pw} onChange={(e) => setForm({ ...form, naver_pw: e.target.value })} />
        <input style={{ ...inp, flex: 1, minWidth: "160px" }} placeholder="블로그 주소(선택, 예: bonetacasa)" value={form.blog_addr} onChange={(e) => setForm({ ...form, blog_addr: e.target.value })} />
        <button onClick={addAccount} style={{ padding: "0.6rem 1.2rem", background: "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>+ 계정 추가</button>
      </div>

      {/* 목록 */}
      <div style={{ border: "1px solid #e2e8f0", borderRadius: "10px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={th}>네이버 아이디</th>
              <th style={th}>블로그 주소</th>
              <th style={th}>등록일</th>
              <th style={th}>인증여부</th>
              <th style={{ ...th, textAlign: "center" }}>관리</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td style={{ ...td, textAlign: "center", color: "#94a3b8" }} colSpan={5}>불러오는 중...</td></tr>
            ) : accounts.length === 0 ? (
              <tr><td style={{ ...td, textAlign: "center", color: "#94a3b8" }} colSpan={5}>등록된 계정이 없습니다. 위에서 추가하세요.</td></tr>
            ) : accounts.map((a) => (
              <tr key={a.id}>
                <td style={{ ...td, fontWeight: "bold" }}>{a.naver_id}</td>
                <td style={td}>
                  {editId === a.id ? (
                    <input style={{ ...inp, width: "150px" }} placeholder="예: bonetacasa" value={editForm.blog_addr} onChange={(e) => setEditForm({ ...editForm, blog_addr: e.target.value })} />
                  ) : (a.blog_addr || <span style={{ color: "#cbd5e1" }}>(아이디와 동일)</span>)}
                </td>
                <td style={{ ...td, color: "#64748b" }}>{fmtDate(a.created_at)}</td>
                <td style={td}>
                  {(() => {
                    const auth = authState[a.id];
                    const running = auth?.status === "running";
                    return (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", alignItems: "flex-start" }}>
                        {a.registered ? (
                          <span style={{ background: "#dcfce7", color: "#166534", padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: "bold" }}>✅ 인증완료</span>
                        ) : (
                          <span style={{ background: "#fef3c7", color: "#b45309", padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.8rem" }}>⚠️ 미인증</span>
                        )}
                        {running ? (
                          <span style={{ color: "#2563eb", fontSize: "0.78rem" }}>🔄 {auth.message || "인증 진행 중..."}</span>
                        ) : (
                          <button
                            onClick={() => startDeviceAuth(a)}
                            style={{ padding: "0.25rem 0.6rem", background: a.registered ? "white" : "#f59e0b", color: a.registered ? "#b45309" : "white", border: a.registered ? "1px solid #f59e0b" : "none", borderRadius: "6px", fontSize: "0.78rem", fontWeight: "bold", cursor: "pointer" }}>
                            {a.registered ? "재인증" : "기기인증"}
                          </button>
                        )}
                      </div>
                    );
                  })()}
                </td>
                <td style={{ ...td, textAlign: "center", whiteSpace: "nowrap" }}>
                  {editId === a.id ? (
                    <>
                      <button onClick={() => saveEdit(a.id)} style={{ padding: "0.35rem 0.7rem", background: "#10b981", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", marginRight: "0.35rem" }}>저장</button>
                      <button onClick={() => setEditId(null)} style={{ padding: "0.35rem 0.7rem", background: "white", color: "#64748b", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer" }}>취소</button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => startEdit(a)} style={{ padding: "0.35rem 0.7rem", background: "white", color: "#2563eb", border: "1px solid #2563eb", borderRadius: "6px", cursor: "pointer", marginRight: "0.35rem" }}>수정</button>
                      <button onClick={() => removeAccount(a)} style={{ padding: "0.35rem 0.7rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "6px", cursor: "pointer" }}>삭제</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ marginTop: "1rem", fontSize: "0.85rem", color: "#94a3b8" }}>
        * 블로그/카페 포스팅 화면에서 계정을 추가하면 여기에도 자동 등록됩니다. 블로그 주소는 로그인 아이디와 블로그 URL이 다를 때만 입력하세요(예: 로그인 ch_2101 / 블로그 bonetacasa).
      </p>
      <p style={{ marginTop: "0.4rem", fontSize: "0.85rem", color: "#94a3b8" }}>
        * <b>기기인증</b>: 버튼을 누르면 브라우저 창이 떠 저장된 ID/PW로 자동 로그인합니다. 캡챠·2단계 인증이 뜨면 창에서 직접 완료하세요. 1회 인증하면 이후 자동 작업에서 재로그인 없이 사용됩니다(미인증 계정은 새 기기 차단으로 로그인 실패할 수 있음).
      </p>
    </div>
  );
}
