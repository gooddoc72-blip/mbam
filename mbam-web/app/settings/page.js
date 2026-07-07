"use client";
import { fetchWithAuth } from "../utils/api";
import { useState, useEffect } from "react";
import { Save, Key, AlertCircle } from "lucide-react";

export default function SettingsPage() {
    const [telegramKeys, setTelegramKeys] = useState({
        bot_token: "",
        chat_id: ""
    });

    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null);

    // 비밀번호 변경
    const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
    const [pwLoading, setPwLoading] = useState(false);
    const [pwMessage, setPwMessage] = useState(null);

    useEffect(() => {
        fetchKeys();
    }, []);

    const fetchKeys = async () => {
        try {
            // Fetch Telegram Keys
            const resTg = await fetchWithAuth("/api/settings/telegram-api");
            if (resTg.ok) {
                const dataTg = await resTg.json();
                setTelegramKeys({
                    bot_token: dataTg.bot_token || "",
                    chat_id: dataTg.chat_id || ""
                });
            }
        } catch (error) {
            console.error("Failed to fetch keys:", error);
        }
    };

    const handleSave = async () => {
        setLoading(true);
        setMessage(null);
        try {
            // Save Telegram Keys
            const res3 = await fetchWithAuth("/api/settings/telegram-api", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(telegramKeys)
            });
            
            if (res3.ok) {
                setMessage({ type: "success", text: "텔레그램 설정이 성공적으로 저장되었습니다." });
            } else {
                setMessage({ type: "error", text: `저장에 실패했습니다. Telegram: ${res3.status}` });
            }
        } catch (error) {
            setMessage({ type: "error", text: `서버와 연결할 수 없습니다: ${error.message}` });
        }
        setLoading(false);
    };

    const handleTelegramChange = (e) => {
        setTelegramKeys({ ...telegramKeys, [e.target.name]: e.target.value });
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
        <div style={{ padding: "1rem", maxWidth: "800px", margin: "0 auto" }}>
            <h1 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#1e293b", marginBottom: "2rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Settings /> 환경 설정
            </h1>

            {message && (
                <div style={{ 
                    padding: "1rem", 
                    marginBottom: "1.5rem", 
                    borderRadius: "8px", 
                    background: message.type === "success" ? "#f0fdf4" : "#fef2f2",
                    color: message.type === "success" ? "#166534" : "#991b1b",
                    border: `1px solid ${message.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem"
                }}>
                    <AlertCircle size={18} />
                    {message.text}
                </div>
            )}

            {/* Telegram API Settings */}
            <div style={{
                background: "white", 
                borderRadius: "16px", 
                padding: "2rem", 
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)",
                marginBottom: "2rem"
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid #e2e8f0" }}>
                    <Key size={24} color="#0284c7" />
                    <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#334155", margin: 0 }}>텔레그램 봇(원격 제어) 연동</h2>
                </div>
                
                <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "2rem", lineHeight: "1.6" }}>
                    스케줄러를 통한 수집 글감 알림 및 모바일에서의 자동 포스팅 승인을 위해 텔레그램 봇을 연동합니다.<br/>
                    BotFather를 통해 발급받은 Bot Token과 메시지를 수신할 Chat ID를 입력해주세요.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>
                            Bot Token (봇 토큰)
                        </label>
                        <input 
                            type="password" 
                            name="bot_token"
                            value={telegramKeys.bot_token}
                            onChange={handleTelegramChange}
                            placeholder="예: 1234567890:AAH_xyz..."
                            style={{ 
                                width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", 
                                border: "1px solid #cbd5e1", fontSize: "1rem", transition: "all 0.2s",
                                outline: "none", boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
                            }}
                        />
                    </div>
                    
                    <div>
                        <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>
                            Chat ID (채팅방 ID)
                        </label>
                        <input 
                            type="text" 
                            name="chat_id"
                            value={telegramKeys.chat_id}
                            onChange={handleTelegramChange}
                            placeholder="예: 123456789"
                            style={{ 
                                width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", 
                                border: "1px solid #cbd5e1", fontSize: "1rem", transition: "all 0.2s",
                                outline: "none", boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
                            }}
                        />
                    </div>
                </div>
            </div>

            {/* 비밀번호 변경 */}
            <div style={{
                background: "white",
                borderRadius: "16px",
                padding: "2rem",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
                border: "1px solid rgba(226, 232, 240, 0.8)",
                marginBottom: "2rem"
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

                <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem", maxWidth: "420px" }}>
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

            <div style={{ marginTop: "2rem", display: "flex", justifyContent: "flex-end" }}>
                <button
                    onClick={handleSave}
                    disabled={loading}
                    style={{
                        background: loading ? "#94a3b8" : "#3b82f6",
                        color: "white",
                        border: "none",
                        padding: "0.8rem 2rem",
                        borderRadius: "8px",
                        fontSize: "1rem",
                        fontWeight: "600",
                        cursor: loading ? "not-allowed" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        boxShadow: "0 4px 6px -1px rgba(59, 130, 246, 0.3)",
                        transition: "all 0.2s"
                    }}
                >
                    <Save size={18} />
                    {loading ? "저장 중..." : "설정 저장하기"}
                </button>
            </div>
        </div>
    );
}

function Settings() {
    return <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
}
