"use client";
import { useState, useEffect, useCallback } from "react";
import { getHistory, removeHistory, clearHistory } from "../utils/workHistory";

/**
 * 메뉴 하단 '이전 작업내역' 리스트.
 * props:
 *  - menuKey: 저장 키 (메뉴별 고유)
 *  - title: 헤더 문구
 *  - onRestore?: (entry) => void  — '다시 보기' 클릭 시 호출(있으면 버튼 노출)
 */
export default function WorkHistory({ menuKey, title = "📋 이전 작업내역", onRestore }) {
  const [list, setList] = useState([]);

  const reload = useCallback(() => setList(getHistory(menuKey)), [menuKey]);

  useEffect(() => {
    reload();
    const onUpdate = (e) => { if (!e?.detail?.menuKey || e.detail.menuKey === menuKey) reload(); };
    const onFocus = () => reload();
    window.addEventListener("mbam-history-updated", onUpdate);
    window.addEventListener("focus", onFocus);
    return () => {
      window.removeEventListener("mbam-history-updated", onUpdate);
      window.removeEventListener("focus", onFocus);
    };
  }, [menuKey, reload]);

  const fmt = (iso) => {
    try {
      const d = new Date(iso);
      const p = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
    } catch (e) { return ""; }
  };

  return (
    <div style={{ marginTop: "2rem", borderTop: "1px solid #e2e8f0", paddingTop: "1.2rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.8rem" }}>
        <h3 style={{ margin: 0, fontSize: "1rem", color: "#334155" }}>{title} <span style={{ color: "#94a3b8", fontWeight: "normal", fontSize: "0.85rem" }}>({list.length})</span></h3>
        {list.length > 0 && (
          <button onClick={() => { if (confirm("이 메뉴의 작업내역을 모두 지울까요?")) clearHistory(menuKey); }}
            style={{ fontSize: "0.8rem", color: "#94a3b8", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>전체 삭제</button>
        )}
      </div>

      {list.length === 0 ? (
        <div style={{ padding: "1.2rem", textAlign: "center", color: "#94a3b8", fontSize: "0.88rem", background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "8px" }}>
          아직 저장된 작업내역이 없습니다.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {list.map((it) => (
            <div key={it.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.8rem", padding: "0.7rem 1rem", background: "white", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{fmt(it.time)}</div>
                <div style={{ fontSize: "0.9rem", color: "#1e293b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={it.summary}>{it.summary || "(내용 없음)"}</div>
              </div>
              <div style={{ display: "flex", gap: "0.4rem", flexShrink: 0 }}>
                {onRestore && it.payload !== undefined && (
                  <button onClick={() => onRestore(it)} style={{ fontSize: "0.8rem", padding: "0.35rem 0.8rem", background: "#eff6ff", color: "#2563eb", border: "1px solid #bfdbfe", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>다시 보기</button>
                )}
                <button onClick={() => removeHistory(menuKey, it.id)} style={{ fontSize: "0.8rem", padding: "0.35rem 0.7rem", background: "#fff", color: "#ef4444", border: "1px solid #fecaca", borderRadius: "6px", cursor: "pointer", whiteSpace: "nowrap" }}>삭제</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
