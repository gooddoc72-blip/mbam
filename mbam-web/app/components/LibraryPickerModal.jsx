"use client";
// 이미지 보관함에서 발행에 쓸 이미지를 고르는 공용 모달.
// 열리면 보관함 목록을 불러오고, 선택 → 스테이징(임시폴더 복사) 후 onUse(folder, count) 콜백.
// (카페 포스팅 / 블로그 예약 등 여러 화면에서 동일하게 재사용 — UI 통일)
import { useEffect, useState } from "react";
import { fetchWithAuth } from "../utils/api";

export default function LibraryPickerModal({ open, onClose, onUse }) {
  const [images, setImages] = useState([]);
  const [selected, setSelected] = useState(() => new Set());
  const [staging, setStaging] = useState(false);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const res = await fetchWithAuth("/api/settings/wash-library");
        if (res.ok) {
          const d = await res.json();
          const items = d.items || [];
          setImages(items);
          setSelected(new Set(items.map(i => i.filename)));  // 기본 전체 선택
        }
      } catch (e) {}
    })();
  }, [open]);

  if (!open) return null;

  const toggle = (fn) => setSelected(prev => { const n = new Set(prev); n.has(fn) ? n.delete(fn) : n.add(fn); return n; });

  const use = async () => {
    const picked = Array.from(selected);
    if (picked.length === 0) { alert("사용할 이미지를 1장 이상 선택하세요."); return; }
    setStaging(true);
    try {
      const res = await fetchWithAuth("/api/settings/wash-library/stage", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filenames: picked }),
      });
      const d = await res.json();
      if (res.ok && d.success && d.folder) {
        onUse && onUse(d.folder, d.count);
      } else alert("이미지 지정에 실패했습니다.");
    } catch (e) { alert("오류: " + e.message); }
    finally { setStaging(false); }
  };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "white", borderRadius: "12px", padding: "1.5rem", width: "640px", maxWidth: "92vw", maxHeight: "82vh", display: "flex", flexDirection: "column", boxShadow: "0 10px 40px rgba(0,0,0,0.25)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.15rem", color: "#1e293b" }}>🗂️ 보관함에서 이미지 선택 <span style={{ fontSize: "0.85rem", color: "#94a3b8", fontWeight: "normal" }}>(선택 {selected.size}/{images.length})</span></h3>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#94a3b8" }}>✕</button>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.8rem" }}>
          <button onClick={() => setSelected(new Set(images.map(i => i.filename)))} style={{ fontSize: "0.82rem", padding: "0.35rem 0.8rem", background: "#eff6ff", color: "#2563eb", border: "1px solid #bfdbfe", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>전체 선택</button>
          <button onClick={() => setSelected(new Set())} style={{ fontSize: "0.82rem", padding: "0.35rem 0.8rem", background: "#f8fafc", color: "#64748b", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontWeight: "bold" }}>전체 해제</button>
        </div>
        <div style={{ flex: 1, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "0.8rem" }}>
          {images.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8", fontSize: "0.9rem" }}>보관함이 비어 있습니다. 이미지 세탁소에서 세탁 후 “💾 보관함에 저장”을 먼저 해주세요.</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))", gap: "0.6rem" }}>
              {images.map((img) => {
                const sel = selected.has(img.filename);
                return (
                  <div key={img.filename} onClick={() => toggle(img.filename)} style={{ position: "relative", border: sel ? "3px solid #7c3aed" : "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden", cursor: "pointer", boxSizing: "border-box" }}>
                    <img src={img.base64_data} alt={img.filename} style={{ width: "100%", height: "90px", objectFit: "cover", display: "block", opacity: sel ? 1 : 0.55 }} />
                    {sel && <span style={{ position: "absolute", top: "4px", right: "4px", width: "20px", height: "20px", borderRadius: "50%", background: "#7c3aed", color: "white", fontSize: "0.75rem", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>✓</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <button onClick={use} disabled={staging || selected.size === 0} style={{ marginTop: "1rem", padding: "0.9rem", background: (staging || selected.size === 0) ? "#cbd5e1" : "#7c3aed", color: "white", border: "none", borderRadius: "8px", fontWeight: "bold", fontSize: "1rem", cursor: (staging || selected.size === 0) ? "not-allowed" : "pointer" }}>
          {staging ? "지정 중..." : `선택한 ${selected.size}장 발행에 사용`}
        </button>
      </div>
    </div>
  );
}
