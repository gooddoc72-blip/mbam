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
      const res = await fetchWithAuth("/api/proxy");
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
      const res = await fetchWithAuth("/api/proxy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lines, label }) });
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

  const removeAll = async () => {
    if (items.length === 0) { alert("등록된 프록시가 없습니다."); return; }
    if (!confirm(`등록된 프록시 ${items.length}개를 모두 삭제합니다.\n되돌릴 수 없습니다. 계속할까요?`)) return;
    try {
      const res = await fetchWithAuth("/api/proxy/all", { method: "DELETE" });
      const d = await res.json().catch(() => ({}));
      alert(res.ok ? (d.message || "삭제되었습니다.") : "삭제 실패: " + (d.detail || res.status));
      load();
    } catch (e) { alert("오류: " + e.message); }
  };

  // USB 테더링 — 폰 연결 여부와 실제 IP 교체를 화면에서 확인할 수 있게 한다.
  const [tether, setTether] = useState(null);
  const [tetherBusy, setTetherBusy] = useState("");
  const checkTethering = async () => {
    setTetherBusy("check"); setTether(null);
    try {
      const res = await fetchWithAuth("/api/proxy/tethering/status");
      setTether(await res.json());
    } catch (e) { setTether({ connected: false, message: "확인 실패: " + e.message }); }
    setTetherBusy("");
  };
  const rotateTethering = async () => {
    setTetherBusy("rotate");
    try {
      const res = await fetchWithAuth("/api/proxy/tethering/rotate", { method: "POST" });
      const d = await res.json().catch(() => ({}));
      alert(res.ok ? d.message : "실패: " + (d.detail || res.status));
    } catch (e) { alert("오류: " + e.message); }
    setTetherBusy("");
  };

  const toggle = async (id) => { try { await fetchWithAuth(`/api/proxy/${id}/toggle`, { method: "POST" }); load(); } catch (e) {} };
  const remove = async (id) => { if (!confirm("이 프록시를 삭제할까요?")) return; try { await fetchWithAuth(`/api/proxy/${id}`, { method: "DELETE" }); load(); } catch (e) {} };
  const test = async (id) => {
    setTesting(t => ({ ...t, [id]: "…" }));
    try {
      const res = await fetchWithAuth(`/api/proxy/${id}/test`, { method: "POST" });
      const d = await res.json().catch(() => ({}));
      // 국가까지 보여준다 — 해외 IP 면 네이버가 이상 접속으로 보기 쉬우므로 눈에 띄게 표시.
      // 한국 IP 라도 '데이터센터'면 네이버가 사람 아닌 접속으로 본다 — 종류까지 표시한다.
      let label;
      if (!d.success) label = `❌ ${d.error || "실패"}`;
      else {
        const risky = (d.country_code && d.country_code !== "KR") || d.hosting || d.proxy_flag;
        const kind = d.hosting ? "데이터센터" : d.mobile ? "모바일" : d.country_code === "KR" ? "가정용" : "";
        label = `${risky ? "⚠️" : "✅"} ${d.ip}` +
                (d.country ? ` · ${d.country}` : "") +
                (kind ? ` · ${kind}` : "") +
                (d.isp ? ` · ${d.isp}` : "");
      }
      setTesting(t => ({ ...t, [id]: label }));
      if (d.warning) alert(d.warning);
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

      {/* USB 테더링 — 연결 상태와 실제 IP 교체를 여기서 확인한다 */}
      <div style={{ background: "white", border: "1px solid #cbd5e1", borderRadius: "12px", padding: "1.2rem", marginBottom: "1.2rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "0.6rem" }}>
          <div style={{ fontWeight: "bold", color: "#0f172a" }}>📶 USB 테더링 (안드로이드 폰으로 IP 바꾸기)</div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={checkTethering} disabled={!!tetherBusy}
              style={{ padding: "0.45rem 0.9rem", background: tetherBusy === "check" ? "#94a3b8" : "#3b82f6", color: "white", border: "none", borderRadius: "6px", cursor: tetherBusy ? "wait" : "pointer", fontSize: "0.85rem", fontWeight: "bold" }}>
              {tetherBusy === "check" ? "확인 중..." : "폰 연결 확인"}
            </button>
            <button onClick={rotateTethering} disabled={!!tetherBusy || !(tether && tether.connected)}
              style={{ padding: "0.45rem 0.9rem", background: "white", color: (tether && tether.connected) ? "#0f172a" : "#cbd5e1", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: (tether && tether.connected && !tetherBusy) ? "pointer" : "not-allowed", fontSize: "0.85rem" }}>
              {tetherBusy === "rotate" ? "교체 중..." : "IP 교체 시험"}
            </button>
          </div>
        </div>
        <p style={{ margin: "0 0 0.6rem", fontSize: "0.85rem", color: "#64748b", lineHeight: 1.7 }}>
          안드로이드 폰을 USB 로 연결하고 <b>비행기모드를 껐다 켜서</b> 통신사 IP 를 새로 받는 방식입니다.
          프록시 없이도 계정마다 다른 IP 를 쓸 수 있고, <b>통신사 실회선이라 데이터센터 IP 보다 안전합니다.</b>
        </p>
        {tether && (
          <div style={{
            padding: "0.8rem 1rem", borderRadius: "8px", fontSize: "0.88rem", lineHeight: 1.7,
            background: tether.connected ? "#f0fdf4" : "#fef2f2",
            color: tether.connected ? "#166534" : "#991b1b",
            border: `1px solid ${tether.connected ? "#bbf7d0" : "#fecaca"}`,
          }}>
            {tether.connected ? "✅ " : "⚠️ "}{tether.message}
          </div>
        )}
        <div style={{ marginTop: "0.6rem", fontSize: "0.8rem", color: "#94a3b8", lineHeight: 1.7 }}>
          준비물 — ① 안드로이드 폰 ② USB 케이블 ③ 폰의 [개발자 옵션 &gt; USB 디버깅] 켜기 ④ PC 에 adb 설치<br />
          사용하려면 위 <b>IP 우회 방식</b>에서 [USB 테더링]을 고르거나, 카페 작업 화면의 테더링 항목을 켜세요.
        </div>
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
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={load} style={{ padding: "0.45rem 0.9rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem" }}>🔄 새로고침</button>
          <button onClick={removeAll} disabled={items.length === 0}
            style={{ padding: "0.45rem 0.9rem", background: "white", color: items.length ? "#ef4444" : "#cbd5e1", border: `1px solid ${items.length ? "#fecaca" : "#e2e8f0"}`, borderRadius: "6px", cursor: items.length ? "pointer" : "not-allowed", fontSize: "0.85rem" }}>
            🗑 전체 삭제
          </button>
        </div>
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
