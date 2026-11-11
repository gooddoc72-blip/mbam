"use client";
import { useState, useEffect, useCallback } from "react";
import { Monitor } from "lucide-react";

// 고객당 PC 2대 · 모든 PC 관리자 승인 — 승인 대기 패널 + 회원별 승인된 PC 목록 모달

const authHeaders = (json) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("mbam_token") : "";
  const h = { Authorization: `Bearer ${token}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
};

const fmt = (v) => {
  if (!v) return "-";
  // 서버는 UTC naive 로 준다 → Z 를 붙여 로컬(KST) 로 표시
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(v) ? v : v + "Z");
  return isNaN(d) ? "-" : d.toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "short" });
};

const btn = (bg, color) => ({
  padding: "0.35rem 0.75rem", fontSize: "0.8rem", fontWeight: 600, background: bg, color,
  border: "none", borderRadius: "6px", cursor: "pointer",
});

export function PcApprovalPanel({ onChanged }) {
  const [reqs, setReqs] = useState([]);
  const [busy, setBusy] = useState(null);
  const [replaceFor, setReplaceFor] = useState(null); // 2대 꽉 찬 요청 → 해제할 PC 선택

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/device-requests", { headers: authHeaders() });
      if (res.ok) setReqs(await res.json());
    } catch { /* 무시 — 다음 새로고침 때 재시도 */ }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const approve = async (r, replaceId) => {
    if (!replaceId && r.approved.length >= 2) { setReplaceFor(r); return; }
    setBusy(r.id);
    try {
      const res = await fetch(`/api/admin/device-requests/${r.id}/approve`, {
        method: "POST", headers: authHeaders(true),
        body: JSON.stringify({ replace_device_id: replaceId || null }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 409) { setReplaceFor(r); return; }
      alert(data.message || data.detail || (res.ok ? "승인했습니다." : "승인 실패"));
      setReplaceFor(null);
      load(); onChanged && onChanged();
    } finally { setBusy(null); }
  };

  const reject = async (r) => {
    if (!confirm(`${r.user_email} 의 PC(${r.pc_name || "-"}) 요청을 거절할까요?\n거절한 PC 는 'PC 등록 초기화' 전까지 다시 요청할 수 없습니다.`)) return;
    setBusy(r.id);
    try {
      const res = await fetch(`/api/admin/device-requests/${r.id}/reject`, { method: "POST", headers: authHeaders() });
      const data = await res.json().catch(() => ({}));
      alert(data.message || data.detail || "처리했습니다.");
      load();
    } finally { setBusy(null); }
  };

  return (
    <div style={{ background: "white", borderRadius: "12px", border: reqs.length ? "2px solid #f59e0b" : "1px solid #e2e8f0", overflow: "hidden", marginBottom: "2rem" }}>
      <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", gap: "10px", background: reqs.length ? "#fffbeb" : "#f8fafc" }}>
        <Monitor size={20} color={reqs.length ? "#d97706" : "#3b82f6"} />
        <h2 style={{ fontSize: "1.2rem", fontWeight: 600, color: "#1e293b", margin: 0 }}>PC 승인 대기</h2>
        <span style={{ background: reqs.length ? "#f59e0b" : "#e2e8f0", color: reqs.length ? "white" : "#64748b", borderRadius: "999px", padding: "0.1rem 0.6rem", fontSize: "0.85rem", fontWeight: 700 }}>{reqs.length}건</span>
        <span style={{ marginLeft: "auto", color: "#64748b", fontSize: "0.82rem" }}>고객당 PC 2대 · 에이전트 첫 로그인 시 자동 요청 · 30초마다 새로고침</span>
      </div>
      {reqs.length === 0 ? (
        <div style={{ padding: "1.25rem 1.5rem", color: "#94a3b8", fontSize: "0.9rem" }}>대기 중인 요청이 없습니다.</div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr style={{ background: "#f8fafc", color: "#64748b", textAlign: "left" }}>
              <th style={{ padding: "0.75rem 1.5rem" }}>회원</th>
              <th style={{ padding: "0.75rem 1rem" }}>PC 이름</th>
              <th style={{ padding: "0.75rem 1rem" }}>요청 시각</th>
              <th style={{ padding: "0.75rem 1rem" }}>현재 승인된 PC</th>
              <th style={{ padding: "0.75rem 1.5rem", textAlign: "right" }}>처리</th>
            </tr>
          </thead>
          <tbody>
            {reqs.map((r) => (
              <tr key={r.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                <td style={{ padding: "0.75rem 1.5rem", fontWeight: 600, color: "#1e293b" }}>{r.user_email || "-"}</td>
                <td style={{ padding: "0.75rem 1rem" }}>{r.pc_name || "-"} <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>…{r.hwid}</span></td>
                <td style={{ padding: "0.75rem 1rem", color: "#475569" }}>{fmt(r.requested_at)}</td>
                <td style={{ padding: "0.75rem 1rem", color: r.approved.length >= 2 ? "#dc2626" : "#475569" }}>
                  {r.approved.length} / 2 {r.approved.length > 0 && <span style={{ color: "#94a3b8" }}>({r.approved.map((d) => d.pc_name || "이름없음").join(", ")})</span>}
                </td>
                <td style={{ padding: "0.75rem 1.5rem", textAlign: "right", whiteSpace: "nowrap" }}>
                  <button disabled={busy === r.id} onClick={() => approve(r)} style={{ ...btn("#16a34a", "white"), marginRight: "0.4rem" }}>승인</button>
                  <button disabled={busy === r.id} onClick={() => reject(r)} style={btn("#fee2e2", "#b91c1c")}>거절</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {replaceFor && (
        <Modal title="PC 교체 승인" onClose={() => setReplaceFor(null)}>
          <p style={{ margin: "0 0 1rem", color: "#475569", fontSize: "0.9rem", lineHeight: 1.6 }}>
            <b>{replaceFor.user_email}</b> 은 이미 PC 2대가 승인되어 있습니다.<br />
            새 PC <b>{replaceFor.pc_name || "-"}</b> 를 승인하려면 해제할 기존 PC 를 고르세요.
          </p>
          {replaceFor.approved.map((d) => (
            <div key={d.id} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.6rem 0", borderTop: "1px solid #f1f5f9" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{d.pc_name || "이름없음"} <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>…{d.hwid}</span></div>
                <div style={{ color: "#94a3b8", fontSize: "0.8rem" }}>마지막 접속 {fmt(d.last_login)}</div>
              </div>
              <button disabled={busy === replaceFor.id} onClick={() => approve(replaceFor, d.id)} style={btn("#2563eb", "white")}>이 PC 해제하고 승인</button>
            </div>
          ))}
        </Modal>
      )}
    </div>
  );
}

export function UserDevicesModal({ user, onClose, onChanged }) {
  const [pcs, setPcs] = useState(null);

  const load = useCallback(async () => {
    const res = await fetch(`/api/admin/users/${user.id}/devices`, { headers: authHeaders() });
    setPcs(res.ok ? await res.json() : []);
  }, [user.id]);

  useEffect(() => { load(); }, [load]);

  const remove = async (d) => {
    if (!confirm(`${d.pc_name || "이 PC"} 의 승인을 해제할까요?\n그 PC 의 에이전트는 1분 안에 멈추고, 다시 쓰려면 승인 요청부터 다시 해야 합니다.`)) return;
    const res = await fetch(`/api/admin/users/${user.id}/devices/${d.id}`, { method: "DELETE", headers: authHeaders() });
    const data = await res.json().catch(() => ({}));
    alert(data.message || data.detail || "처리했습니다.");
    load(); onChanged && onChanged();
  };

  return (
    <Modal title={`승인된 PC — ${user.email}`} onClose={onClose}>
      {pcs === null ? <div style={{ color: "#94a3b8" }}>불러오는 중...</div> :
        pcs.length === 0 ? <div style={{ color: "#94a3b8" }}>승인된 PC 가 없습니다.</div> :
          pcs.map((d) => (
            <div key={d.id} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.6rem 0", borderTop: "1px solid #f1f5f9" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{d.pc_name || "이름없음"} <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>…{d.hwid}</span></div>
                <div style={{ color: "#94a3b8", fontSize: "0.8rem" }}>마지막 접속 {fmt(d.last_login)}</div>
              </div>
              <button onClick={() => remove(d)} style={btn("#fee2e2", "#b91c1c")}>해제</button>
            </div>
          ))}
    </Modal>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "16px" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "white", borderRadius: "12px", width: "100%", maxWidth: "520px", padding: "1.5rem", boxShadow: "0 20px 40px rgba(0,0,0,.2)" }}>
        <div style={{ display: "flex", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#1e293b" }}>{title}</h3>
          <button onClick={onClose} style={{ marginLeft: "auto", background: "none", border: "none", fontSize: "1.3rem", cursor: "pointer", color: "#64748b" }}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}
