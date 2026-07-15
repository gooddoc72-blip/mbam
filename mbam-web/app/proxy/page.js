"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";

export default function ProxyPage() {
  const [items, setItems] = useState([]);
  const [settings, setSettings] = useState({ ip_mode: "none", proxy_rotation: "hybrid" });
  const [lines, setLines] = useState("");
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState({});   // id -> "ip" | "error"

  const load = async () => {
    try {
      const res = await fetchWithAuth("/api/proxy/");
      const d = res.ok ? await res.json() : {};
      setItems(d.items || []);
      if (d.settings) setSettings(d.settings);
    } catch (e) { console.error(e); }
  };
  useEffect(() => { load(); }, []);

  const saveSettings = async (patch) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    try { await fetchWithAuth("/api/proxy/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }); }
    catch (e) { alert("설정 저장 실패: " + e.message); }
  };

  const addProxies = async () => {
    if (!lines.trim()) { alert("프록시를 한 줄에 하나씩 입력하세요."); return; }
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/proxy/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lines, label }) });
      const d = await res.json().catch(() => ({}));
      if (res.ok) {
        setLines(""); setLabel("");
        let msg = `${d.added || 0}개 등록되었습니다.`;
        if (d.invalid && d.invalid.length) msg += `\n\n형식 오류로 제외된 줄 ${d.invalid.length}개:\n` + d.invalid.slice(0, 5).join("\n");
        alert(msg);
        load();
      } else alert("등록 실패: " + (d.detail || res.status));
    } catch (e) { alert("오류: " + e.message); } finally { setLoading(false); }
  };

  const toggle = async (id) => { try { await fetchWithAuth(`/api/proxy/${id}/toggle`, { method: "POST" }); load(); } catch (e) {} };
  const remove = async (id) => { if (!confirm("이 프록시를 삭제할까요?")) return; try { await fetchWithAuth(`/api/proxy/${id}`, { method: "DELETE" }); load(); } catch (e) {} };
  const test = async (id) => {
    setTesting(t => ({ ...t, [id]: "…" }));
    try {
      const res = await fetchWithAuth(`/api/proxy/${id}/test`, { method: "POST" });
      const d = await res.json().catch(() => ({}));
      setTesting(t => ({ ...t, [id]: d.success ? `✅ ${d.ip}` : `❌ ${d.error || "실패"}` }));
    } catch (e) { setTesting(t => ({ ...t, [id]: "❌ " + e.message })); }
  };

  const th = { padding: "0.6rem 0.8rem", textAlign: "left", fontSize: "0.82rem", color: "#64748b", borderBottom: "1px solid #e2e8f0", whiteSpace: "nowrap" };
  const td = { padding: "0.6rem 0.8rem", fontSize: "0.88rem", borderBottom: "1px solid #f1f5f9" };
  const modeBtn = (val, cur, onClick, title, desc) => (
    <button onClick={onClick} style={{ flex: "1 1 150px", textAlign: "left", padding: "0.8rem 1rem", borderRadius: "10px", cursor: "pointer",
      border: cur === val ? "2px solid #2563eb" : "1px solid #cbd5e1", background: cur === val ? "#eff6ff" : "white" }}>
      <div style={{ fontWeight: "bold", color: cur === val ? "#1d4ed8" : "#334155" }}>{title}</div>
      <div style={{ fontSize: "0.78rem", color: "#64748b", marginTop: "0.2rem" }}>{desc}</div>
    </button>
  );

  const activeCount = items.filter(i => i.is_active).length;

  return (
    <div style={{ padding: "2rem", boxSizing: "border-box" }}>
      <h1 style={{ fontSize: "1.6rem", color: "#1e293b", marginBottom: "0.4rem" }}>🌐 프록시 IP 관리</h1>
      <p style={{ color: "#64748b", margin: "0 0 1.4rem", fontSize: "0.9rem", lineHeight: 1.6 }}>
        여러 프록시 IP를 등록해두면 자동화 실행 시 <b>자동으로 돌려가며(로테이션)</b> 사용합니다. USB 테더링 대신(또는 함께) 쓸 수 있습니다.
      </p>

      {/* IP 방식 */}
      <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "12px", padding: "1.2rem", marginBottom: "1.2rem" }}>
        <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.7rem" }}>IP 우회 방식</div>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
          {modeBtn("none", settings.ip_mode, () => saveSettings({ ip_mode: "none" }), "사용 안 함", "IP 그대로 진행")}
          {modeBtn("tethering", settings.ip_mode, () => saveSettings({ ip_mode: "tethering" }), "USB 테더링", "안드로이드 비행기모드 토글")}
          {modeBtn("proxy", settings.ip_mode, () => saveSettings({ ip_mode: "proxy" }), "프록시 풀", `등록된 프록시 자동 로테이션 (사용중 ${activeCount}개)`)}
        </div>

        {settings.ip_mode === "proxy" && (
          <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px dashed #e2e8f0" }}>
            <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.7rem", fontSize: "0.92rem" }}>로테이션 방식</div>
            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
              {modeBtn("hybrid", settings.proxy_rotation, () => saveSettings({ proxy_rotation: "hybrid" }), "하이브리드 (권장)", "발행·소통이웃=계정별 고정, 방문·부스트=회전")}
              {modeBtn("roundrobin", settings.proxy_rotation, () => saveSettings({ proxy_rotation: "roundrobin" }), "무조건 회전", "매 실행마다 다른 IP로 돌림")}
              {modeBtn("sticky", settings.proxy_rotation, () => saveSettings({ proxy_rotation: "sticky" }), "계정별 고정", "계정마다 같은 IP 유지(가장 안전)")}
            </div>
            {activeCount === 0 && <div style={{ marginTop: "0.7rem", color: "#b45309", fontSize: "0.85rem" }}>⚠️ 사용 중인 프록시가 없습니다. 아래에서 등록하세요.</div>}
          </div>
        )}
      </div>

      {/* 등록 폼 */}
      <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "12px", padding: "1.2rem", marginBottom: "1.4rem" }}>
        <div style={{ fontWeight: "bold", color: "#0f172a", marginBottom: "0.6rem" }}>프록시 등록 (한 줄에 하나씩)</div>
        <textarea value={lines} onChange={e => setLines(e.target.value)} rows={5}
          placeholder={"아이디:비번@호스트:포트  (인증형)\n호스트:포트           (비인증)\nsocks5://아이디:비번@호스트:포트\n예) user1:pw1@123.45.67.89:8080"}
          style={{ width: "100%", padding: "0.7rem", border: "1px solid #cbd5e1", borderRadius: "8px", boxSizing: "border-box", fontFamily: "monospace", fontSize: "0.85rem", resize: "vertical" }} />
        <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
          <input value={label} onChange={e => setLabel(e.target.value)} placeholder="메모(선택): 업체/지역 등" style={{ flex: "1 1 200px", padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box" }} />
          <button onClick={addProxies} disabled={loading} style={{ padding: "0.65rem 1.4rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: loading ? "wait" : "pointer" }}>＋ 등록</button>
        </div>
      </div>

      {/* 목록 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
        <h2 style={{ fontSize: "1.1rem", color: "#0f172a", margin: 0 }}>등록된 프록시 ({items.length})</h2>
        <button onClick={load} style={{ padding: "0.45rem 0.9rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem" }}>🔄 새로고침</button>
      </div>
      <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: "10px", overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "640px" }}>
          <thead><tr>
            <th style={th}>서버</th><th style={th}>인증</th><th style={th}>메모</th><th style={th}>상태</th><th style={th}>연결 테스트</th><th style={th}></th>
          </tr></thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td style={td} colSpan={6}><span style={{ color: "#94a3b8" }}>등록된 프록시가 없습니다. 위에서 추가하세요.</span></td></tr>
            ) : items.map(p => (
              <tr key={p.id} style={{ opacity: p.is_active ? 1 : 0.5 }}>
                <td style={{ ...td, fontFamily: "monospace", fontSize: "0.82rem" }}>{p.server}</td>
                <td style={td}>{p.username ? `${p.username} / ${p.password_set ? "••••" : "(무)"}` : <span style={{ color: "#94a3b8" }}>없음</span>}</td>
                <td style={{ ...td, color: "#64748b" }}>{p.label || "-"}</td>
                <td style={td}>{p.is_active ? <span style={{ color: "#16a34a", fontWeight: "bold" }}>사용</span> : <span style={{ color: "#94a3b8" }}>중지</span>}</td>
                <td style={{ ...td, fontSize: "0.82rem" }}>{testing[p.id] || "-"}</td>
                <td style={{ ...td, whiteSpace: "nowrap" }}>
                  <button onClick={() => test(p.id)} style={{ padding: "0.3rem 0.6rem", background: "#0ea5e9", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", marginRight: "0.35rem", fontSize: "0.82rem" }}>테스트</button>
                  <button onClick={() => toggle(p.id)} style={{ padding: "0.3rem 0.6rem", background: "white", color: "#334155", border: "1px solid #cbd5e1", borderRadius: "5px", cursor: "pointer", marginRight: "0.35rem", fontSize: "0.82rem" }}>{p.is_active ? "중지" : "사용"}</button>
                  <button onClick={() => remove(p.id)} style={{ padding: "0.3rem 0.6rem", background: "#ef4444", color: "white", border: "none", borderRadius: "5px", cursor: "pointer", fontSize: "0.82rem" }}>삭제</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
