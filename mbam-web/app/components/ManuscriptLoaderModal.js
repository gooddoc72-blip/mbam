import React, { useState, useEffect } from 'react';
import { X, Search, FileText } from 'lucide-react';

export default function ManuscriptLoaderModal({ isOpen, onClose, onSelect }) {
    const [manuscripts, setManuscripts] = useState([]);
    const [loading, setLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState("");

    useEffect(() => {
        if (isOpen) {
            fetchManuscripts();
        }
    }, [isOpen]);

    const fetchManuscripts = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/manuscripts');
            if (res.ok) {
                const data = await res.json();
                setManuscripts(data);
            }
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    if (!isOpen) return null;

    const filtered = manuscripts.filter(m => 
        m.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
        m.content.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.5)', zIndex: 9999,
            display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
            <div style={{
                background: 'white', width: '90%', maxWidth: '600px', borderRadius: '12px',
                boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)',
                display: 'flex', flexDirection: 'column', maxHeight: '80vh'
            }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.25rem 1.5rem', borderBottom: '1px solid #e2e8f0' }}>
                    <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '600', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={20} color="#3b82f6" /> 내 원고 불러오기
                    </h2>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b' }}>
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>
                    <div style={{ position: 'relative', marginBottom: '1rem' }}>
                        <Search size={18} color="#94a3b8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                        <input 
                            type="text" 
                            placeholder="제목 또는 내용 검색" 
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            style={{
                                width: '100%', padding: '0.75rem 1rem 0.75rem 2.5rem',
                                border: '1px solid #cbd5e1', borderRadius: '8px', fontSize: '0.95rem',
                                outline: 'none'
                            }}
                        />
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {loading ? (
                            <div style={{ textAlign: 'center', color: '#64748b', padding: '2rem 0' }}>불러오는 중...</div>
                        ) : filtered.length === 0 ? (
                            <div style={{ textAlign: 'center', color: '#64748b', padding: '2rem 0' }}>검색 결과가 없습니다.</div>
                        ) : (
                            filtered.map(m => (
                                <div 
                                    key={m.id} 
                                    onClick={() => { onSelect(m); onClose(); }}
                                    style={{
                                        border: '1px solid #e2e8f0', borderRadius: '8px', padding: '1rem',
                                        cursor: 'pointer', transition: 'all 0.2s', background: '#f8fafc'
                                    }}
                                    onMouseOver={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.background = '#eff6ff'; }}
                                    onMouseOut={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.background = '#f8fafc'; }}
                                >
                                    <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1rem', color: '#1e293b', fontWeight: '600' }}>{m.title}</h3>
                                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                        {m.content}
                                    </p>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
