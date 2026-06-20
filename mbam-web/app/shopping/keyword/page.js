'use client';
import { useState } from 'react';
import { Search, Loader2, Key, Tag } from 'lucide-react';

import { fetchWithAuth } from '../../utils/api';

export default function ShoppingKeyword() {
    const [seedKeyword, setSeedKeyword] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    const handleAnalyze = async () => {
        if (!seedKeyword) return alert('시드 키워드를 입력해주세요.');
        
        setLoading(true);
        setResult(null);
        try {
            const res = await fetchWithAuth(`/api/shopping/keyword/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed_keyword: seedKeyword })
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
                <Key size={28} /> 쇼핑 키워드 분석 및 정제 모듈
            </h1>
            <div style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
                <p style={{ color: '#64748b', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
                    시드 키워드를 입력하면, 연관 키워드를 수집한 후 카테고리가 일치하는 것만 필터링하고,<br/>
                    형태소 분석(Mecab/Kiwi)을 통해 스팸 단어와 특수기호를 완벽히 제거한 '클린 토큰 풀(Pool)'을 생성합니다.
                </p>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                    <input value={seedKeyword} onChange={e => setSeedKeyword(e.target.value)} placeholder="시드 키워드 (예: 무선 청소기)" style={{ flex: 1, padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
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
                                <h4 style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#334155', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                    <Tag size={16} /> 클린 토큰 풀 (총 {(result.valid_tokens_pool || []).length}개)
                                </h4>
                                <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1rem' }}>
                                    네이버 상위 10위 상품들의 핵심 키워드와 조회수 기반 롱테일 키워드가 병합된 토큰 풀입니다.
                                </p>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                    {(result.valid_tokens_pool || []).map((token, idx) => (
                                        <span key={idx} style={{ background: '#e0f2fe', color: '#0284c7', padding: '0.3rem 0.8rem', borderRadius: '999px', fontSize: '0.9rem', fontWeight: '500' }}>
                                            {token}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                        
                        {/* SEO Title Assembler Section */}
                        <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'white', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '1rem' }}>🤖 네이버 거리점수 반영 SEO 상품명 조립기</h3>
                            <p style={{ fontSize: '0.9rem', color: '#64748b', marginBottom: '1.5rem' }}>
                                메인 키워드와의 <strong>형태소 거리(Proximity)</strong>를 최소화하는 네이버 알고리즘 최적화 방식으로 상품명을 자동 조립합니다.<br/>
                                <span style={{color: '#0284c7'}}>[롱테일 키워드 2개] + [브랜드명] + [메인(시드)키워드] + [상위노출 핵심 수식어들]</span> 순서로 결합됩니다.
                            </p>
                            
                            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
                                <input id="brandInput" placeholder="브랜드명 (선택사항)" style={{ flex: 1, padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                                <button 
                                    onClick={async () => {
                                        const brand = document.getElementById('brandInput').value;
                                        const res = await fetchWithAuth('/api/shopping/keyword/assemble', {
                                            method: 'POST',
                                            headers: {'Content-Type': 'application/json'},
                                            body: JSON.stringify({
                                                seed_keyword: result.seed_keyword,
                                                brand_name: brand,
                                                tokens: result.valid_tokens_pool
                                            })
                                        });
                                        const data = await res.json();
                                        if(data.optimized_title) {
                                            document.getElementById('assembledResult').innerText = data.optimized_title;
                                            document.getElementById('assembledLength').innerText = `총 ${data.length}자 (네이버 권장 50자 이내)`;
                                            document.getElementById('assembledLength').style.color = data.length > 50 ? 'red' : '#10b981';
                                        }
                                    }}
                                    style={{ padding: '0.75rem 2rem', background: '#10b981', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}>
                                    최적화 상품명 생성
                                </button>
                            </div>
                            
                            <div style={{ padding: '1.5rem', background: '#f1f5f9', borderRadius: '8px', textAlign: 'center' }}>
                                <div id="assembledResult" style={{ fontSize: '1.3rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '0.5rem' }}>버튼을 눌러 상품명을 생성해보세요!</div>
                                <div id="assembledLength" style={{ fontSize: '0.9rem', color: '#64748b' }}></div>
                            </div>
                        </div>
                        
                    </div>
                )}
            </div>
        </div>
    );
}
