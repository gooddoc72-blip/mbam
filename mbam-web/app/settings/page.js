"use client";
import { fetchWithAuth } from "../utils/api";
import { IS_BLOG_EDITION } from "../utils/product";
import { useState, useEffect } from "react";
import { Save, Key, AlertCircle } from "lucide-react";

export default function SettingsPage() {
    // 비밀번호 변경
    const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
    const [pwLoading, setPwLoading] = useState(false);
    const [pwMessage, setPwMessage] = useState(null);

    // AI API 키 (BYOK) — 설치형은 고객이 본인 키를 넣어야 글·댓글 생성이 된다.
    // 저장된 키는 서버가 마스킹해서만 돌려주므로, 입력란은 항상 비워두고 새로 넣을 때만 채운다.
    const [aiKeys, setAiKeys] = useState({ claude_key: "", gemini_key: "", openai_key: "" });
    const [aiSaved, setAiSaved] = useState({ claude: "", gemini: "", openai: "" });
    const [aiHas, setAiHas] = useState({ claude: false, gemini: false, openai: false });
    const [aiLoading, setAiLoading] = useState(false);
    const [aiMessage, setAiMessage] = useState(null);

    // 계정 동기화 — 여러 PC 에서 같은 네이버 계정 목록 쓰기
    const [syncForm, setSyncForm] = useState({ email: "", password: "" });
    const [syncLoading, setSyncLoading] = useState("");   // "" | "upload" | "download"
    const [syncMessage, setSyncMessage] = useState(null);

    // 카페 AI 댓글 프롬프트
    const [cmtPrompt, setCmtPrompt] = useState("");
    const [cmtDefault, setCmtDefault] = useState("");
    const [cmtPlaceholders, setCmtPlaceholders] = useState({});
    const [cmtLoading, setCmtLoading] = useState(false);
    const [cmtMessage, setCmtMessage] = useState(null);

    // 카페 원고 추가 지시 (정보성 / 맛집)
    const [postPrompts, setPostPrompts] = useState({});   // { cafe: {label, prompt}, cafe_matjip: {...} }
    const [postHelp, setPostHelp] = useState("");
    const [postSaving, setPostSaving] = useState("");
    const [postMessage, setPostMessage] = useState(null);

    useEffect(() => {
        fetchAiKeys();
        fetchCmtPrompt();
        fetchPostPrompts();
    }, []);

    const fetchPostPrompts = async () => {
        try {
            const res = await fetchWithAuth("/api/cafe-nurture/post-prompt");
            if (res.ok) {
                const d = await res.json();
                setPostPrompts(d.items || {});
                setPostHelp(d.help || "");
            }
        } catch (e) { console.error(e); }
    };

    const savePostPrompt = async (key) => {
        setPostSaving(key); setPostMessage(null);
        try {
            const res = await fetchWithAuth("/api/cafe-nurture/post-prompt", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ category: key, prompt: postPrompts[key]?.prompt || "" }),
            });
            const d = await res.json().catch(() => ({}));
            if (res.ok) setPostMessage({ type: "success", text: d.message || "저장되었습니다." });
            else setPostMessage({ type: "error", text: d.detail || `실패 (HTTP ${res.status})` });
        } catch (e) { setPostMessage({ type: "error", text: "서버와 연결할 수 없습니다: " + e.message }); }
        setPostSaving("");
    };

    const fetchCmtPrompt = async () => {
        try {
            const res = await fetchWithAuth("/api/cafe-nurture/comment-prompt");
            if (res.ok) {
                const d = await res.json();
                setCmtPrompt(d.prompt || d.default || "");
                setCmtDefault(d.default || "");
                setCmtPlaceholders(d.placeholders || {});
            }
        } catch (e) { console.error(e); }
    };

    const saveCmtPrompt = async (reset = false) => {
        if (reset && !confirm("기본 프롬프트로 되돌립니다. 계속할까요?")) return;
        setCmtLoading(true); setCmtMessage(null);
        try {
            const res = await fetchWithAuth("/api/cafe-nurture/comment-prompt", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: reset ? "" : cmtPrompt }),
            });
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                setCmtMessage({ type: "success", text: d.message || "저장되었습니다." });
                if (reset) setCmtPrompt(cmtDefault);
            } else setCmtMessage({ type: "error", text: d.detail || `실패 (HTTP ${res.status})` });
        } catch (e) { setCmtMessage({ type: "error", text: "서버와 연결할 수 없습니다: " + e.message }); }
        setCmtLoading(false);
    };

    const runSync = async (kind) => {
        if (!syncForm.email.trim() || !syncForm.password) {
            setSyncMessage({ type: "error", text: "이메일과 비밀번호를 입력하세요." });
            return;
        }
        if (kind === "download" &&
            !confirm("서버에 저장된 계정을 이 PC 로 가져옵니다.\n같은 아이디는 서버 값으로 갱신되고, 이 PC 에만 있는 계정은 그대로 둡니다.\n\n계속할까요?")) return;
        setSyncLoading(kind); setSyncMessage(null);
        try {
            const res = await fetchWithAuth(`/api/sync/${kind}`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: syncForm.email.trim(), password: syncForm.password }),
            });
            const d = await res.json().catch(() => ({}));
            if (res.ok) setSyncMessage({ type: "success", text: d.message || "완료되었습니다." });
            else setSyncMessage({ type: "error", text: d.detail || `실패 (HTTP ${res.status})` });
        } catch (e) {
            setSyncMessage({ type: "error", text: "서버와 연결할 수 없습니다: " + e.message });
        }
        setSyncLoading("");
    };

    const fetchAiKeys = async () => {
        try {
            const res = await fetchWithAuth("/api/accounts/ai-keys");
            if (res.ok) {
                const d = await res.json();
                setAiSaved({ claude: d.claude || "", gemini: d.gemini || "", openai: d.openai || "" });
                setAiHas(d.has || { claude: false, gemini: false, openai: false });
            }
        } catch (e) { console.error("Failed to fetch AI keys:", e); }
    };

    const handleSaveAiKeys = async () => {
        // 서버는 '전달된 값만' 갱신한다(빈 값은 무시). 지우려면 "-" 를 넣는다.
        const body = {};
        ["claude_key", "gemini_key", "openai_key"].forEach(k => {
            if (aiKeys[k].trim()) body[k] = aiKeys[k].trim();
        });
        if (Object.keys(body).length === 0) {
            setAiMessage({ type: "error", text: "저장할 키를 입력하세요. (지우려면 - 한 글자를 넣으세요)" });
            return;
        }
        setAiLoading(true); setAiMessage(null);
        try {
            const res = await fetchWithAuth("/api/accounts/ai-keys", {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
            });
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                setAiMessage({ type: "success", text: d.message || "AI 키가 저장되었습니다." });
                setAiKeys({ claude_key: "", gemini_key: "", openai_key: "" });
                fetchAiKeys();
            } else {
                setAiMessage({ type: "error", text: "저장 실패: " + (d.detail || res.status) });
            }
        } catch (e) { setAiMessage({ type: "error", text: "서버와 연결할 수 없습니다: " + e.message }); }
        setAiLoading(false);
    };

    const handleChangePassword = async () => {
        setPwMessage(null);
        if (!pwForm.current || !pwForm.next) {
            setPwMessage({ type: "error", text: "현재 비밀번호와 새 비밀번호를 입력해주세요." });
            return;
        }
        if (pwForm.next.length < 8) {
            setPwMessage({ type: "error", text: "새 비밀번호는 8자 이상이어야 합니다." });
            return;
        }
        if (pwForm.next !== pwForm.confirm) {
            setPwMessage({ type: "error", text: "새 비밀번호가 서로 일치하지 않습니다." });
            return;
        }
        setPwLoading(true);
        try {
            const res = await fetchWithAuth("/api/auth/change-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.next })
            });
            const data = await res.json();
            if (res.ok) {
                setPwMessage({ type: "success", text: data.message || "비밀번호가 변경되었습니다." });
                setPwForm({ current: "", next: "", confirm: "" });
            } else {
                setPwMessage({ type: "error", text: data.detail || "비밀번호 변경에 실패했습니다." });
            }
        } catch (error) {
            setPwMessage({ type: "error", text: `서버와 연결할 수 없습니다: ${error.message}` });
        }
        setPwLoading(false);
    };

    return (
        <div style={{ padding: "1rem", maxWidth: "1400px", margin: "0 auto" }}>
            <h1 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#1e293b", marginBottom: "2rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Settings /> 환경 설정
            </h1>

            {/* 카드를 좌우 2단으로 배열한다. 세로로만 쌓으면 화면이 지나치게 길어져
                아래쪽 항목(AI API 키 등)을 매번 스크롤해서 찾아야 했다.
                폭이 좁아지면(노트북·창 축소) 자동으로 1단이 된다. */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: "1.5rem", alignItems: "start" }}>
            {/* 카페 전용 설정 — 블로그 전용판에는 카페 화면이 없으므로 감춘다.
                (엔드포인트는 /api/cafe-nurture 라 살아 있지만, 쓰지도 않는 설정을
                 두면 고객이 "이건 뭐냐"고 묻는다) */}
            {!IS_BLOG_EDITION && (<>
            {/* 카페 AI 댓글 프롬프트 */}
            <div style={{
                background: "white", borderRadius: "16px", padding: "2rem",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)"
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid #e2e8f0" }}>
                    <Key size={24} color="#e11d48" />
                    <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#334155", margin: 0 }}>카페 AI 댓글 프롬프트</h2>
                </div>

                <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1rem", lineHeight: 1.7 }}>
                    AI 가 댓글을 쓸 때 쓰는 지시문입니다. 말투·길이·금지어 등을 직접 정할 수 있습니다.
                </p>

                <div style={{ padding: "0.9rem 1rem", marginBottom: "1rem", borderRadius: "8px", background: "#f8fafc", border: "1px solid #e2e8f0", fontSize: "0.85rem", color: "#475569", lineHeight: 1.9 }}>
                    <b>아래 자리표시자는 실행할 때 자동으로 채워집니다</b><br />
                    {Object.entries(cmtPlaceholders).map(([k, v]) => (
                        <span key={k}><code style={{ background: "#e2e8f0", padding: "0.1rem 0.35rem", borderRadius: "4px" }}>{k}</code> {v}<br /></span>
                    ))}
                </div>

                {cmtMessage && (
                    <div style={{
                        padding: "0.9rem 1rem", marginBottom: "1rem", borderRadius: "8px",
                        background: cmtMessage.type === "success" ? "#f0fdf4" : "#fef2f2",
                        color: cmtMessage.type === "success" ? "#166534" : "#991b1b",
                        border: `1px solid ${cmtMessage.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                        display: "flex", alignItems: "center", gap: "0.5rem"
                    }}>
                        <AlertCircle size={18} />{cmtMessage.text}
                    </div>
                )}

                <textarea value={cmtPrompt} onChange={e => setCmtPrompt(e.target.value)} rows={8}
                    style={{ width: "100%", padding: "0.9rem", border: "1px solid #cbd5e1", borderRadius: "8px", boxSizing: "border-box", fontSize: "0.9rem", lineHeight: 1.7, fontFamily: "inherit", resize: "vertical" }} />

                <div style={{ display: "flex", gap: "0.7rem", marginTop: "1rem", flexWrap: "wrap" }}>
                    <button onClick={() => saveCmtPrompt(false)} disabled={cmtLoading}
                        style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.8rem 1.6rem", background: cmtLoading ? "#94a3b8" : "#e11d48", color: "white", border: "none", borderRadius: "8px", fontWeight: 600, cursor: cmtLoading ? "wait" : "pointer" }}>
                        <Save size={18} />{cmtLoading ? "저장 중..." : "프롬프트 저장"}
                    </button>
                    <button onClick={() => saveCmtPrompt(true)} disabled={cmtLoading}
                        style={{ padding: "0.8rem 1.4rem", background: "white", color: "#64748b", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: 600, cursor: "pointer" }}>
                        기본값으로 되돌리기
                    </button>
                </div>
            </div>

            {/* 카페 원고 프롬프트 — 정보성 / 맛집 */}
            <div style={{
                background: "white", borderRadius: "16px", padding: "2rem",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)"
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid #e2e8f0" }}>
                    <Key size={24} color="#7c3aed" />
                    <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#334155", margin: 0 }}>카페 원고 프롬프트</h2>
                </div>

                <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1rem", lineHeight: 1.7 }}>
                    {postHelp || "여기 적은 내용이 기본 규칙 뒤에 '추가 지시'로 붙습니다."}
                    {" "}비워두면 기본 규칙만 사용합니다.
                </p>

                {postMessage && (
                    <div style={{
                        padding: "0.9rem 1rem", marginBottom: "1rem", borderRadius: "8px",
                        background: postMessage.type === "success" ? "#f0fdf4" : "#fef2f2",
                        color: postMessage.type === "success" ? "#166534" : "#991b1b",
                        border: `1px solid ${postMessage.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                        display: "flex", alignItems: "center", gap: "0.5rem"
                    }}>
                        <AlertCircle size={18} />{postMessage.text}
                    </div>
                )}

                {Object.entries(postPrompts).map(([key, item]) => (
                    <div key={key} style={{ marginBottom: "1.5rem" }}>
                        <label style={{ display: "block", fontWeight: 600, color: "#475569", marginBottom: "0.5rem", fontSize: "0.95rem" }}>
                            {item.label}
                        </label>
                        <textarea value={item.prompt || ""} rows={5}
                            placeholder="예) 존댓말로 쓰고, 문단마다 소제목을 달아주세요. '최고', '무조건' 같은 단정 표현은 쓰지 마세요."
                            onChange={e => setPostPrompts(p => ({ ...p, [key]: { ...p[key], prompt: e.target.value } }))}
                            style={{ width: "100%", padding: "0.9rem", border: "1px solid #cbd5e1", borderRadius: "8px", boxSizing: "border-box", fontSize: "0.9rem", lineHeight: 1.7, fontFamily: "inherit", resize: "vertical" }} />
                        <button onClick={() => savePostPrompt(key)} disabled={postSaving === key}
                            style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.7rem", padding: "0.7rem 1.4rem", background: postSaving === key ? "#94a3b8" : "#7c3aed", color: "white", border: "none", borderRadius: "8px", fontWeight: 600, cursor: postSaving === key ? "wait" : "pointer" }}>
                            <Save size={18} />{postSaving === key ? "저장 중..." : "저장"}
                        </button>
                    </div>
                ))}
            </div>
            </>)}

            {/* 계정 동기화 — 여러 PC 에서 같은 네이버 계정 목록 쓰기 */}
            <div style={{
                background: "white", borderRadius: "16px", padding: "2rem",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)"
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid #e2e8f0" }}>
                    <Key size={24} color="#0ea5e9" />
                    <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#334155", margin: 0 }}>계정 동기화 (다른 PC 와 공유)</h2>
                </div>

                <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1.2rem", lineHeight: 1.7 }}>
                    등록한 <b>네이버 계정 목록과 카페 매핑</b>을 다른 PC 로 옮깁니다.<br />
                    A 컴퓨터에서 <b>[서버에 올리기]</b> → B 컴퓨터에서 <b>[서버에서 가져오기]</b> 하면 됩니다.
                </p>

                <div style={{ padding: "0.9rem 1rem", marginBottom: "1.2rem", borderRadius: "8px", background: "#fffbeb", border: "1px solid #fde68a", color: "#92400e", fontSize: "0.88rem", lineHeight: 1.7 }}>
                    🔒 계정 정보는 <b>이 PC 에서 암호화한 뒤</b> 올라가므로 서버는 내용을 볼 수 없습니다.<br />
                    그래서 <b>비밀번호를 잊으면 서버에 있는 백업도 풀 수 없습니다.</b> 꼭 기억해 주세요.<br />
                    <span style={{ color: "#b45309" }}>※ 네이버 로그인(기기인증)은 PC 마다 따로 해야 합니다 — 이건 옮겨지지 않습니다.</span>
                </div>

                {syncMessage && (
                    <div style={{
                        padding: "0.9rem 1rem", marginBottom: "1.2rem", borderRadius: "8px",
                        background: syncMessage.type === "success" ? "#f0fdf4" : "#fef2f2",
                        color: syncMessage.type === "success" ? "#166534" : "#991b1b",
                        border: `1px solid ${syncMessage.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                        display: "flex", alignItems: "center", gap: "0.5rem"
                    }}>
                        <AlertCircle size={18} />{syncMessage.text}
                    </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: 600, color: "#475569", marginBottom: "0.5rem" }}>이메일</label>
                        <input type="email" value={syncForm.email} autoComplete="off"
                            onChange={e => setSyncForm({ ...syncForm, email: e.target.value })}
                            placeholder="가입하신 이메일"
                            style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.95rem", outline: "none", boxSizing: "border-box" }} />
                    </div>
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: 600, color: "#475569", marginBottom: "0.5rem" }}>비밀번호</label>
                        <input type="password" value={syncForm.password} autoComplete="off"
                            onChange={e => setSyncForm({ ...syncForm, password: e.target.value })}
                            placeholder="계정 비밀번호 (암호화 열쇠로도 쓰입니다)"
                            style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.95rem", outline: "none", boxSizing: "border-box" }} />
                    </div>
                    <div style={{ display: "flex", gap: "0.7rem", flexWrap: "wrap" }}>
                        <button onClick={() => runSync("upload")} disabled={!!syncLoading}
                            style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.8rem 1.4rem", background: syncLoading === "upload" ? "#94a3b8" : "#0ea5e9", color: "white", border: "none", borderRadius: "8px", fontWeight: 600, cursor: syncLoading ? "wait" : "pointer" }}>
                            <Save size={18} />{syncLoading === "upload" ? "올리는 중..." : "⬆ 서버에 올리기"}
                        </button>
                        <button onClick={() => runSync("download")} disabled={!!syncLoading}
                            style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.8rem 1.4rem", background: "white", color: "#0f172a", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: 600, cursor: syncLoading ? "wait" : "pointer" }}>
                            {syncLoading === "download" ? "가져오는 중..." : "⬇ 서버에서 가져오기"}
                        </button>
                    </div>
                </div>
            </div>

            {/* AI API 키 (BYOK) — 원고·댓글 생성에 필요 */}
            <div style={{
                background: "white", borderRadius: "16px", padding: "2rem",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)"
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid #e2e8f0" }}>
                    <Key size={24} color="#16a34a" />
                    <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#334155", margin: 0 }}>AI API 키</h2>
                </div>

                <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1.5rem", lineHeight: 1.7 }}>
                    원고 생성과 <b>AI 댓글 생성</b>에 쓰입니다. 하나 이상 넣어야 동작하며, 요금은 본인 계정으로 청구됩니다.<br />
                    <b>Claude</b> 키는 <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer" style={{ color: "#2563eb" }}>console.anthropic.com</a> 에서 발급합니다 (형식: <code>sk-ant-…</code>).
                </p>

                {aiMessage && (
                    <div style={{
                        padding: "0.9rem 1rem", marginBottom: "1.2rem", borderRadius: "8px",
                        background: aiMessage.type === "success" ? "#f0fdf4" : "#fef2f2",
                        color: aiMessage.type === "success" ? "#166534" : "#991b1b",
                        border: `1px solid ${aiMessage.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                        display: "flex", alignItems: "center", gap: "0.5rem"
                    }}>
                        <AlertCircle size={18} />{aiMessage.text}
                    </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
                    {[
                        { k: "claude_key", id: "claude", name: "Claude (권장)", ph: "sk-ant-..." },
                        { k: "gemini_key", id: "gemini", name: "Gemini", ph: "AIza..." },
                        { k: "openai_key", id: "openai", name: "OpenAI", ph: "sk-..." },
                    ].map(({ k, id, name, ph }) => (
                        <div key={k}>
                            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem", fontWeight: 600, color: "#475569", marginBottom: "0.5rem" }}>
                                {name}
                                {aiHas[id]
                                    ? <span style={{ fontSize: "0.78rem", fontWeight: 500, color: "#16a34a" }}>● 등록됨 ({aiSaved[id]})</span>
                                    : <span style={{ fontSize: "0.78rem", fontWeight: 500, color: "#94a3b8" }}>○ 미등록</span>}
                            </label>
                            <input
                                type="password"
                                value={aiKeys[k]}
                                onChange={e => setAiKeys({ ...aiKeys, [k]: e.target.value })}
                                placeholder={aiHas[id] ? "새 키를 넣을 때만 입력 (지우려면 - )" : ph}
                                autoComplete="off"
                                style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.95rem", outline: "none", boxSizing: "border-box", fontFamily: "monospace" }}
                            />
                        </div>
                    ))}
                    <button onClick={handleSaveAiKeys} disabled={aiLoading}
                        style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.8rem 1.6rem", background: aiLoading ? "#94a3b8" : "#16a34a", color: "white", border: "none", borderRadius: "8px", fontWeight: 600, cursor: aiLoading ? "wait" : "pointer" }}>
                        <Save size={18} />{aiLoading ? "저장 중..." : "AI 키 저장"}
                    </button>
                </div>
            </div>

            {/* 비밀번호 변경 */}
            <div style={{
                background: "white",
                borderRadius: "16px",
                padding: "2rem",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)"
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid #e2e8f0" }}>
                    <Key size={24} color="#7c3aed" />
                    <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#334155", margin: 0 }}>비밀번호 변경</h2>
                </div>

                {pwMessage && (
                    <div style={{
                        padding: "0.9rem 1rem",
                        marginBottom: "1.2rem",
                        borderRadius: "8px",
                        background: pwMessage.type === "success" ? "#f0fdf4" : "#fef2f2",
                        color: pwMessage.type === "success" ? "#166534" : "#991b1b",
                        border: `1px solid ${pwMessage.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem"
                    }}>
                        <AlertCircle size={18} />
                        {pwMessage.text}
                    </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>
                            현재 비밀번호
                        </label>
                        <input
                            type="password"
                            value={pwForm.current}
                            onChange={e => setPwForm({ ...pwForm, current: e.target.value })}
                            autoComplete="current-password"
                            style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "1rem", outline: "none" }}
                        />
                    </div>
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>
                            새 비밀번호 (8자 이상)
                        </label>
                        <input
                            type="password"
                            value={pwForm.next}
                            onChange={e => setPwForm({ ...pwForm, next: e.target.value })}
                            autoComplete="new-password"
                            style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "1rem", outline: "none" }}
                        />
                    </div>
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>
                            새 비밀번호 확인
                        </label>
                        <input
                            type="password"
                            value={pwForm.confirm}
                            onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })}
                            autoComplete="new-password"
                            style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "1rem", outline: "none" }}
                        />
                    </div>
                    <div>
                        <button
                            onClick={handleChangePassword}
                            disabled={pwLoading}
                            style={{
                                background: pwLoading ? "#94a3b8" : "#7c3aed",
                                color: "white", border: "none",
                                padding: "0.7rem 1.6rem", borderRadius: "8px",
                                fontSize: "0.95rem", fontWeight: "600",
                                cursor: pwLoading ? "not-allowed" : "pointer"
                            }}
                        >
                            {pwLoading ? "변경 중..." : "비밀번호 변경"}
                        </button>
                    </div>
                </div>
            </div>
            </div>

        </div>
    );
}

function Settings() {
    return <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
}
