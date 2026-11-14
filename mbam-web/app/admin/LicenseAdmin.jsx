"use client";
import { useState, useEffect, useCallback } from "react";
import { Shield } from "lucide-react";

// 설치형(카페·블로그·크롤러) 라이선스 관리 — 관리자_승인도구.exe 의 웹 버전.
// 브라우저는 라이선스 서버 토큰을 모른다: /api/admin/license/* 가 서버에서 중계한다.

const hdr = (json) => {
  const h = { Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("mbam_token") : ""}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
};
const api = async (path, body) => {
  const res = await fetch(`/api/admin/license${path}`, body === undefined
    ? { headers: hdr() }
    : { method: "POST", headers: hdr(true), body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `오류 (${res.status})`);
  return data;
};
const fmt = (v) => {
  if (!v) return "-";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(v) ? v : v + "Z");
  return isNaN(d) ? "-" : d.toLocaleDateString("ko-KR");
};
const PRODUCT = { "": "크롤러", cafe: "카페", blog: "블로그 기본", blog_pro: "블로그 프로" };
const STATUS = {
  approved: { t: "승인", bg: "#dcfce7", c: "#166534" },
  pending: { t: "대기", bg: "#fef3c7", c: "#92400e" },
  blocked: { t: "차단", bg: "#fee2e2", c: "#991b1b" },
};
const btn = (bg, color) => ({ padding: "0.35rem 0.7rem", fontSize: "0.8rem", fontWeight: 600, background: bg, color, border: "none", borderRadius: "6px", cursor: "pointer", minHeight: "32px" });
const th = { padding: "0.7rem 1rem", fontWeight: 600, whiteSpace: "nowrap" };
const td = { padding: "0.7rem 1rem", whiteSpace: "nowrap" };

export default function LicenseAdmin() {
  const [st, setSt] = useState(null);
  const [devices, setDevices] = useState([]);
  const [codes, setCodes] = useState([]);
  const [tab, setTab] = useState("devices");
  const [filter, setFilter] = useState("pending");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState({ count: 1, valid_days: 30, memo: "" });
  const [issued, setIssued] = useState([]);

  const load = useCallback(async () => {
    try {
      const s = await api("/status");
      setSt(s);
      if (!s.ok) return;
      const [d, c] = await Promise.all([api("/devices"), api("/codes")]);
      setDevices(Array.isArray(d) ? d : []);
      setCodes(Array.isArray(c) ? c : []);
    } catch (e) { setSt({ ok: false, message: e.message }); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (fn, msg) => {
    setBusy(true);
    try { const r = await fn(); if (msg) alert(typeof msg === "function" ? msg(r) : msg); await load(); }
    catch (e) { alert(e.message); }
    finally { setBusy(false); }
  };
  const daysLabel = (n) => (Number(n) === 0 ? "무기한" : `${n}일`);

  const approve = (d) => run(() => api("/device/status", { hwid: d.hwid, product: d.product, status: "approved", days: d.product ? Number(days) : null }),
    d.product ? `승인했습니다 (${daysLabel(days)}).` : "승인했습니다.");
  const block = (d) => confirm(`${d.name || d.hwid} 기기를 차단할까요?`) &&
    run(() => api("/device/status", { hwid: d.hwid, product: d.product, status: "blocked" }), "차단했습니다.");
  const extend = (d) => confirm(`${d.name || d.hwid} 기간을 ${daysLabel(days)} 연장할까요?`) &&
    run(() => api("/device/extend", { hwid: d.hwid, product: d.product, days: Number(days) }), (r) => `만료일: ${fmt(r.expires_at) === "-" ? "무기한" : fmt(r.expires_at)}`);

  const counts = devices.reduce((a, d) => { a[d.status] = (a[d.status] || 0) + 1; return a; }, {});
  const shown = devices.filter((d) => filter === "all" || d.status === filter);

  return (
    <div style={{ background: "white", borderRadius: "12px", border: counts.pending ? "2px solid #f59e0b" : "1px solid #e2e8f0", overflow: "hidden", marginBottom: "2rem" }}>
      <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid #e2e8f0", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", background: "#f8fafc" }}>
        <Shield size={20} color="#3b82f6" />
        <h2 style={{ fontSize: "1.2rem", fontWeight: 600, color: "#1e293b", margin: 0 }}>설치형 라이선스 (카페·블로그·크롤러)</h2>
        {st && (st.ok
          ? <span style={{ fontSize: "0.8rem", color: "#166534", background: "#dcfce7", padding: "0.15rem 0.6rem", borderRadius: "999px" }}>라이선스 서버 연결됨</span>
          : <span style={{ fontSize: "0.8rem", color: "#991b1b", background: "#fee2e2", padding: "0.15rem 0.6rem", borderRadius: "999px" }}>연결 안 됨</span>)}
        <div style={{ marginLeft: "auto", display: "flex", gap: "6px" }}>
          <button onClick={() => setTab("devices")} style={btn(tab === "devices" ? "#1e293b" : "#e2e8f0", tab === "devices" ? "white" : "#334155")}>기기 승인{counts.pending ? ` (${counts.pending})` : ""}</button>
          <button onClick={() => setTab("codes")} style={btn(tab === "codes" ? "#1e293b" : "#e2e8f0", tab === "codes" ? "white" : "#334155")}>인증코드</button>
          <button onClick={load} style={btn("#eff6ff", "#1d4ed8")}>새로고침</button>
        </div>
      </div>

      {st && !st.ok && (
        <div style={{ padding: "1rem 1.5rem", color: "#991b1b", fontSize: "0.9rem" }}>{st.message || "라이선스 서버에 연결할 수 없습니다."}</div>
      )}

      {st?.ok && tab === "devices" && (
        <>
          <div style={{ padding: "0.9rem 1.5rem", display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap", borderBottom: "1px solid #f1f5f9", fontSize: "0.88rem" }}>
            {[["pending", "대기"], ["approved", "승인"], ["blocked", "차단"], ["all", "전체"]].map(([k, t]) => (
              <button key={k} onClick={() => setFilter(k)} style={btn(filter === k ? "#3b82f6" : "#f1f5f9", filter === k ? "white" : "#334155")}>
                {t} {k === "all" ? devices.length : counts[k] || 0}
              </button>
            ))}
            <label style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "6px", color: "#475569" }}>
              승인·연장 기간
              <select value={days} onChange={(e) => setDays(e.target.value)} style={{ padding: "0.35rem", borderRadius: "6px", border: "1px solid #cbd5e1" }}>
                <option value={30}>30일</option><option value={90}>90일</option><option value={180}>180일</option><option value={365}>365일</option><option value={0}>무기한</option>
              </select>
            </label>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
              <thead><tr style={{ background: "#f8fafc", color: "#64748b", textAlign: "left" }}>
                <th style={th}>제품</th><th style={th}>신청자 / PC</th><th style={th}>기기</th><th style={th}>상태</th><th style={th}>신청일</th><th style={th}>마지막 접속</th><th style={th}>만료</th><th style={{ ...th, textAlign: "right" }}>처리</th>
              </tr></thead>
              <tbody>
                {shown.length === 0 && <tr><td colSpan={8} style={{ ...td, color: "#94a3b8" }}>해당하는 기기가 없습니다.</td></tr>}
                {shown.map((d) => {
                  const s = STATUS[d.status] || { t: d.status, bg: "#e2e8f0", c: "#334155" };
                  const exp = d.product ? (d.expires_at ? `${fmt(d.expires_at)} (${d.days_left}일)` : "무기한") : "-";
                  return (
                    <tr key={`${d.product}:${d.hwid}`} style={{ borderTop: "1px solid #f1f5f9" }}>
                      <td style={td}>{PRODUCT[d.product] ?? d.product}</td>
                      <td style={{ ...td, fontWeight: 600, color: "#1e293b", whiteSpace: "normal" }}>{d.name || "-"}</td>
                      <td style={{ ...td, color: "#94a3b8", fontFamily: "monospace" }}>…{(d.hwid || "").slice(-6)}</td>
                      <td style={td}><span style={{ background: s.bg, color: s.c, padding: "0.15rem 0.55rem", borderRadius: "999px", fontWeight: 600, fontSize: "0.78rem" }}>{s.t}</span></td>
                      <td style={td}>{fmt(d.created_at)}</td>
                      <td style={td}>{fmt(d.last_seen)}</td>
                      <td style={{ ...td, color: d.days_left !== null && d.days_left !== undefined && d.days_left <= 7 ? "#dc2626" : "#475569" }}>{exp}</td>
                      <td style={{ ...td, textAlign: "right" }}>
                        <div style={{ display: "inline-flex", gap: "4px" }}>
                          {d.status !== "approved" && <button disabled={busy} onClick={() => approve(d)} style={btn("#16a34a", "white")}>승인</button>}
                          {d.status === "approved" && d.product && <button disabled={busy} onClick={() => extend(d)} style={btn("#eff6ff", "#1d4ed8")}>연장</button>}
                          {d.status !== "blocked" && <button disabled={busy} onClick={() => block(d)} style={btn("#fee2e2", "#b91c1c")}>차단</button>}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {st?.ok && tab === "codes" && (
        <div style={{ padding: "1rem 1.5rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end", flexWrap: "wrap", marginBottom: "1rem", fontSize: "0.88rem" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>발급 개수
              <input type="number" min={1} max={100} value={issue.count} onChange={(e) => setIssue({ ...issue, count: e.target.value })} style={{ width: "80px", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} /></label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>사용 기간
              <select value={issue.valid_days} onChange={(e) => setIssue({ ...issue, valid_days: e.target.value })} style={{ padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "6px" }}>
                <option value={30}>30일</option><option value={90}>90일</option><option value={365}>365일</option><option value={0}>무기한</option>
              </select></label>
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", flex: "1 1 200px" }}>고객 이름/메모
              <input value={issue.memo} onChange={(e) => setIssue({ ...issue, memo: e.target.value })} placeholder="예: 홍길동 / OO마케팅" style={{ padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "6px" }} /></label>
            <button disabled={busy} onClick={() => run(async () => { const r = await api("/codes/issue", { count: Number(issue.count), valid_days: Number(issue.valid_days), memo: issue.memo }); setIssued(r.issued || []); })} style={{ ...btn("#2563eb", "white"), padding: "0.55rem 1rem" }}>발급</button>
          </div>
          {issued.length > 0 && (
            <div style={{ background: "#eff6ff", borderRadius: "8px", padding: "0.75rem 1rem", marginBottom: "1rem", fontSize: "0.88rem" }}>
              <b>새로 발급된 코드</b> <button onClick={() => navigator.clipboard?.writeText(issued.join("\n"))} style={{ ...btn("white", "#1d4ed8"), marginLeft: "8px" }}>전체 복사</button>
              <div style={{ fontFamily: "monospace", marginTop: "6px", whiteSpace: "pre-wrap" }}>{issued.join("\n")}</div>
            </div>
          )}
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.86rem" }}>
              <thead><tr style={{ background: "#f8fafc", color: "#64748b", textAlign: "left" }}>
                <th style={th}>코드</th><th style={th}>메모</th><th style={th}>상태</th><th style={th}>사용 PC</th><th style={th}>만료</th><th style={{ ...th, textAlign: "right" }}>처리</th>
              </tr></thead>
              <tbody>
                {codes.length === 0 && <tr><td colSpan={6} style={{ ...td, color: "#94a3b8" }}>발급된 코드가 없습니다.</td></tr>}
                {codes.map((c) => (
                  <tr key={c.code} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ ...td, fontFamily: "monospace" }}>{c.code}</td>
                    <td style={{ ...td, whiteSpace: "normal" }}>{c.memo || "-"}</td>
                    <td style={td}>{c.is_active === false ? <span style={{ color: "#b91c1c", fontWeight: 600 }}>정지</span> : (c.expires_at && new Date(c.expires_at + (/[zZ]$/.test(c.expires_at) ? "" : "Z")) < new Date()) ? <span style={{ color: "#92400e" }}>만료</span> : <span style={{ color: "#166534" }}>사용 가능</span>}</td>
                    <td style={td}>{c.machine_name || (c.hwid ? `…${String(c.hwid).slice(-6)}` : "미사용")}</td>
                    <td style={td}>{c.expires_at ? fmt(c.expires_at) : "무기한"}</td>
                    <td style={{ ...td, textAlign: "right" }}>
                      <div style={{ display: "inline-flex", gap: "4px" }}>
                        <button onClick={() => navigator.clipboard?.writeText(c.code)} style={btn("#f1f5f9", "#334155")}>복사</button>
                        {c.is_active === false
                          ? <button disabled={busy} onClick={() => run(() => api("/codes/unrevoke", { code: c.code }), "다시 사용 가능하게 했습니다.")} style={btn("#dcfce7", "#166534")}>다시 사용</button>
                          : <button disabled={busy} onClick={() => confirm(`${c.code} 를 정지할까요?`) && run(() => api("/codes/revoke", { code: c.code }), "정지했습니다.")} style={btn("#fee2e2", "#b91c1c")}>정지</button>}
                        {c.hwid && <button disabled={busy} onClick={() => confirm("PC 이전을 허용할까요? (기존 PC 연결 해제)") && run(() => api("/codes/reset", { code: c.code }), "PC 연결을 해제했습니다.")} style={btn("#eff6ff", "#1d4ed8")}>PC 교체 허용</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
