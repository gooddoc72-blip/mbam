"use client";
import React, { useState, useEffect } from "react";
import { fetchWithAuth, resolveMaybeAgent } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";
import { PenTool, Video, Calendar, Clock, Image as ImageIcon, Search, CheckCircle2 } from "lucide-react";

export default function PlaceNewsPage() {
    const [mid, setMid] = useState("");
    const [placeUrl, setPlaceUrl] = useState("");
    const [placeName, setPlaceName] = useState("");
    const [intervalWeeks, setIntervalWeeks] = useState(1);
    
    // Step 2 State — 수집/생성 진행 상태는 전역 보관: 메뉴 이동해도 작업이 계속되고 복귀 시 유지
    const [fetchedReviews, setFetchedReviews] = usePersistentState("place-news:fetchedReviews", []);
    const [fetchedImages, setFetchedImages] = usePersistentState("place-news:fetchedImages", []);
    const [selectedTheme, setSelectedTheme] = usePersistentState("place-news:selectedTheme", "🌟 고객 극찬 릴레이 (방문 후기형)");
    const [step, setStep] = usePersistentState("place-news:step", 1); // 1: 설정/수집, 2: 테마선택/생성

    const [schedules, setSchedules] = useState([]);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = usePersistentState("place-news:loading", false);

    // 발행 계정 (플레이스 소유주) — 계정관리(전체 풀)와 동일 저장소 사용
    const [ownerAccounts, setOwnerAccounts] = useState([]);
    const [ownerSelected, setOwnerSelected] = usePersistentState("place-news:ownerSelected", "");
    const [registeredIds, setRegisteredIds] = useState([]);
    const [newOwnerId, setNewOwnerId] = useState("");
    const [newOwnerPw, setNewOwnerPw] = useState("");
    const [publishing, setPublishing] = useState(false);

    const loadOwnerAccounts = async () => {
        try {
            const [accRes, regRes] = await Promise.all([
                fetchWithAuth("/api/cafe-nurture/accounts"),
                fetchWithAuth("/api/auto_post/registered-accounts"),
            ]);
            if (accRes.ok) setOwnerAccounts(await accRes.json() || []);
            if (regRes.ok) { const d = await regRes.json(); setRegisteredIds(d.registered || []); }
        } catch (e) {}
    };

    const handleAddOwnerAccount = async () => {
        if (!newOwnerId || !newOwnerPw) return alert("아이디와 비밀번호를 입력하세요.");
        try {
            const res = await fetchWithAuth("/api/cafe-nurture/accounts", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ naver_id: newOwnerId, naver_pw: newOwnerPw }),
            });
            if (res.ok) { alert("계정이 등록되었습니다. (계정관리에도 반영) 이어서 '기기 인증'을 완료하세요."); setNewOwnerId(""); setNewOwnerPw(""); loadOwnerAccounts(); }
            else { const d = await res.json().catch(() => ({})); alert("등록 실패: " + (d.detail || res.status)); }
        } catch (e) { alert("서버 오류: " + e.message); }
    };

    const handleRegisterOwner = async (naverId) => {
        if (!window.confirm(`'${naverId}' 기기 인증을 시작합니다.\n내 PC에서 브라우저가 열리면 로그인 + 2단계 인증을 완료해 주세요.`)) return;
        try {
            const res = await fetchWithAuth("/api/auto_post/register-account", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ naver_id: naverId, naver_pw: null }),
            });
            let data = await res.json();
            if (data.mode === "agent" && data.job_id) {
                alert("내 PC에서 브라우저가 열립니다. 로그인 완료까지 기다려 주세요...");
                data = await resolveMaybeAgent(data, { tries: 120, intervalMs: 3000 });
            }
            if (data.success) { alert("✅ 기기 인증 완료!"); loadOwnerAccounts(); }
            else alert(data.error || data.message || "인증 결과를 확인하세요.");
        } catch (e) { alert("인증 실패/시간초과: " + e.message); loadOwnerAccounts(); }
    };

    // 소식 원고(고객 리뷰 기반)를 블로그 원고로 확장 생성 → 소유주 블로그에 바로 발행
    const handlePublishBlog = async (h) => {
        if (!ownerSelected) return alert("좌측에서 발행 계정을 먼저 선택(등록·인증)하세요.");
        if (!window.confirm(`'${ownerSelected}' 블로그에 이 소식을 발행할까요?\n(고객 리뷰 기반으로 블로그용 원고를 새로 생성해 발행합니다)`)) return;
        setPublishing(true);
        try {
            const kw = (h.place_name && h.place_name !== "수동생성") ? h.place_name : "가게 소식";
            const source = `[고객 리뷰 기반 소식 원고 — 아래 후기·내용을 인용하며 방문을 유도하는 블로그 글로 확장 작성]\n${h.generated_text}`;
            const payload = {
                target_type: "blog", login_mode: "auto",
                accounts: [{ id: ownerSelected, pw: "", checked: true }],
                naver_id: ownerSelected, naver_pw: null,
                post_mode: "ai_generate", target_keyword: kw,
                source_data: source, post_purpose: "review", promo_type: "place",
                distribution_mode: "normal", publish_mode: "instant",
                generate_card_news: true, cafe_action_type: "post",
            };
            const res = await fetchWithAuth("/api/auto_post/", {
                method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
            });
            let data = await res.json();
            data = await resolveMaybeAgent(data, { tries: 150, intervalMs: 4000 });
            if (data.success !== false) alert("✅ 블로그 발행 작업이 완료되었습니다. 블로그에서 확인해 보세요.");
            else alert("발행 실패: " + (data.error || "오류"));
        } catch (e) { alert("발행 실패/시간초과: " + e.message); }
        finally { setPublishing(false); }
    };

    // 스마트플레이스 '새소식'으로 발행 (에이전트 자동화)
    const handlePublishPlace = async (h) => {
        if (!ownerSelected) return alert("좌측에서 발행 계정을 먼저 선택(등록·인증)하세요.");
        if (!window.confirm(`'${ownerSelected}' 계정으로 스마트플레이스 새소식에 발행할까요?\n(내 PC에서 브라우저가 열려 자동 등록됩니다)`)) return;
        setPublishing(true);
        try {
            const res = await fetchWithAuth("/api/place/news/publish", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ history_id: h.id, naver_id: ownerSelected }),
            });
            let data = await res.json();
            data = await resolveMaybeAgent(data, { tries: 150, intervalMs: 4000 });
            if (data.success) { alert("✅ 스마트플레이스 새소식 발행 완료!"); fetchData(); }
            else alert("발행 실패: " + (data.error || data.detail || "자동화 단계에서 막히면 열린 브라우저에서 직접 마무리해 주세요."));
        } catch (e) { alert("발행 실패/시간초과: " + e.message); }
        finally { setPublishing(false); }
    };

    useEffect(() => {
        fetchData();
        loadOwnerAccounts();
    }, []);
    
    const fetchData = async () => {
        try {
            const schRes = await fetchWithAuth("/api/place/news/schedule");
            const schData = await schRes.json();
            if (schData.success) {
                setSchedules(schData.schedules);
            }
            
            const histRes = await fetchWithAuth("/api/place/news/history");
            const histData = await histRes.json();
            if (histData.success) {
                setHistory(histData.history);
            }
        } catch (e) {
            console.error("데이터 로드 실패", e);
        }
    };
    
    const handleFetchMid = async () => {
        if (!mid) {
            alert("플레이스 MID 번호를 입력해주세요.");
            return;
        }
        try {
            setLoading(true);
            const res = await fetchWithAuth("/api/place/fetch-mid", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mid: mid })
            });
            let data = await res.json();
            data = await resolveMaybeAgent(data, { tries: 40, intervalMs: 2000 });
            if (data.success && data.name) {
                setPlaceName(data.name);
                setPlaceUrl(`https://m.place.naver.com/place/${mid}/home`);
                alert(`[${data.name}] 기본 정보가 연동되었습니다.`);
            } else {
                alert("정보를 불러오는데 실패했습니다: " + (data.detail || data.error || "알 수 없는 오류"));
            }
        } catch (e) {
            alert("서버 연결 실패");
        } finally {
            setLoading(false);
        }
    };

    const handleSaveSchedule = async () => {
        if (!placeUrl || !placeName) {
            alert("가게명과 URL을 입력해주세요.");
            return;
        }
        
        try {
            setLoading(true);
            const res = await fetchWithAuth("/api/place/news/schedule", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    place_url: placeUrl,
                    place_name: placeName,
                    interval_weeks: intervalWeeks
                })
            });
            const data = await res.json();
            if (data.success) {
                alert("스케줄이 저장되었습니다!");
                fetchData();
            }
        } catch (e) {
            alert("저장 실패");
        } finally {
            setLoading(false);
        }
    };
    
    const handleFetchReviews = async () => {
        if (!placeUrl || !placeName) {
            alert("가게명과 URL을 입력해주세요.");
            return;
        }
        
        try {
            setLoading(true);
            const res = await fetchWithAuth("/api/place/news/fetch-reviews", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ place_url: placeUrl })
            });
            let data = await res.json();
            data = await resolveMaybeAgent(data, { tries: 90, intervalMs: 3000 });
            if (data.success) {
                setFetchedReviews(data.reviews);
                setFetchedImages(data.image_paths);
                setStep(2);
            } else {
                alert("리뷰 수집 실패: " + (data.error || "알 수 없는 오류"));
            }
        } catch (e) {
            alert("리뷰 수집 중 오류 발생");
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateWithTheme = async () => {
        try {
            setLoading(true);
            alert("선택하신 테마로 원고 및 영상 제작을 시작합니다. 약 1분 정도 소요됩니다.");
            const res = await fetchWithAuth("/api/place/news/generate-with-theme", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    place_name: placeName,
                    reviews: fetchedReviews,
                    image_paths: fetchedImages,
                    theme: selectedTheme
                })
            });
            const data = await res.json();
            if (data.success) {
                alert("원고 및 영상이 성공적으로 제작되었습니다!");
                try { addHistory("place-news", { summary: `소식·영상 제작 완료` }); } catch (e) {}
                setStep(1); // 초기화
                fetchData();
            } else {
                alert("생성 실패: " + (data.detail || data.error || "알 수 없는 오류"));
            }
        } catch (e) {
            alert("생성 중 오류 발생: " + e.message);
        } finally {
            setLoading(false);
        }
    };

    const THEMES = [
        { id: "🌟 고객 극찬 릴레이 (방문 후기형)", desc: "고객들의 찐 반응과 칭찬(맛, 친절도 등)을 집중적으로 어필하는 감동 후기 원고" },
        { id: "👩‍🍳 우리 매장의 차별점 (전문성 어필형)", desc: "리뷰에서 찾아낸 우리 매장만의 독보적인 메뉴, 시설 등 차별 포인트를 강조하는 원고" },
        { id: "🎉 이번 주 베스트 포토 (시각적 어필형)", desc: "예쁜 리뷰 사진들을 메인으로 삼아 시각적인 매력과 분위기를 짧고 강렬하게 홍보" }
    ];

    return (
        <main style={{ maxWidth: "1400px", margin: "0 auto", padding: "2rem" }}>
            <header style={{ marginBottom: "2rem" }}>
                <h1 style={{ fontSize: "2.5rem", fontWeight: "bold", background: "linear-gradient(90deg, #ec4899, #8b5cf6)", WebkitBackgroundClip: "text", color: "transparent", marginBottom: "0.5rem" }}>
                    ✨ 플레이스 소식 & 영상 자동화
                </h1>
                <p style={{ color: "#64748b", fontSize: "1.1rem" }}>
                    방문자 리뷰를 AI가 분석하여 가장 매력적인 '새소식 원고'와 '숏폼 홍보 클립'을 자동 제작합니다.
                </p>
            </header>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "2rem" }}>
                
                {/* Left Panel: Settings or Theme Selection */}
                <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                    
                    {step === 1 ? (
                        <div style={{ background: "white", padding: "2rem", borderRadius: "16px", border: "1px solid #e2e8f0", boxShadow: "0 10px 25px rgba(0,0,0,0.05)" }}>
                            <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", color: "#1e293b", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <PenTool size={20} color="#8b5cf6" />
                                자동화 대상 설정
                            </h2>
                            
                            <div style={{ marginBottom: "1.25rem", display: "flex", gap: "0.5rem", alignItems: "flex-end" }}>
                                <div style={{ flex: 1 }}>
                                    <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>플레이스 MID (고유번호)</label>
                                    <input 
                                        type="text" 
                                        placeholder="예: 12345678"
                                        value={mid}
                                        onChange={(e) => setMid(e.target.value)}
                                        style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none", fontSize: "1rem" }}
                                    />
                                </div>
                                <button 
                                    onClick={handleFetchMid}
                                    disabled={loading}
                                    style={{ 
                                        padding: "0.75rem 1rem", borderRadius: "8px", border: "none", 
                                        background: "#3b82f6", color: "white", fontWeight: "bold", fontSize: "0.95rem",
                                        cursor: loading ? "not-allowed" : "pointer", height: "46px", transition: "background 0.2s"
                                    }}
                                    onMouseOver={(e) => e.currentTarget.style.background = "#2563eb"}
                                    onMouseOut={(e) => e.currentTarget.style.background = "#3b82f6"}
                                >
                                    자동 입력
                                </button>
                            </div>
                            
                            <div style={{ marginBottom: "1.25rem" }}>
                                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>가게 상호명</label>
                                <input 
                                    type="text" 
                                    placeholder="예: 맛집식당 강남점"
                                    value={placeName}
                                    onChange={(e) => setPlaceName(e.target.value)}
                                    style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none", fontSize: "1rem", background: "#f8fafc" }}
                                />
                            </div>
                            
                            <div style={{ marginBottom: "1.25rem" }}>
                                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>플레이스 URL</label>
                                <input 
                                    type="text" 
                                    placeholder="예: https://m.place.naver.com/restaurant/12345/home"
                                    value={placeUrl}
                                    onChange={(e) => setPlaceUrl(e.target.value)}
                                    style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none", fontSize: "1rem", background: "#f8fafc" }}
                                />
                            </div>
                            
                            <div style={{ marginBottom: "2rem" }}>
                                <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>리뷰 수집 및 생성 주기</label>
                                <div style={{ position: "relative" }}>
                                    <select 
                                        value={intervalWeeks}
                                        onChange={(e) => setIntervalWeeks(Number(e.target.value))}
                                        style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none", fontSize: "1rem", appearance: "none", background: "#f8fafc" }}
                                    >
                                        <option value={1}>1주 마다 최신 리뷰 분석 및 생성</option>
                                        <option value={2}>2주 마다 최신 리뷰 분석 및 생성</option>
                                    </select>
                                    <Calendar size={18} color="#64748b" style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} />
                                </div>
                            </div>
                            
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                <button 
                                    onClick={handleFetchReviews}
                                    disabled={loading}
                                    style={{ 
                                        padding: "1rem", borderRadius: "8px", border: "none", 
                                        background: "linear-gradient(90deg, #3b82f6, #0ea5e9)", color: "white", 
                                        fontWeight: "bold", fontSize: "1rem", cursor: loading ? "not-allowed" : "pointer",
                                        boxShadow: "0 4px 6px -1px rgba(59, 130, 246, 0.3)"
                                    }}
                                >
                                    {loading ? "리뷰 수집 중..." : "🔍 리뷰 분석하고 테마 고르기"}
                                </button>
                                <button 
                                    onClick={handleSaveSchedule}
                                    disabled={loading}
                                    style={{ 
                                        padding: "1rem", borderRadius: "8px", border: "1px solid #cbd5e1", 
                                        background: "white", color: "#475569", 
                                        fontWeight: "bold", fontSize: "1rem", cursor: loading ? "not-allowed" : "pointer",
                                        transition: "background 0.2s"
                                    }}
                                    onMouseOver={(e) => e.currentTarget.style.background = "#f1f5f9"}
                                    onMouseOut={(e) => e.currentTarget.style.background = "white"}
                                >
                                    스케줄 저장 (자동화 켜기)
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div style={{ background: "white", padding: "2rem", borderRadius: "16px", border: "1px solid #e2e8f0", boxShadow: "0 10px 25px rgba(0,0,0,0.05)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                                <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", color: "#1e293b", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                    <Search size={20} color="#ec4899" />
                                    글감 테마 선택
                                </h2>
                                <button 
                                    onClick={() => setStep(1)} 
                                    style={{ background: "none", border: "none", color: "#64748b", textDecoration: "underline", cursor: "pointer", fontSize: "0.9rem" }}
                                >
                                    다시 설정하기
                                </button>
                            </div>
                            
                            <p style={{ fontSize: "0.95rem", color: "#475569", marginBottom: "1.5rem", lineHeight: "1.5" }}>
                                <strong>최근 1주일치 {fetchedReviews.length}개의 리뷰</strong>와 <strong>{fetchedImages.length}장의 사진</strong>이 성공적으로 수집되었습니다.<br/>원하시는 마케팅 테마를 골라주세요!
                            </p>
                            
                            <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "2rem" }}>
                                {THEMES.map(theme => (
                                    <label key={theme.id} style={{ 
                                        display: "flex", alignItems: "flex-start", gap: "1rem", padding: "1.25rem", 
                                        borderRadius: "12px", border: `2px solid ${selectedTheme === theme.id ? '#8b5cf6' : '#e2e8f0'}`,
                                        background: selectedTheme === theme.id ? '#f5f3ff' : 'white',
                                        cursor: "pointer", transition: "all 0.2s"
                                    }}>
                                        <input 
                                            type="radio" 
                                            name="theme" 
                                            value={theme.id} 
                                            checked={selectedTheme === theme.id}
                                            onChange={(e) => setSelectedTheme(e.target.value)}
                                            style={{ marginTop: "0.25rem", width: "1.2rem", height: "1.2rem", accentColor: "#8b5cf6" }}
                                        />
                                        <div>
                                            <div style={{ fontWeight: "bold", color: "#1e293b", marginBottom: "0.25rem", fontSize: "1.05rem" }}>{theme.id}</div>
                                            <div style={{ fontSize: "0.85rem", color: "#64748b", lineHeight: "1.4" }}>{theme.desc}</div>
                                        </div>
                                    </label>
                                ))}
                            </div>
                            
                            <button 
                                onClick={handleGenerateWithTheme}
                                disabled={loading}
                                style={{ 
                                    width: "100%", padding: "1.1rem", borderRadius: "8px", border: "none", 
                                    background: "linear-gradient(90deg, #ec4899, #8b5cf6)", color: "white", 
                                    fontWeight: "bold", fontSize: "1.05rem", cursor: loading ? "not-allowed" : "pointer",
                                    boxShadow: "0 4px 6px -1px rgba(236, 72, 153, 0.3)"
                                }}
                            >
                                {loading ? "원고/영상 제작 중..." : "🚀 원고 및 영상 최종 생성"}
                            </button>
                        </div>
                    )}

                    {/* 발행 계정 (플레이스 소유주) — 계정관리 풀과 연동, 여기서 등록·기기인증·선택 */}
                    <div style={{ background: "rgba(255, 255, 255, 0.7)", backdropFilter: "blur(10px)", padding: "1.5rem", borderRadius: "16px", border: "1px solid rgba(255,255,255,0.5)" }}>
                        <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#1e293b", marginBottom: "0.4rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <CheckCircle2 size={18} color="#8b5cf6" />
                            발행 계정 (플레이스 소유주)
                        </h3>
                        <p style={{ margin: "0 0 0.8rem", fontSize: "0.8rem", color: "#64748b" }}>이 계정으로 블로그·스마트플레이스에 발행합니다. 등록하면 <b>계정관리</b>에도 함께 저장됩니다.</p>
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "0.8rem" }}>
                            {ownerAccounts.map(acc => {
                                const reg = registeredIds.includes(acc.naver_id);
                                const sel = ownerSelected === acc.naver_id;
                                return (
                                    <div key={acc.id} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                        <button onClick={() => setOwnerSelected(acc.naver_id)}
                                            style={{ flex: 1, textAlign: "left", padding: "0.55rem 0.9rem", borderRadius: "8px", border: sel ? "2px solid #8b5cf6" : "1px solid #cbd5e1", background: sel ? "#f5f3ff" : "white", color: sel ? "#6d28d9" : "#334155", fontWeight: "bold", cursor: "pointer", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                            {sel ? "✔ " : ""}{acc.naver_id}
                                        </button>
                                        <button onClick={() => handleRegisterOwner(acc.naver_id)}
                                            style={{ padding: "0.5rem 0.7rem", borderRadius: "8px", border: reg ? "1px solid #86efac" : "1px solid #fcd34d", background: reg ? "#dcfce7" : "#fef3c7", color: reg ? "#166534" : "#b45309", fontWeight: "bold", fontSize: "0.8rem", cursor: "pointer", whiteSpace: "nowrap" }}>
                                            {reg ? "✅ 인증완료" : "🔐 기기 인증"}
                                        </button>
                                    </div>
                                );
                            })}
                            {ownerAccounts.length === 0 && <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>등록된 계정이 없습니다. 아래에서 추가하세요.</span>}
                        </div>
                        <div style={{ display: "flex", gap: "0.4rem" }}>
                            <input type="text" placeholder="네이버 아이디" value={newOwnerId} onChange={e => setNewOwnerId(e.target.value)} style={{ flex: 1, minWidth: 0, padding: "0.55rem", border: "1px solid #cbd5e1", borderRadius: "8px" }} />
                            <input type="password" placeholder="비밀번호" value={newOwnerPw} onChange={e => setNewOwnerPw(e.target.value)} style={{ flex: 1, minWidth: 0, padding: "0.55rem", border: "1px solid #cbd5e1", borderRadius: "8px" }} />
                            <button onClick={handleAddOwnerAccount} style={{ padding: "0.55rem 0.9rem", background: "#8b5cf6", color: "white", border: "none", borderRadius: "8px", fontWeight: "bold", cursor: "pointer", whiteSpace: "nowrap" }}>추가</button>
                        </div>
                    </div>

                    <div style={{ background: "rgba(255, 255, 255, 0.7)", backdropFilter: "blur(10px)", padding: "1.5rem", borderRadius: "16px", border: "1px solid rgba(255,255,255,0.5)" }}>
                        <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#1e293b", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <Clock size={18} color="#10b981" />
                            현재 등록된 자동 스케줄
                        </h3>
                        {schedules.length === 0 ? (
                            <div style={{ textAlign: "center", color: "#94a3b8", padding: "2rem 0", fontSize: "0.9rem" }}>
                                등록된 스케줄이 없습니다.
                            </div>
                        ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                {schedules.map(s => (
                                    <div key={s.id} style={{ background: "white", padding: "1rem", borderRadius: "10px", border: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                        <div>
                                            <div style={{ fontWeight: "bold", color: "#0f172a" }}>{s.place_name}</div>
                                            <div style={{ fontSize: "0.75rem", color: "#64748b", maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.place_url}</div>
                                        </div>
                                        <div style={{ background: "#d1fae5", color: "#047857", padding: "0.25rem 0.75rem", borderRadius: "20px", fontSize: "0.8rem", fontWeight: "bold" }}>
                                            매 {s.interval_weeks}주
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Panel: History & Reviews preview */}
                <div style={{ background: "white", padding: "2rem", borderRadius: "16px", border: "1px solid #e2e8f0", boxShadow: "0 10px 25px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", height: "calc(100vh - 150px)" }}>
                    <h2 style={{ fontSize: "1.25rem", fontWeight: "bold", color: "#1e293b", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <ImageIcon size={20} color="#3b82f6" />
                        {step === 1 ? "생성된 원고 및 클립 리스트" : "수집된 데이터 미리보기"}
                    </h2>
                    
                    <div style={{ flex: 1, overflowY: "auto", paddingRight: "0.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                        
                        {step === 2 ? (
                            <>
                                <div style={{ background: "#f8fafc", padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
                                    <h3 style={{ fontSize: "1.05rem", fontWeight: "bold", marginBottom: "1rem", color: "#0f172a", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                        <CheckCircle2 size={18} color="#10b981" /> 최근 고객 리뷰 ({fetchedReviews.length}건)
                                    </h3>
                                    <ul style={{ listStyle: "disc", paddingLeft: "1.5rem", color: "#475569", fontSize: "0.9rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                        {fetchedReviews.slice(0, 10).map((rev, idx) => (
                                            <li key={idx} style={{ lineHeight: "1.4" }}>{rev}</li>
                                        ))}
                                        {fetchedReviews.length > 10 && <li style={{ color: "#94a3b8", listStyle: "none", marginLeft: "-1.5rem", marginTop: "0.5rem" }}>...외 {fetchedReviews.length - 10}건 추가 분석 됨</li>}
                                    </ul>
                                </div>
                                <div style={{ background: "#f8fafc", padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
                                    <h3 style={{ fontSize: "1.05rem", fontWeight: "bold", marginBottom: "1rem", color: "#0f172a", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                        <CheckCircle2 size={18} color="#10b981" /> 수집된 리뷰 사진 ({fetchedImages.length}장)
                                    </h3>
                                    <p style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "1rem" }}>*해당 사진들은 클립 영상(.mp4) 합성 재료로 자동 사용됩니다.</p>
                                    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.5rem" }}>
                                        {fetchedImages.map((img, idx) => {
                                            const filename = img.split('/').pop().split('\\').pop();
                                            const imgUrl = `/api/images/${filename}?t=${new Date().getTime()}`;
                                            return (
                                                <div key={idx} style={{ aspectRatio: "1/1", background: "#cbd5e1", borderRadius: "8px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem", color: "white", overflow: "hidden" }}>
                                                    <img src={imgUrl} alt={`수집된 사진 ${idx+1}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            </>
                        ) : history.length === 0 ? (
                            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#94a3b8" }}>
                                <ImageIcon size={48} style={{ opacity: 0.2, marginBottom: "1rem" }} />
                                <p>생성된 내역이 없습니다.</p>
                            </div>
                        ) : (
                            history.map(h => (
                                <div key={h.id} style={{ background: "#f8fafc", padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", transition: "transform 0.2s" }} onMouseOver={(e)=>e.currentTarget.style.transform="translateY(-2px)"} onMouseOut={(e)=>e.currentTarget.style.transform="translateY(0)"}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                                        <span style={{ fontWeight: "bold", color: "#1d4ed8", fontSize: "1.1rem" }}>{h.place_name}</span>
                                        <span style={{ fontSize: "0.8rem", color: "#64748b", background: "white", padding: "0.25rem 0.5rem", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                                            {new Date(h.created_at).toLocaleString('ko-KR')}
                                        </span>
                                    </div>
                                    <div style={{ background: "white", padding: "1rem", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "0.95rem", color: "#334155", lineHeight: "1.6", whiteSpace: "pre-wrap", maxHeight: "150px", overflowY: "auto", marginBottom: "1rem", boxShadow: "inset 0 2px 4px rgba(0,0,0,0.02)" }}>
                                        {h.generated_text}
                                    </div>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                                        <span style={{ fontSize: "0.8rem", color: "#64748b" }}>상태: {h.status === 'pending' ? '발행 대기중' : '발행 완료'}</span>
                                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                                            <button
                                                onClick={() => handlePublishBlog(h)}
                                                disabled={publishing}
                                                style={{
                                                    background: publishing ? "#94a3b8" : "#2563eb", color: "white", border: "none", padding: "0.5rem 1rem",
                                                    borderRadius: "6px", fontWeight: "bold", fontSize: "0.9rem", cursor: publishing ? "wait" : "pointer"
                                                }}
                                            >
                                                📝 블로그 발행
                                            </button>
                                            <button
                                                onClick={() => handlePublishPlace(h)}
                                                disabled={publishing}
                                                style={{
                                                    background: publishing ? "#94a3b8" : "#db2777", color: "white", border: "none", padding: "0.5rem 1rem",
                                                    borderRadius: "6px", fontWeight: "bold", fontSize: "0.9rem", cursor: publishing ? "wait" : "pointer"
                                                }}
                                            >
                                                📍 플레이스 발행
                                            </button>
                                            {h.clip_path && (
                                                <button
                                                    onClick={() => alert(`(프로토타입) 다음 경로에 MP4 영상이 저장되어 있습니다:\n\n${h.clip_path}`)}
                                                    style={{
                                                        background: "#10b981", color: "white", border: "none", padding: "0.5rem 1rem",
                                                        borderRadius: "6px", fontWeight: "bold", fontSize: "0.9rem", cursor: "pointer",
                                                        display: "flex", alignItems: "center", gap: "0.5rem", boxShadow: "0 2px 5px rgba(16,185,129,0.3)"
                                                    }}
                                                >
                                                    <Video size={16} />
                                                    클립 영상 확인하기
                                                </button>
                                            )}
                                            <button
                                                onClick={async () => {
                                                    if (!window.confirm("이 생성 이력을 삭제할까요? (클립 파일도 함께 삭제)")) return;
                                                    try {
                                                        const r = await fetchWithAuth(`/api/place/news/history/${h.id}`, { method: "DELETE" });
                                                        if (r.ok) setHistory(prev => prev.filter(x => x.id !== h.id));
                                                        else { const d = await r.json().catch(() => ({})); alert("삭제 실패: " + (d.detail || r.status)); }
                                                    } catch (e) { alert("서버 오류: " + e.message); }
                                                }}
                                                style={{
                                                    background: "white", color: "#ef4444", border: "1px solid #ef4444", padding: "0.5rem 0.9rem",
                                                    borderRadius: "6px", fontWeight: "bold", fontSize: "0.9rem", cursor: "pointer"
                                                }}
                                            >
                                                삭제
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
            <WorkHistory menuKey="place-news" />
        </main>
    );
}
