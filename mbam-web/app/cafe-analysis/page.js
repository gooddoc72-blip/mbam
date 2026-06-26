"use client";
import { fetchWithAuth } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";
import React, { useState } from 'react';
import { Search, ChevronRight, Activity, AlertCircle, FileText, CheckCircle2, ShieldAlert, Link2, Users, BarChart3 } from 'lucide-react';

const GRADE_COLORS = {
    S: { bg: '#fef3c7', fg: '#92400e' },
    A: { bg: '#d1fae5', fg: '#065f46' },
    B: { bg: '#dbeafe', fg: '#1e40af' },
    C: { bg: '#fed7aa', fg: '#9a3412' },
    D: { bg: '#e2e8f0', fg: '#475569' },
};

function GradeBadge({ grade, score, title }) {
    const c = GRADE_COLORS[grade] || GRADE_COLORS.D;
    return (
        <span
            title={title}
            style={{
                display: 'inline-flex', alignItems: 'baseline', gap: '4px',
                padding: '3px 10px', borderRadius: '14px',
                backgroundColor: c.bg, color: c.fg,
                fontSize: '0.75rem', fontWeight: 'bold', letterSpacing: '0.02em',
            }}
        >
            <span style={{ fontSize: '0.9rem' }}>{grade}</span>
            <span style={{ opacity: 0.8 }}>{Number(score || 0).toFixed(0)}</span>
        </span>
    );
}

function CafeAuthorityCards({ item }) {
    const cai = item.cafe_author_info;
    if (!cai || !cai.nickname) {
        return (
            <div style={{ padding: '1rem', color: '#94a3b8', fontSize: '0.9rem', textAlign: 'center', background: '#f8fafc', borderRadius: '8px' }}>
                카페 작성자 정보를 추출하지 못했습니다.
            </div>
        );
    }
    return (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
            {/* 작성자 */}
            <div style={{ flex: "1 1 240px", border: "1px solid #e2e8f0", backgroundColor: "white", borderRadius: "10px", padding: "1.2rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                    <div style={{ fontSize: "0.8rem", color: "#7c3aed", fontWeight: "bold" }}>👤 작성자</div>
                    {cai.author_grade && (
                        <GradeBadge
                            grade={cai.author_grade}
                            score={cai.author_score}
                            title={`등급 ${cai.score_breakdown?.tier_pts ?? 0}pt + 인기멤버 ${cai.score_breakdown?.popular_bonus ?? 0}pt + 호응도 ${cai.score_breakdown?.engagement ?? 0}pt`}
                        />
                    )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                    <span style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#0f172a" }}>{cai.nickname}</span>
                    {cai.is_popular && (
                        <span style={{ fontSize: "0.7rem", padding: "2px 8px", borderRadius: "12px", backgroundColor: "#fef3c7", color: "#92400e", fontWeight: "bold" }}>🌟 인기멤버</span>
                    )}
                </div>
                <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.3rem" }}>
                    <span style={{ fontWeight: "600" }}>{cai.level_name || "-"}</span>
                    {cai.level_tier != null && (
                        <span style={{ marginLeft: "6px", fontSize: "0.75rem", color: "#94a3b8" }}>tier {cai.level_tier}</span>
                    )}
                </div>
                <div style={{ fontSize: "0.8rem", color: "#64748b" }}>📅 {cai.post_date || "-"}</div>
            </div>

            {/* 카페 */}
            <div style={{ flex: "1 1 240px", border: "1px solid #e2e8f0", backgroundColor: "white", borderRadius: "10px", padding: "1.2rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                    <div style={{ fontSize: "0.8rem", color: "#0ea5e9", fontWeight: "bold" }}>☕ 카페</div>
                    {cai.cafe_grade && (
                        <GradeBadge
                            grade={cai.cafe_grade}
                            score={cai.cafe_score}
                            title={`회원수 ${cai.score_breakdown?.cafe_member_pts ?? 0}pt (랭킹/활성도 미수집)`}
                        />
                    )}
                </div>
                <div style={{ fontSize: "1rem", fontWeight: "bold", color: "#0f172a", marginBottom: "0.5rem", lineHeight: "1.35", maxHeight: "2.7em", overflow: "hidden" }}>
                    {cai.cafe_name || "-"}
                </div>
                <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.3rem" }}>
                    👥 멤버 <span style={{ fontWeight: "bold" }}>{(cai.cafe_member || 0).toLocaleString()}</span>명
                </div>
                {cai.club_id && (
                    <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>🆔 클럽 {cai.club_id}</div>
                )}
            </div>

            {/* 호응도 */}
            <div style={{ flex: "1 1 240px", border: "1px solid #e2e8f0", backgroundColor: "white", borderRadius: "10px", padding: "1.2rem" }}>
                <div style={{ fontSize: "0.8rem", color: "#10b981", fontWeight: "bold", marginBottom: "0.6rem" }}>📊 글 호응도</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
                    <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: "0.75rem", color: "#64748b" }}>👁 조회</div>
                        <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#0f172a" }}>{(cai.view_count || 0).toLocaleString()}</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: "0.75rem", color: "#64748b" }}>❤ 좋아요</div>
                        <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#ef4444" }}>{(cai.like_count || 0).toLocaleString()}</div>
                    </div>
                    <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: "0.75rem", color: "#64748b" }}>💬 댓글</div>
                        <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#3b82f6" }}>{(cai.comment_count || 0).toLocaleString()}</div>
                    </div>
                </div>
                <div style={{ marginTop: "0.6rem", paddingTop: "0.6rem", borderTop: "1px dashed #e2e8f0", fontSize: "0.75rem", color: "#94a3b8", textAlign: "center" }}>
                    글자수 {(item.char_count || 0).toLocaleString()}자 · 이미지 {item.img_count || 0}장
                </div>
            </div>
        </div>
    );
}

export default function CafeAnalysisPage() {
    const [mode, setMode] = usePersistentState('cafe-analysis:mode', 'url'); // 'url' | 'content'

    // ─ 본문 해부 분석 (다중 URL, 최대 10) ───────────────────────
    const [keyword, setKeyword] = usePersistentState('cafe-analysis:keyword', '');
    const [cafeUrls, setCafeUrls] = usePersistentState('cafe-analysis:cafeUrls', '');
    const [loading, setLoading] = usePersistentState('cafe-analysis:loading', false);
    const [result, setResult] = usePersistentState('cafe-analysis:result', null);        // [{url, title, used_keyword, content_chars, data}]
    const [analyzeErrors, setAnalyzeErrors] = usePersistentState('cafe-analysis:analyzeErrors', []);
    const [error, setError] = usePersistentState('cafe-analysis:error', '');

    const handleAnalyze = async () => {
        const urls = cafeUrls.split(/\r?\n/).map(s => s.trim()).filter(s => s.startsWith('http'));
        if (urls.length === 0) { alert('카페글 또는 블로그글 URL을 1개 이상 입력해주세요. (한 줄에 한 개)'); return; }
        if (urls.length > 10) { alert('한 번에 최대 10개까지 분석할 수 있습니다.'); return; }
        setLoading(true); setError(''); setResult(null); setAnalyzeErrors([]);
        try {
            const res = await fetchWithAuth('/api/seo/analyze-cafe-post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword, urls })
            });
            const data = await res.json();
            if (Array.isArray(data.items)) {
                setResult(data.items);
                setAnalyzeErrors(data.errors || []);
                if (data.items.length === 0) setError('분석된 글이 없습니다. URL을 확인해주세요.');
                else addHistory('cafe-analysis', {
                    summary: `본문 해부 ${data.items.length}건${keyword ? ' · ' + keyword : ''}`,
                    payload: { cafeUrls, keyword, result: data.items, analyzeErrors: data.errors || [], mode: 'content' }
                });
            } else {
                setError(data.detail || '분석 중 오류가 발생했습니다.');
            }
        } catch (err) {
            setError(err.message || '서버 연결에 실패했습니다.');
        } finally { setLoading(false); }
    };

    // 작업내역 '다시 보기' → 저장된 입력/결과 복원
    const handleRestore = (entry) => {
        const p = (entry && entry.payload) || {};
        if (p.mode) setMode(p.mode);
        if (p.mode === 'url') {
            if (p.urlsText !== undefined) setUrlsText(p.urlsText);
            if (p.urlItems) setUrlItems(p.urlItems);
            if (p.urlErrors) setUrlErrors(p.urlErrors);
        } else {
            if (p.cafeUrls !== undefined) setCafeUrls(p.cafeUrls);
            if (p.keyword !== undefined) setKeyword(p.keyword);
            if (p.result) setResult(p.result);
            if (p.analyzeErrors) setAnalyzeErrors(p.analyzeErrors);
        }
        try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) {}
    };

    const getScoreColor = (s) => s >= 90 ? "#10b981" : s >= 75 ? "#3b82f6" : s >= 60 ? "#f59e0b" : "#ef4444";

    const renderCard = (key, data, icon) => {
        if (!data) return null;
        return (
            <div className="glass-card" style={{ padding: "1.2rem", display: "flex", flexDirection: "column", boxSizing: "border-box" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.7rem", gap: "0.5rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", minWidth: 0 }}>
                        {icon}
                        <h3 style={{ margin: 0, fontSize: "0.98rem", color: "#1e293b", lineHeight: 1.3 }}>{data.title}</h3>
                    </div>
                    <div style={{ background: `${getScoreColor(data.score)}15`, color: getScoreColor(data.score), padding: "0.15rem 0.6rem", borderRadius: "20px", fontWeight: "bold", fontSize: "1rem", whiteSpace: "nowrap" }}>{data.score}점</div>
                </div>
                <div style={{ color: "#475569", lineHeight: "1.55", fontSize: "0.9rem", backgroundColor: "#f8fafc", padding: "0.8rem", borderRadius: "8px", border: "1px solid #e2e8f0", whiteSpace: "pre-wrap", maxHeight: "160px", overflowY: "auto" }}>{data.analysis}</div>
            </div>
        );
    };

    // 분석 결과 전체를 '상위노출 공식 요약'으로 만들어 글쓰기 화면에 넘긴다.
    const buildAnalysisSource = () => {
        if (!result || !result.length) return { summary: "", kw: "" };
        const kw = (keyword && keyword.trim()) || (result.find(r => r.used_keyword)?.used_keyword || "");
        const lines = [`[상위노출 인기글 분석 요약 — 아래 글들의 성공 패턴을 반영해 '${kw || "주제"}' 새 글을 작성하세요]`];
        result.forEach((item, i) => {
            const d = item.data || {};
            const type = (item.text_type || '').includes('카페') ? '카페글' : '블로그글';
            lines.push(`\n#${i + 1} [${type}] ${item.title || ''}`);
            ['rcon', 'scqa', 'dia', 'chain', 'author_power'].forEach((k) => {
                const v = d[k];
                if (v) lines.push(` - ${v.title}(${v.score}점): ${String(v.analysis || '').replace(/\s+/g, ' ').slice(0, 110)}`);
            });
        });
        let summary = lines.join("\n");
        if (summary.length > 1800) summary = summary.slice(0, 1800) + " …";
        return { summary, kw };
    };

    const goWrite = (channel) => {
        const { summary, kw } = buildAnalysisSource();
        if (!summary) { alert("먼저 분석을 완료해주세요."); return; }
        if (channel === 'blog') {
            try {
                localStorage.setItem('autoWriteSourceData', summary);
                localStorage.setItem('autoWriteRefData', JSON.stringify({ keyword: kw, formula: summary }));
            } catch (e) {}
            window.location.href = `/blog-posting?keyword=${encodeURIComponent(kw)}`;
        } else {
            const params = new URLSearchParams({ source_data: summary, keyword: kw });
            window.location.href = `/cafe-auto?${params.toString()}`;
        }
    };

    // ─ URL 권위 분석 (신규) ─────────────────────────────────────
    const [urlsText, setUrlsText] = usePersistentState('cafe-analysis:urlsText', '');
    const [urlLoading, setUrlLoading] = usePersistentState('cafe-analysis:urlLoading', false);
    const [urlError, setUrlError] = usePersistentState('cafe-analysis:urlError', '');
    const [urlItems, setUrlItems] = usePersistentState('cafe-analysis:urlItems', null);    // [{url, cafe_author_info, ...}]
    const [urlErrors, setUrlErrors] = usePersistentState('cafe-analysis:urlErrors', []);

    const handleUrlAnalyze = async () => {
        const urls = urlsText.split(/\r?\n/).map(s => s.trim()).filter(s => s.startsWith('http'));
        if (urls.length === 0) { alert('카페 URL을 1개 이상 입력해주세요. (한 줄에 한 개)'); return; }
        if (urls.length > 5) { alert('한 번에 최대 5개까지 분석할 수 있습니다.'); return; }
        setUrlLoading(true); setUrlError(''); setUrlItems(null); setUrlErrors([]);
        try {
            const res = await fetchWithAuth('/api/seo/analyze-cafe-urls', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls })
            });
            if (!res.ok) {
                const j = await res.json().catch(() => ({}));
                throw new Error(j.detail || `서버 오류 (${res.status})`);
            }
            const data = await res.json();
            setUrlItems(data.items || []);
            setUrlErrors(data.errors || []);
            if ((data.items || []).length) addHistory('cafe-analysis', {
                summary: `URL 권위 분석 ${data.items.length}건`,
                payload: { urlsText, urlItems: data.items, urlErrors: data.errors || [], mode: 'url' }
            });
        } catch (err) {
            setUrlError(err.message || '서버 연결에 실패했습니다.');
        } finally { setUrlLoading(false); }
    };

    const tabBtn = (key, label, Icon) => (
        <button
            onClick={() => setMode(key)}
            style={{
                padding: '0.7rem 1.4rem', border: 'none', cursor: 'pointer',
                borderBottom: mode === key ? '3px solid #3b82f6' : '3px solid transparent',
                background: 'transparent',
                color: mode === key ? '#3b82f6' : '#64748b',
                fontWeight: mode === key ? '700' : '500', fontSize: '1rem',
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                marginBottom: '-1px',
            }}
        >
            <Icon size={18} />{label}
        </button>
    );

    return (
        <div style={{ maxWidth: "1200px", margin: "0 auto", paddingBottom: "3rem" }}>
            <div style={{ marginBottom: "1rem" }}>
                <h1 style={{ fontSize: "2rem", color: "#1e293b", margin: "0 0 0.5rem 0" }}>카페글·블로그글 분석</h1>
                <p style={{ color: "#64748b", margin: 0 }}>네이버 검색 인기글을 분석합니다 — URL 권위 분석(카페 작성자/카페 권위) + 본문 해부 분석(카페글·블로그글 유형 자동 판별).</p>
            </div>

            {/* 탭 */}
            <div style={{ display: 'flex', gap: '0.2rem', borderBottom: '1px solid #e2e8f0', marginBottom: '1.5rem' }}>
                {tabBtn('url', 'URL 권위 분석', Link2)}
                {tabBtn('content', '본문 해부 분석', FileText)}
            </div>

            {/* ───────── URL 권위 분석 ───────── */}
            {mode === 'url' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 380px) 1fr', gap: '1.5rem', alignItems: 'start' }}>
                    {/* 입력 */}
                    <div className="glass-card" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 0.6rem 0', fontSize: '1rem', color: '#334155' }}>분석할 카페 글 URL</h3>
                        <p style={{ margin: '0 0 0.8rem 0', fontSize: '0.8rem', color: '#94a3b8' }}>한 줄에 한 개씩, 최대 5개. <code>cafe.naver.com/...</code> 형식</p>
                        <textarea
                            value={urlsText}
                            onChange={(e) => setUrlsText(e.target.value)}
                            placeholder={"https://cafe.naver.com/example/12345\nhttps://cafe.naver.com/another/6789"}
                            rows={8}
                            style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.85rem', boxSizing: 'border-box', fontFamily: 'monospace', lineHeight: '1.5' }}
                        />
                        <button
                            onClick={handleUrlAnalyze}
                            disabled={urlLoading}
                            className="btn-primary"
                            style={{ marginTop: '1rem', width: '100%', padding: '0.9rem', fontSize: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
                        >
                            {urlLoading ? '분석 중… (약 15~30초)' : <><BarChart3 size={18} />권위 분석 시작</>}
                        </button>
                        {urlError && (
                            <div style={{ marginTop: '1rem', padding: '0.9rem', background: '#fef2f2', color: '#b91c1c', borderRadius: '8px', border: '1px solid #fecaca', fontSize: '0.85rem' }}>
                                <AlertCircle size={16} style={{ verticalAlign: 'middle', marginRight: '4px' }} />{urlError}
                            </div>
                        )}

                        {/* 점수 기준 안내 */}
                        <div style={{ marginTop: '1.5rem', padding: '0.9rem', background: '#f8fafc', borderRadius: '8px', fontSize: '0.78rem', color: '#475569', lineHeight: '1.6' }}>
                            <strong style={{ color: '#334155' }}>등급 기준</strong><br />
                            <span style={{ color: '#92400e', fontWeight: 'bold' }}>S</span> 80+ ·{' '}
                            <span style={{ color: '#065f46', fontWeight: 'bold' }}>A</span> 65+ ·{' '}
                            <span style={{ color: '#1e40af', fontWeight: 'bold' }}>B</span> 45+ ·{' '}
                            <span style={{ color: '#9a3412', fontWeight: 'bold' }}>C</span> 25+ ·{' '}
                            <span style={{ color: '#475569', fontWeight: 'bold' }}>D</span> 미만
                            <br /><br />
                            <span style={{ color: '#94a3b8' }}>
                                Author = 등급 + 인기멤버 + 호응도(조회/좋아요/댓글)<br />
                                Cafe = 회원수 정규화 (랭킹/활성도 추후 합류)
                            </span>
                        </div>
                    </div>

                    {/* 결과 */}
                    <div>
                        {!urlItems && !urlLoading && (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px', border: '2px dashed #cbd5e1', borderRadius: '16px', color: '#94a3b8' }}>
                                <Users size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                                <p style={{ fontSize: '1rem', margin: 0 }}>카페 URL을 입력하면 작성자/카페 권위 지수를 분석합니다.</p>
                                <p style={{ fontSize: '0.85rem', marginTop: '0.4rem' }}>닉네임 · 등급 · 인기멤버 · 글 호응도 · 카페 회원수</p>
                            </div>
                        )}
                        {urlLoading && (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
                                <div style={{ width: '50px', height: '50px', border: '4px solid #f3f3f3', borderTop: '4px solid #3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                                <p style={{ marginTop: '1.5rem', color: '#3b82f6', fontWeight: 'bold', fontSize: '1rem' }}>카페 데이터 수집 중…</p>
                                <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
                            </div>
                        )}
                        {urlItems && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                                {urlItems.length === 0 && (
                                    <div style={{ padding: '1rem', background: '#fef2f2', color: '#b91c1c', borderRadius: '8px' }}>분석 가능한 URL이 없습니다.</div>
                                )}
                                {urlItems.map((item, idx) => (
                                    <div key={idx} className="glass-card" style={{ padding: '1.5rem' }}>
                                        <div style={{ marginBottom: '1rem' }}>
                                            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '4px' }}>#{idx + 1}</div>
                                            <a href={item.url} target="_blank" rel="noreferrer" style={{ fontSize: '1.05rem', fontWeight: 'bold', color: '#1e293b', textDecoration: 'none' }}>
                                                {item.title || item.url}
                                            </a>
                                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px', wordBreak: 'break-all' }}>{item.url}</div>
                                        </div>
                                        <CafeAuthorityCards item={item} />
                                    </div>
                                ))}
                                {urlErrors.length > 0 && (
                                    <div className="glass-card" style={{ padding: '1.2rem', background: '#fef2f2', border: '1px solid #fecaca' }}>
                                        <div style={{ fontWeight: 'bold', color: '#b91c1c', marginBottom: '0.5rem' }}>분석 실패한 URL</div>
                                        {urlErrors.map((e, idx) => (
                                            <div key={idx} style={{ fontSize: '0.85rem', color: '#7f1d1d', marginBottom: '4px' }}>
                                                <code style={{ background: 'white', padding: '1px 6px', borderRadius: '4px' }}>{e.url}</code> — {e.error}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ───────── 본문 해부 분석 (기존) ───────── */}
            {mode === 'content' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div className="glass-card" style={{ padding: '2rem' }}>
                        <div style={{ marginBottom: '1.2rem' }}>
                            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#334155' }}>카페글·블로그글 URL <span style={{ fontWeight: 'normal', color: '#94a3b8', fontSize: '0.85rem' }}>(한 줄에 하나, 최대 10개)</span></label>
                            <textarea value={cafeUrls} onChange={(e) => setCafeUrls(e.target.value)} placeholder={"https://cafe.naver.com/카페주소/글번호\nhttps://blog.naver.com/블로그아이디/글번호\n..."} rows={5} style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.95rem', boxSizing: 'border-box', resize: 'vertical', fontFamily: 'inherit', lineHeight: '1.6' }} />
                            <p style={{ margin: '0.4rem 0 0', fontSize: '0.83rem', color: '#94a3b8' }}>네이버 검색 인기글의 <b>카페글·블로그글 URL</b>을 섞어 넣어도 됩니다. 서버가 글 유형을 자동 판별해 각각 맞는 지표로 해부합니다. (현재 {cafeUrls.split(/\r?\n/).filter(s => s.trim().startsWith('http')).length}개)</p>
                        </div>
                        {/* 타겟 키워드 + 분석 시작 버튼 한 줄 */}
                        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
                            <div style={{ flex: 1 }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#334155' }}>타겟 키워드 <span style={{ fontWeight: 'normal', color: '#94a3b8', fontSize: '0.85rem' }}>(선택 — 비우면 각 글 제목 기준)</span></label>
                                <input type="text" value={keyword} onChange={(e) => setKeyword(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()} placeholder="예: 강남역 맛집" style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '1rem', boxSizing: 'border-box' }} />
                            </div>
                            <button onClick={handleAnalyze} disabled={loading} className="btn-primary" style={{ padding: '0.8rem 1.6rem', fontSize: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', whiteSpace: 'nowrap', flexShrink: 0 }}>
                                {loading ? <>분석 중... (10~20초)</> : <><Search size={18} />AI 해부 분석 시작</>}
                            </button>
                        </div>
                        {error && (<div style={{ marginTop: '1rem', padding: '1rem', background: '#fef2f2', color: '#b91c1c', borderRadius: '8px', border: '1px solid #fecaca' }}>{error}</div>)}
                    </div>

                    {!result && !loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '220px', border: '2px dashed #cbd5e1', borderRadius: '16px', color: '#94a3b8' }}>
                            <Activity size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                            <p style={{ fontSize: '1.1rem', margin: 0 }}>카페글·블로그글 URL을 입력하고 분석을 시작해보세요.</p>
                            <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>AI가 5가지 주요 알고리즘 지표를 통해 글을 해부합니다. (유형 자동 판별)</p>
                        </div>
                    )}
                    {loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '220px' }}>
                            <div style={{ width: '50px', height: '50px', border: '4px solid #f3f3f3', borderTop: '4px solid #3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                            <p style={{ marginTop: '1.5rem', color: '#3b82f6', fontWeight: 'bold', fontSize: '1.1rem' }}>네이버 알고리즘 패턴 분석 중...</p>
                            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
                        </div>
                    )}
                    {result && !loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            {analyzeErrors.length > 0 && (
                                <div style={{ padding: '0.8rem 1rem', background: '#fef2f2', color: '#b91c1c', borderRadius: '8px', border: '1px solid #fecaca', fontSize: '0.88rem' }}>
                                    분석 실패 {analyzeErrors.length}건: {analyzeErrors.map(e => e.url).join(', ')}
                                </div>
                            )}
                            {/* 전체 분석 기반으로 새 글쓰기 */}
                            <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', alignItems: 'center', padding: '1rem', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '10px' }}>
                                <span style={{ fontWeight: 'bold', color: '#0369a1', fontSize: '0.92rem' }}>이 분석을 바탕으로 새 글 작성 →</span>
                                <button onClick={() => goWrite('blog')} style={{ padding: '0.6rem 1.2rem', background: '#16a34a', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>📝 블로그 글쓰기</button>
                                <button onClick={() => goWrite('cafe')} style={{ padding: '0.6rem 1.2rem', background: '#7c3aed', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>☕ 카페 글쓰기</button>
                            </div>
                            {result.map((item, i) => {
                                const d = item.data || {};
                                return (
                                    <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                        <div style={{ borderBottom: '2px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                                            <div style={{ fontSize: '1rem', fontWeight: 'bold', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                {(() => {
                                                    const isCafe = (item.text_type || '').includes('카페');
                                                    return <span style={{ fontSize: '0.72rem', fontWeight: 'bold', padding: '0.15rem 0.55rem', borderRadius: '999px', background: isCafe ? '#f5f3ff' : '#f0fdf4', color: isCafe ? '#7c3aed' : '#16a34a', border: `1px solid ${isCafe ? '#ddd6fe' : '#bbf7d0'}`, whiteSpace: 'nowrap' }}>{isCafe ? '☕ 카페글' : '📝 블로그글'}</span>;
                                                })()}
                                                <span>#{i + 1} {item.title || '제목 없음'}</span>
                                            </div>
                                            <a href={item.url} target="_blank" rel="noreferrer" style={{ fontSize: '0.8rem', color: '#2563eb', wordBreak: 'break-all' }}>{item.url}</a>
                                            {item.used_keyword && <span style={{ marginLeft: '0.5rem', fontSize: '0.78rem', color: '#94a3b8' }}>키워드: {item.used_keyword} · {item.content_chars}자</span>}
                                        </div>
                                        {renderCard('author_power', d.author_power, <ShieldAlert color="#f59e0b" />)}
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', alignItems: 'start' }}>
                                            {renderCard('rcon', d.rcon, <Search color="#3b82f6" />)}
                                            {renderCard('scqa', d.scqa, <FileText color="#10b981" />)}
                                            {renderCard('dia', d.dia, <CheckCircle2 color="#8b5cf6" />)}
                                            {renderCard('chain', d.chain, <Activity color="#ec4899" />)}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            <WorkHistory menuKey="cafe-analysis" onRestore={handleRestore} />
        </div>
    );
}
