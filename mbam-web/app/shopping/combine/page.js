'use client';
import { useState } from 'react';
import { Search, Loader2, Sparkles, Tags, AlertCircle } from 'lucide-react';

import { fetchWithAuth } from '../../utils/api';

export default function ShoppingCombine() {
    const [brandName, setBrandName] = useState('');
    const [seedKeyword, setSeedKeyword] = useState('');
    const [tokensInput, setTokensInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

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
                    tokens: tokensArray
                })
            });
            const data = await res.json();
            setResult(data);
        } catch (e) {
            alert('오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '2rem' }}>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 'bold', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={28} /> AI 상품명 조립 및 태그 배치
            </h1>
            <div style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
                <p style={{ color: '#64748b', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
                    네이버 검색 가중치 로직(전방 1~3어절 집중)과 어뷰징(50자 초과) 감점 로직을 분석하여,<br/>
                    준비된 단어 토큰들을 가장 최적화된 순서와 길이로 자동 조립해 줍니다. 남은 단어들은 추천 태그로 분산시킵니다.
                </p>
                
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

                <div style={{ marginBottom: '1.5rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '0.9rem' }}>클린 토큰 풀 (쉼표로 구분)</label>
                    <textarea 
                        value={tokensInput} 
                        onChange={e => setTokensInput(e.target.value)} 
                        placeholder="예: 가성비, 소형, 강력, 먼지, 거치대, 자취방, 화이트, 1인용..." 
                        style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0', minHeight: '100px', resize: 'vertical' }} 
                    />
                </div>

                <button onClick={handleAssemble} disabled={loading} style={{ width: '100%', padding: '1rem', background: '#8b5cf6', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                    {loading ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />} 최적화 상품명 조립하기
                </button>

                {result && (
                    <div style={{ marginTop: '2rem', padding: '1.5rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                        
                        {result.warning && (
                            <div style={{ background: '#fef3c7', color: '#b45309', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.95rem' }}>
                                <AlertCircle size={18} style={{ marginTop: '0.1rem' }} />
                                <div>
                                    <strong>주의사항: </strong>
                                    {result.warning}
                                </div>
                            </div>
                        )}

                        <div style={{ marginBottom: '2rem' }}>
                            <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.8rem' }}>🎯 AI 조립 완성 상품명 ({result.length}자)</h3>
                            <div style={{ background: '#f1f5f9', padding: '1.5rem', borderRadius: '8px', fontSize: '1.5rem', fontWeight: 'bold', color: '#0f172a', border: '2px dashed #cbd5e1' }}>
                                {result.optimized_title}
                            </div>
                            <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.5rem' }}>
                                * 50자 커트라인 제한이 적용되었습니다. 전방에 위치한 단어일수록 네이버 검색 가중치가 높게 산정됩니다.
                            </p>
                        </div>

                        <div>
                            <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                <Tags size={18} /> 잔여 키워드 추천 태그 (최대 10개)
                            </h3>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                {result.recommended_tags.length > 0 ? (
                                    result.recommended_tags.map((tag, idx) => (
                                        <span key={idx} style={{ background: '#f3e8ff', color: '#7e22ce', padding: '0.4rem 1rem', borderRadius: '999px', fontSize: '0.9rem', fontWeight: '500' }}>
                                            #{tag}
                                        </span>
                                    ))
                                ) : (
                                    <span style={{ color: '#94a3b8' }}>추천 가능한 남은 태그가 없습니다.</span>
                                )}
                            </div>
                        </div>

                        <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid #e2e8f0' }}>
                            <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#334155', marginBottom: '0.8rem' }}>💡 2026 옵션명 구조화 가이드</h3>
                            <p style={{ fontSize: '0.95rem', color: '#475569', marginBottom: '0.5rem' }}>
                                네이버 2026 알고리즘에서는 옵션명에 단독 텍스트("화이트", "1번")만 쓰면 인덱싱이 무시됩니다. 다음과 같은 [속성: 값] 템플릿을 활용하세요.
                            </p>
                            <code style={{ background: '#1e293b', color: '#a7f3d0', padding: '1rem', borderRadius: '8px', display: 'block', fontSize: '0.9rem' }}>
                                [색상: 화이트], [색상: 블랙]<br/>
                                [사이즈: M], [사이즈: L]<br/>
                                [재질: 스테인리스]
                            </code>
                        </div>

                    </div>
                )}
            </div>
        </div>
    );
}
