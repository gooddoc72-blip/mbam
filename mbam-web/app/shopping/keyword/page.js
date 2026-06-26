'use client';
import { useState } from 'react';
import { Search, Loader2, Key, Tag, Check, Copy } from 'lucide-react';

import { fetchWithAuth } from '../../utils/api';
import { usePersistentState } from '../../utils/persistentState';
import { addHistory } from '../../utils/workHistory';
import WorkHistory from '../../components/WorkHistory';

export default function ShoppingKeyword() {
    const [seedKeyword, setSeedKeyword] = usePersistentState('shopping-keyword:seedKeyword', '');
    const [loading, setLoading] = usePersistentState('shopping-keyword:loading', false);
    const [result, setResult] = usePersistentState('shopping-keyword:result', null);

    // 클린 토큰 선택 상태(상품명 조립에 들어갈 토큰)
    const [selected, setSelected] = useState(() => new Set());
    // 연관 키워드 선택 상태(선택 시 시드 제외 단어가 상품명 앞쪽 롱테일로 들어감)
    const [selectedRel, setSelectedRel] = useState(() => new Set());
    const [brand, setBrand] = useState('');
    const [assembling, setAssembling] = useState(false);
    const [assembled, setAssembled] = useState(null); // { title, length, tags }
    const [copiedTags, setCopiedTags] = useState(false);
    const [showAllRelated, setShowAllRelated] = useState(false); // 연관키워드 더보기

    const handleAnalyze = async () => {
        if (!seedKeyword) return alert('시드 키워드를 입력해주세요.');

        setLoading(true);
        setResult(null);
        setAssembled(null);
        try {
            const res = await fetchWithAuth(`/api/shopping/keyword/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed_keyword: seedKeyword })
            });
            const data = await res.json();
            setResult(data);
            setShowAllRelated(false);
            setSelectedRel(new Set());
            // 분석 직후 전체 토큰을 기본 선택(원하면 클릭으로 해제)
            setSelected(new Set(data.valid_tokens_pool || []));
            addHistory('shopping-keyword', { summary: `키워드 분석 · ${seedKeyword}`, payload: { seedKeyword, result: data } });
        } catch (e) {
            alert('오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    const handleRestore = (entry) => {
        const p = (entry && entry.payload) || {};
        if (p.seedKeyword !== undefined) setSeedKeyword(p.seedKeyword);
        if (p.result) { setResult(p.result); setSelected(new Set(p.result.valid_tokens_pool || [])); }
        try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) {}
    };

    const pool = result?.valid_tokens_pool || [];

    const toggleToken = (token) => {
        setSelected(prev => {
            const next = new Set(prev);
            if (next.has(token)) next.delete(token);
            else next.add(token);
            return next;
        });
    };

    const selectAll = () => setSelected(new Set(pool));
    const clearAll = () => setSelected(new Set());

    // 풀 순서를 유지한 선택 토큰(검색량/우선순위 순서가 조립에 반영되도록)
    const orderedSelected = pool.filter(t => selected.has(t));

    const relList = result?.related_with_volume || [];

    const toggleRel = (kw) => {
        setSelectedRel(prev => {
            const next = new Set(prev);
            if (next.has(kw)) next.delete(kw); else next.add(kw);
            return next;
        });
    };

    // 선택한 연관키워드에서 시드를 뺀 단어만 추출(예: "코스트코 그릭요거트" → "코스트코")
    const extractRelTokens = () => {
        if (!result) return [];
        const seedNs = (result.seed_keyword || '').replace(/\s/g, '');
        const out = [];
        const seen = new Set(selected); // 이미 선택된 태그와 중복 방지
        relList.forEach(r => {
            if (!selectedRel.has(r.keyword)) return;
            r.keyword.split(/\s+/).forEach(w => {
                const word = w.split(seedNs).join('').trim(); // 단어에서 시드 제거
                if (word.length >= 2 && !seen.has(word)) { seen.add(word); out.push(word); }
            });
        });
        return out;
    };

    const handleAssemble = async () => {
        if (!result) return;
        const relTokens = extractRelTokens();
        // 연관키워드 추출어(롱테일)를 앞에, 선택 태그를 뒤에 배치
        const combined = [];
        const seen = new Set();
        [...relTokens, ...orderedSelected].forEach(t => { if (!seen.has(t)) { seen.add(t); combined.push(t); } });
        if (combined.length === 0) return alert('태그 또는 연관 키워드를 1개 이상 선택해주세요.');

        setAssembling(true);
        setAssembled(null);
        setCopiedTags(false);
        try {
            const res = await fetchWithAuth('/api/shopping/keyword/assemble', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    seed_keyword: result.seed_keyword,
                    brand_name: brand,
                    tokens: combined,                 // 연관키워드 추출어(앞) + 선택 태그
                    ai_modifiers: pool                // 태그 추천 풀(전체) → 상품명에 안 쓰인 단어를 태그로 수집
                })
            });
            const data = await res.json();
            if (data.optimized_title) {
                setAssembled({
                    title: data.optimized_title,
                    length: data.length,
                    tags: data.recommended_tags || [],
                    warning: data.warning
                });
            }
        } catch (e) {
            alert('상품명 생성 중 오류가 발생했습니다.');
        } finally {
            setAssembling(false);
        }
    };

    const copyTags = () => {
        if (!assembled?.tags?.length) return;
        // 네이버 쇼핑 태그는 쉼표 구분 입력 → 쉼표로 복사
        navigator.clipboard.writeText(assembled.tags.join(', '));
        setCopiedTags(true);
        setTimeout(() => setCopiedTags(false), 1500);
    };

    return (
        <div style={{ padding: '2rem' }}>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 'bold', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Key size={28} /> 쇼핑 키워드 분석 및 정제 모듈
            </h1>
            <div style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
                <p style={{ color: '#64748b', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
                    시드 키워드를 입력하면, 연관 키워드를 수집한 후 카테고리가 일치하는 것만 필터링하고,<br/>
                    형태소 분석(Mecab/Kiwi)을 통해 스팸 단어와 특수기호를 완벽히 제거한 '클린 토큰 풀(Pool)'을 생성합니다.
                </p>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                    <input value={seedKeyword} onChange={e => setSeedKeyword(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleAnalyze()} placeholder="시드 키워드 (예: 무선 청소기)" style={{ flex: 1, padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                    <button onClick={handleAnalyze} disabled={loading} style={{ padding: '0.75rem 2rem', background: '#3b82f6', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {loading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />} 데이터 정제 시작
                    </button>
                </div>

                {result && (
                    <div style={{ padding: '1.5rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#0f172a' }}>분석 결과</h3>
                            <span style={{ fontSize: '0.85rem', color: '#64748b', background: '#e2e8f0', padding: '0.3rem 0.8rem', borderRadius: '999px' }}>
                                {result.message}
                            </span>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem' }}>
                            <div style={{ background: 'white', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                <h4 style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#334155' }}>데이터 수집 현황</h4>
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0, color: '#475569', fontSize: '0.95rem' }}>
                                    <li style={{ padding: '0.5rem 0', borderBottom: '1px solid #f1f5f9' }}>시드 키워드: <strong style={{ color: '#0f172a' }}>{result.seed_keyword}</strong></li>
                                    <li style={{ padding: '0.5rem 0', borderBottom: '1px solid #f1f5f9' }}>분리된 시드 토큰: <strong>{(result.seed_tokens || []).join(', ')}</strong></li>
                                    <li style={{ padding: '0.5rem 0' }}>수집된 연관 키워드: <strong>{result.related_keywords_count}개</strong></li>
                                </ul>
                            </div>

                            <div style={{ background: 'white', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                                    <h4 style={{ fontWeight: 'bold', color: '#334155', display: 'flex', alignItems: 'center', gap: '0.3rem', margin: 0 }}>
                                        <Tag size={16} /> 태그 · 상품명용 토큰 (총 {pool.length}개) · <span style={{ color: '#0284c7' }}>선택 {orderedSelected.length}개</span>
                                    </h4>
                                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                                        <button onClick={selectAll} style={{ fontSize: '0.8rem', padding: '0.25rem 0.7rem', borderRadius: '6px', border: '1px solid #cbd5e1', background: 'white', color: '#475569', cursor: 'pointer' }}>전체 선택</button>
                                        <button onClick={clearAll} style={{ fontSize: '0.8rem', padding: '0.25rem 0.7rem', borderRadius: '6px', border: '1px solid #cbd5e1', background: 'white', color: '#475569', cursor: 'pointer' }}>전체 해제</button>
                                    </div>
                                </div>
                                <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' }}>쇼핑 상품명에 실제 쓰이는 단어 위주로 정제된 <strong>태그</strong>입니다. <strong>클릭</strong>해 상품명에 넣을 단어를 선택하세요.</p>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                    {pool.map((token, idx) => {
                                        const on = selected.has(token);
                                        return (
                                            <button
                                                key={idx}
                                                onClick={() => toggleToken(token)}
                                                style={{
                                                    background: on ? '#0284c7' : '#e0f2fe',
                                                    color: on ? 'white' : '#0284c7',
                                                    padding: '0.3rem 0.8rem',
                                                    borderRadius: '999px',
                                                    fontSize: '0.9rem',
                                                    fontWeight: '500',
                                                    border: on ? '1px solid #0284c7' : '1px solid #bae6fd',
                                                    cursor: 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.25rem'
                                                }}>
                                                {on && <Check size={13} />}{token}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* 연관 키워드 (검색량순) — 태그와 분리, 선택 가능 */}
                        {relList.length > 0 && (() => {
                            const hasVol = relList.some(r => r.volume > 0);
                            const shown = showAllRelated ? relList : relList.slice(0, 40);
                            return (
                                <div style={{ marginTop: '1.5rem', background: 'white', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                    <h4 style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#334155', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                        <Search size={16} /> 연관 키워드 ({relList.length}개) · <span style={{ color: '#7c3aed' }}>선택 {selectedRel.size}개</span>{hasVol && <span style={{ fontWeight: 'normal', fontSize: '0.82rem', color: '#94a3b8' }}> · 검색량순(PC+MO)</span>}
                                    </h4>
                                    <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' }}>실제 검색되는 연관 검색어입니다. <strong>클릭</strong>하면 시드를 뺀 단어(예: "코스트코 그릭요거트"→<strong>코스트코</strong>)가 상품명 앞쪽 롱테일로 들어갑니다.</p>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                        {shown.map((r, idx) => {
                                            const on = selectedRel.has(r.keyword);
                                            return (
                                                <button
                                                    key={idx}
                                                    onClick={() => toggleRel(r.keyword)}
                                                    style={{
                                                        background: on ? '#7c3aed' : '#f1f5f9',
                                                        color: on ? 'white' : '#475569',
                                                        padding: '0.3rem 0.7rem',
                                                        borderRadius: '8px',
                                                        fontSize: '0.88rem',
                                                        border: on ? '1px solid #7c3aed' : '1px solid #e2e8f0',
                                                        cursor: 'pointer',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '0.4rem'
                                                    }}>
                                                    {on && <Check size={13} />}{r.keyword}
                                                    {r.volume > 0 && <strong style={{ color: on ? '#ddd6fe' : '#0284c7', fontSize: '0.8rem' }}>{r.volume.toLocaleString()}</strong>}
                                                </button>
                                            );
                                        })}
                                    </div>
                                    {relList.length > 40 && (
                                        <button onClick={() => setShowAllRelated(v => !v)} style={{ marginTop: '0.8rem', fontSize: '0.85rem', padding: '0.35rem 1rem', borderRadius: '6px', border: '1px solid #cbd5e1', background: 'white', color: '#475569', cursor: 'pointer' }}>
                                            {showAllRelated ? '접기' : `더보기 (+${relList.length - 40})`}
                                        </button>
                                    )}
                                </div>
                            );
                        })()}

                        {/* SEO Title Assembler Section */}
                        <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'white', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '1rem' }}>🤖 네이버 거리점수 반영 SEO 상품명 조립기</h3>
                            <p style={{ fontSize: '0.9rem', color: '#64748b', marginBottom: '1.5rem' }}>
                                메인 키워드와의 <strong>형태소 거리(Proximity)</strong>를 최소화하는 네이버 알고리즘 최적화 방식으로 상품명을 자동 조립합니다.<br/>
                                <span style={{color: '#0284c7'}}>[롱테일 키워드 2개] + [브랜드명] + [메인(시드)키워드] + [상위노출 핵심 수식어들]</span> 순서로 결합됩니다.
                            </p>

                            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                                <input value={brand} onChange={e => setBrand(e.target.value)} placeholder="브랜드명 (선택사항)" style={{ flex: 1, padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                                <button
                                    onClick={handleAssemble}
                                    disabled={assembling}
                                    style={{ padding: '0.75rem 2rem', background: '#10b981', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    {assembling ? <Loader2 size={18} className="animate-spin" /> : null} 최적화 상품명 생성
                                </button>
                            </div>

                            <div style={{ padding: '1.5rem', background: '#f1f5f9', borderRadius: '8px', textAlign: 'center' }}>
                                {assembled ? (
                                    <>
                                        <div style={{ fontSize: '1.3rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '0.5rem' }}>{assembled.title}</div>
                                        <div style={{ fontSize: '0.9rem', color: assembled.length > 50 ? 'red' : '#10b981' }}>총 {assembled.length}자 (네이버 권장 50자 이내)</div>
                                        {assembled.warning && <div style={{ fontSize: '0.85rem', color: '#dc2626', marginTop: '0.4rem' }}>⚠️ {assembled.warning}</div>}
                                    </>
                                ) : (
                                    <div style={{ fontSize: '1.3rem', fontWeight: 'bold', color: '#0f172a' }}>토큰을 선택하고 버튼을 눌러 상품명을 생성해보세요!</div>
                                )}
                            </div>

                            {/* 수집된 태그 (상품명에 안 쓰인 연관어 → 쇼핑 태그용) */}
                            {assembled && assembled.tags.length > 0 && (
                                <div style={{ marginTop: '1.5rem', padding: '1.25rem', background: '#fefce8', borderRadius: '8px', border: '1px solid #fde68a' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                                        <h4 style={{ fontWeight: 'bold', color: '#92400e', display: 'flex', alignItems: 'center', gap: '0.3rem', margin: 0 }}>
                                            <Tag size={16} /> 수집된 태그 ({assembled.tags.length}개)
                                        </h4>
                                        <button onClick={copyTags} style={{ fontSize: '0.8rem', padding: '0.3rem 0.8rem', borderRadius: '6px', border: '1px solid #f59e0b', background: copiedTags ? '#f59e0b' : 'white', color: copiedTags ? 'white' : '#b45309', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                            {copiedTags ? <Check size={13} /> : <Copy size={13} />} {copiedTags ? '복사됨' : '태그 전체 복사'}
                                        </button>
                                    </div>
                                    <p style={{ fontSize: '0.83rem', color: '#a16207', marginBottom: '0.75rem' }}>상품명에 넣지 않은 연관어입니다. 네이버 쇼핑 등록 시 <strong>태그(키워드)</strong> 칸에 활용하세요.</p>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                        {assembled.tags.map((tag, idx) => (
                                            <span key={idx} style={{ background: '#fef3c7', color: '#92400e', padding: '0.3rem 0.8rem', borderRadius: '999px', fontSize: '0.9rem', fontWeight: '500' }}>
                                                #{tag}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                    </div>
                )}
            </div>
            <WorkHistory menuKey="shopping-keyword" onRestore={handleRestore} />
        </div>
    );
}
