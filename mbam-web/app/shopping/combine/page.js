'use client';
import { useState } from 'react';
import { Search, Loader2, Sparkles, Tags, AlertCircle, TrendingUp, CheckCircle, Copy } from 'lucide-react';

import { fetchWithAuth } from '../../utils/api';
import { addHistory } from '../../utils/workHistory';
import WorkHistory from '../../components/WorkHistory';

export default function ShoppingCombine() {
    const [brandName, setBrandName] = useState('');
    const [seedKeyword, setSeedKeyword] = useState('');
    const [tokensInput, setTokensInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    
    // AI 자동 제안용 상태
    const [aiLoading, setAiLoading] = useState(false);
    const [aiResult, setAiResult] = useState(null);

    const handleAssemble = async () => {
        if (!seedKeyword) return alert('메인 시드 키워드를 입력해주세요.');
        if (!tokensInput) return alert('조합할 단어(토큰) 풀을 쉼표로 구분하여 입력해주세요.');
        
        const tokensArray = tokensInput.split(',').map(t => t.trim()).filter(t => t);
        
        setLoading(true);
        setResult(null);
        try {
            const res = await fetchWithAuth(`/api/shopping/keyword/assemble`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    brand_name: brandName,
                    seed_keyword: seedKeyword,
                    tokens: tokensArray,
                    ai_modifiers: aiResult ? [
                        ...(aiResult.top_modifiers || []),
                        ...(aiResult.related_keywords ? aiResult.related_keywords.map(k => k.keyword) : [])
                    ] : []
                })
            });
            const data = await res.json();
            setResult(data);
            try { addHistory('shopping-combine', { summary: `상품명 조합 · ${seedKeyword}` }); } catch (e2) {}
        } catch (e) {
            alert('오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    const handleAiSuggest = async () => {
        if (!seedKeyword) return alert('메인 시드 키워드를 입력해주세요.');
        
        setAiLoading(true);
        setAiResult(null);
        try {
            const res = await fetchWithAuth(`/api/shopping/keyword/analyze-and-suggest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    brand_name: brandName,
                    seed_keyword: seedKeyword
                })
            });
            const data = await res.json();
            setAiResult(data);
        } catch (e) {
            alert('오류가 발생했습니다.');
        } finally {
            setAiLoading(false);
        }
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
        alert('상품명이 복사되었습니다!');
    };

    return (
        <div style={{ padding: '2rem' }}>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 'bold', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={28} /> 상품명 최적화 스튜디오
            </h1>
            
            {/* 공통 입력 영역 */}
            <div style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', marginBottom: '2rem' }}>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Search size={20} /> 1단계: 기본 정보 입력
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '0.9rem' }}>브랜드/제조사 (선택)</label>
                        <input value={brandName} onChange={e => setBrandName(e.target.value)} placeholder="예: 삼성전자" style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                    </div>
                    <div>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '0.9rem' }}>메인 시드 키워드 (필수)</label>
                        <input value={seedKeyword} onChange={e => setSeedKeyword(e.target.value)} placeholder="예: 무선 청소기" style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                
                {/* 왼쪽: AI 자동 분석 및 제안 */}
                <div style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#4f46e5' }}>
                        <TrendingUp size={20} /> 2단계: AI 트렌드 분석 및 1초 완성
                    </h2>
                    <p style={{ color: '#64748b', marginBottom: '1.5rem', fontSize: '0.9rem', lineHeight: '1.5' }}>
                        네이버 쇼핑 1위~40위 경쟁사들의 상품명을 실시간으로 분석하고, 
                        <strong>최신성 버프(롱테일 키워드 우선 노출)</strong> 전략을 적용하여 
                        가장 완벽한 형태소 구조의 상품명 3가지를 자동 제안합니다.
                    </p>

                    <button onClick={handleAiSuggest} disabled={aiLoading} style={{ width: '100%', padding: '1rem', background: '#4f46e5', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '1.5rem' }}>
                        {aiLoading ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />} 1~40위 분석 및 상품명 추천받기
                    </button>

                    {aiResult && (
                        <div style={{ background: '#f8fafc', padding: '1.5rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            <div style={{ marginBottom: '1.5rem' }}>
                                <h3 style={{ fontSize: '0.95rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.5rem' }}>🔥 1~40위 경쟁사들이 가장 많이 쓴 핵심 수식어</h3>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                    {(aiResult.top_modifiers || []).map((mod, idx) => (
                                        <span key={idx} style={{ background: '#e0e7ff', color: '#4338ca', padding: '0.3rem 0.6rem', borderRadius: '4px', fontSize: '0.85rem' }}>
                                            {mod}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {aiResult.related_keywords && aiResult.related_keywords.length > 0 && (
                                <div style={{ marginBottom: '2rem' }}>
                                    <h3 style={{ fontSize: '0.95rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                        <TrendingUp size={16} color="#0284c7" /> 📊 연관 검색어 (PC / 모바일)
                                    </h3>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '0.4rem', marginTop: '0.8rem' }}>
                                        {aiResult.related_keywords.map((kw, idx) => (
                                            <div key={idx} style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.2rem', transition: 'all 0.2s', cursor: 'default' }}
                                                 onMouseEnter={e => { e.currentTarget.style.borderColor = '#0ea5e9'; e.currentTarget.style.boxShadow = '0 1px 2px rgba(14, 165, 233, 0.1)'; }}
                                                 onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.boxShadow = 'none'; }}>
                                                <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={kw.keyword}>
                                                    {kw.keyword}
                                                </div>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: '#64748b' }}>
                                                    <span><span style={{ color: '#0284c7' }}>P</span> {kw.pc_vol ? kw.pc_vol.toLocaleString() : 0}</span>
                                                    <span><span style={{ color: '#059669' }}>M</span> {kw.mo_vol ? kw.mo_vol.toLocaleString() : 0}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                    <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.5rem' }}>* 롱테일 키워드 전략을 위해 조회수가 낮은 알짜배기 키워드들을 우측의 <strong>수동 조합 풀</strong>에 추가해 보세요!</p>
                                </div>
                            )}

                            <h3 style={{ fontSize: '1.05rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <CheckCircle size={18} color="#10b981" /> AI 추천 상품명 (클릭하여 복사)
                            </h3>
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {(aiResult.suggestions || []).map((sugg, idx) => (
                                    <div key={idx} style={{ background: 'white', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '1rem', position: 'relative', cursor: 'pointer', transition: 'all 0.2s' }}
                                         onMouseEnter={e => e.currentTarget.style.borderColor = '#4f46e5'}
                                         onMouseLeave={e => e.currentTarget.style.borderColor = '#cbd5e1'}
                                         onClick={() => copyToClipboard(sugg.title)}>
                                        <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#6366f1', marginBottom: '0.3rem' }}>{sugg.strategy}</div>
                                        <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#1e293b', marginBottom: '0.4rem' }}>{sugg.title}</div>
                                        <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{sugg.desc} ({sugg.title.length}자)</div>
                                        <Copy size={16} color="#94a3b8" style={{ position: 'absolute', top: '1rem', right: '1rem' }} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* 오른쪽: 수동 커스텀 조합 */}
                <div style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#8b5cf6' }}>
                        <Tags size={20} /> (옵션) 수동 커스텀 조립
                    </h2>
                    <p style={{ color: '#64748b', marginBottom: '1.5rem', fontSize: '0.9rem', lineHeight: '1.5' }}>
                        AI 추천 상품명에 원하는 단어를 추가하고 싶거나, 직접 추출해둔 키워드들이 있다면 아래에 쉼표로 구분하여 입력하세요. 어뷰징을 방지하며 50자 이내로 안전하게 조립해 줍니다.
                    </p>

                    <div style={{ marginBottom: '1.5rem' }}>
                        <textarea 
                            value={tokensInput} 
                            onChange={e => setTokensInput(e.target.value)} 
                            placeholder="예: 가성비, 소형, 강력, 먼지, 거치대, 화이트..." 
                            style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0', minHeight: '100px', resize: 'vertical' }} 
                        />
                    </div>

                    <button onClick={handleAssemble} disabled={loading} style={{ width: '100%', padding: '1rem', background: '#8b5cf6', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                        {loading ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />} 커스텀 단어로 수동 조립하기
                    </button>

                    {result && (
                        <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            {result.warning && (
                                <div style={{ background: '#fef3c7', color: '#b45309', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.95rem' }}>
                                    <AlertCircle size={18} style={{ marginTop: '0.1rem' }} />
                                    <div><strong>주의사항: </strong>{result.warning}</div>
                                </div>
                            )}

                            <div style={{ marginBottom: '2rem' }}>
                                <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.8rem' }}>🎯 조립 완성 상품명 ({result.length}자)</h3>
                                <div style={{ background: '#f1f5f9', padding: '1.5rem', borderRadius: '8px', fontSize: '1.5rem', fontWeight: 'bold', color: '#0f172a', border: '2px dashed #cbd5e1' }}>
                                    {result.optimized_title || result.assembled_title}
                                </div>
                            </div>

                            <div>
                                <h3 style={{ fontSize: '0.95rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.8rem' }}>
                                    잔여 키워드 추천 태그
                                </h3>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                    {result.recommended_tags && result.recommended_tags.length > 0 ? (
                                        result.recommended_tags.map((tag, idx) => (
                                            <span key={idx} style={{ background: '#f3e8ff', color: '#7e22ce', padding: '0.4rem 1rem', borderRadius: '999px', fontSize: '0.85rem' }}>
                                                #{tag}
                                            </span>
                                        ))
                                    ) : (
                                        <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>추천 가능한 태그가 없거나 API 응답에 없습니다.</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
            <WorkHistory menuKey="shopping-combine" />
        </div>
    );
}
