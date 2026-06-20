"use client";
import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, UploadCloud, FileText, CheckCircle, Search, Edit3, ScrollText } from 'lucide-react';

export default function ManuscriptPage() {
    const [manuscripts, setManuscripts] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [form, setForm] = useState({ title: '', content: '' });
    const fileInputRef = useRef(null);

    useEffect(() => {
        fetchManuscripts();
    }, []);

    const fetchManuscripts = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/manuscripts');
            if (res.ok) {
                const data = await res.json();
                setManuscripts(data);
            }
        } catch (e) {
            console.error("Failed to fetch manuscripts:", e);
        }
        setLoading(false);
    };

    const handleSave = async () => {
        if (!form.title || !form.content) {
            alert("제목과 내용을 모두 입력해주세요.");
            return;
        }
        try {
            const res = await fetch('http://127.0.0.1:8000/api/manuscripts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form)
            });
            if (res.ok) {
                setForm({ title: '', content: '' });
                fetchManuscripts();
                alert("원고가 성공적으로 저장되었습니다.");
            }
        } catch (e) {
            alert("저장 실패: " + e.message);
        }
    };

    const handleDelete = async (id) => {
        if (!confirm("정말 이 원고를 삭제하시겠습니까?")) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/manuscripts/${id}`, { method: 'DELETE' });
            if (res.ok) fetchManuscripts();
        } catch (e) {
            console.error(e);
        }
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append("file", file);
        
        setUploading(true);
        try {
            const res = await fetch('http://127.0.0.1:8000/api/manuscripts/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                setForm({
                    ...form,
                    title: file.name.replace(/\.[^/.]+$/, ""),
                    content: data.content
                });
            } else {
                alert(data.detail || "업로드 실패");
            }
        } catch (e) {
            alert("업로드 중 오류 발생");
        }
        setUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    return (
        <div style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}>
            <h1 style={{ fontSize: "2rem", fontWeight: "bold", marginBottom: "2rem", color: "#1e293b", display: "flex", alignItems: "center", gap: "10px" }}>
                <FileText size={32} color="#3b82f6" /> 내 원고 관리
            </h1>

            <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
                {/* 작성 폼 영역 */}
                <div style={{ flex: "1 1 500px", background: "white", padding: "2rem", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" }}>
                    <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "1.5rem", color: "#334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        새 원고 작성
                        <div>
                            <input 
                                type="file" 
                                ref={fileInputRef} 
                                style={{ display: 'none' }} 
                                accept=".txt,.docx"
                                onChange={handleFileUpload}
                            />
                            <button 
                                onClick={() => fileInputRef.current?.click()}
                                disabled={uploading}
                                style={{
                                    display: "flex", alignItems: "center", gap: "6px", padding: "0.5rem 1rem",
                                    background: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1",
                                    borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem", fontWeight: "500",
                                    transition: "all 0.2s"
                                }}
                                onMouseOver={(e) => { e.currentTarget.style.background = "#e2e8f0"; }}
                                onMouseOut={(e) => { e.currentTarget.style.background = "#f1f5f9"; }}
                            >
                                <UploadCloud size={18} /> {uploading ? "업로드 중..." : "파일 업로드 (.txt, .docx)"}
                            </button>
                        </div>
                    </h2>
                    
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                        <div>
                            <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "500", color: "#64748b", marginBottom: "0.5rem" }}>제목</label>
                            <input 
                                type="text" 
                                value={form.title}
                                onChange={(e) => setForm({...form, title: e.target.value})}
                                placeholder="원고 제목을 입력하세요"
                                style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "1rem", outline: "none", transition: "border-color 0.2s" }}
                                onFocus={(e) => e.target.style.borderColor = "#3b82f6"}
                                onBlur={(e) => e.target.style.borderColor = "#cbd5e1"}
                            />
                        </div>
                        <div>
                            <label style={{ display: "block", fontSize: "0.9rem", fontWeight: "500", color: "#64748b", marginBottom: "0.5rem" }}>본문 내용</label>
                            <textarea 
                                value={form.content}
                                onChange={(e) => setForm({...form, content: e.target.value})}
                                placeholder="원고 내용을 입력하거나 파일을 업로드하세요."
                                style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "1rem", minHeight: "300px", resize: "vertical", outline: "none", transition: "border-color 0.2s" }}
                                onFocus={(e) => e.target.style.borderColor = "#3b82f6"}
                                onBlur={(e) => e.target.style.borderColor = "#cbd5e1"}
                            />
                        </div>
                        <button 
                            onClick={handleSave}
                            style={{
                                display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
                                width: "100%", padding: "0.875rem", background: "#3b82f6", color: "white",
                                border: "none", borderRadius: "8px", fontSize: "1rem", fontWeight: "600",
                                cursor: "pointer", transition: "all 0.2s"
                            }}
                            onMouseOver={(e) => { e.currentTarget.style.background = "#2563eb"; }}
                            onMouseOut={(e) => { e.currentTarget.style.background = "#3b82f6"; }}
                        >
                            <CheckCircle size={20} /> DB에 저장하기
                        </button>
                    </div>
                </div>

                {/* 리스트 영역 */}
                <div style={{ flex: "1 1 400px", background: "white", padding: "2rem", borderRadius: "12px", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" }}>
                    <h2 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "1.5rem", color: "#334155", display: "flex", alignItems: "center", gap: "8px" }}>
                        <ScrollText size={24} color="#64748b" /> 저장된 원고 목록
                    </h2>
                    
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem", maxHeight: "550px", overflowY: "auto", paddingRight: "0.5rem" }}>
                        {loading ? (
                            <div style={{ textAlign: "center", color: "#94a3b8", padding: "2rem 0" }}>로딩 중...</div>
                        ) : manuscripts.length === 0 ? (
                            <div style={{ textAlign: "center", color: "#94a3b8", padding: "2rem 0" }}>저장된 원고가 없습니다.</div>
                        ) : (
                            manuscripts.map(m => (
                                <div key={m.id} style={{ padding: "1rem", border: "1px solid #e2e8f0", borderRadius: "8px", transition: "all 0.2s" }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                                        <h3 style={{ fontSize: "1rem", fontWeight: "600", color: "#1e293b", margin: 0 }}>{m.title}</h3>
                                        <div style={{ display: "flex", gap: "0.5rem" }}>
                                            <button 
                                                onClick={() => setForm({ title: m.title, content: m.content })}
                                                style={{ background: "none", border: "none", color: "#3b82f6", cursor: "pointer", padding: "0.25rem" }}
                                                title="불러오기"
                                            >
                                                <Edit3 size={18} />
                                            </button>
                                            <button 
                                                onClick={() => handleDelete(m.id)}
                                                style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", padding: "0.25rem" }}
                                                title="삭제"
                                            >
                                                <Trash2 size={18} />
                                            </button>
                                        </div>
                                    </div>
                                    <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "0 0 0.5rem 0", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                                        {m.content}
                                    </p>
                                    <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                                        {new Date(m.created_at).toLocaleString()}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
