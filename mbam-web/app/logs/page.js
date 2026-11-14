"use client";
// [로그] 화면 — 두 가지를 보여준다.
//   1) 작업 기록: 각 메뉴가 작업을 마칠 때 이 PC 브라우저에 남긴 기록(utils/workHistory)을 한데 모아 최신순으로.
//   2) 앱 로그: 백엔드 로그 파일(mbam_sys.log)의 마지막 N줄. 비밀번호·키 같은 값은 서버에서 가려서 온다.
//      설치형(카페·블로그 전용판)은 누구나, 웹 버전은 관리자만 볼 수 있다.
import { useEffect, useState } from "react";
import { fetchWithAuth } from "../utils/api";

const HISTORY_PREFIX = "mbam_history:";

// 메뉴 키 → 화면 이름 (모르는 키는 그대로 보여준다)
const MENU_LABELS = {
  "cafe-auto": "카페 포스팅",
  "image-wash": "이미지 세탁소",
  "cafe-analysis": "형태소 분석",
  "blog-posting": "블로그 발행",
  "blog-check": "블로그 진단",
  "blogspot": "구글 블로그스팟",
  "communication": "소통 & 이웃",
  "content-collect": "글감수집",
  "manuscript": "원고관리",
  "seo-analysis": "SEO 분석",
  "place-news": "플레이스 소식",
  "place-seo": "플레이스 진단",
  "shopping-rank": "쇼핑 순위",
  "shopping-keyword": "쇼핑 키워드",
  "shopping-combine": "쇼핑 키워드 조합",
  "coupang-rank": "쿠팡 순위",
};

function readAllHistory() {
  const out = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith(HISTORY_PREFIX)) continue;
      const menuKey = k.slice(HISTORY_PREFIX.length);
      let list = [];
      try { list = JSON.parse(localStorage.getItem(k) || "[]"); } catch (e) { list = []; }
      (Array.isArray(list) ? list : []).forEach(r => out.push({ ...r, menuKey }));
    }
  } catch (e) {}
  out.sort((a, b) => String(b.time || "").localeCompare(String(a.time || "")));
  return out;
}

function fmtTime(iso) {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso || "";
    return d.toLocaleString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch (e) { return iso || ""; }
}

function lineColor(line) {
  if (/\|\s*(ERROR|CRITICAL)\s*\|/.test(line) || line.includes("❌")) return "#f87171";
  if (/\|\s*WARNING\s*\|/.test(line) || line.includes("⚠️")) return "#fbbf24";
  if (line.includes("✅")) return "#34d399";
  return "#cbd5e1";
}

const card = { background: "white", padding: "1.5rem", border: "1px solid #cbd5e1", borderRadius: "8px" };
const btn = { padding: "0.45rem 0.9rem", background: "#f1f5f9", color: "#334155", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem", whiteSpace: "nowrap" };

export default function LogsPage() {
  const [history, setHistory] = useState([]);
  const [lines, setLines] = useState([]);
  const [lineCount, setLineCount] = useState(200);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState("");
  const [loadedAt, setLoadedAt] = useState(null);

  const loadHistory = () => setHistory(readAllHistory());

  const loadLog = async (n = lineCount) => {
    setLogLoading(true); setLogError("");
    try {
      const res = await fetchWithAuth(`/api/history/system-log/tail?lines=${n}`);
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setLines([]);
        setLogError(typeof d.detail === "string" ? d.detail : `앱 로그를 불러오지 못했습니다. (HTTP ${res.status})`);
        return;
      }
      setLines(d.lines || []);
      setLoadedAt(new Date());
    } catch (e) {
      setLogError("서버에 연결하지 못했습니다. 프로그램(백엔드)이 켜져 있는지 확인해주세요.");
    } finally {
      setLogLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
    loadLog();
    const onUpd = () => loadHistory();
    window.addEventListener("mbam-history-updated", onUpd);
    return () => window.removeEventListener("mbam-history-updated", onUpd);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shown = onlyProblems
    ? lines.filter(l => /\|\s*(WARNING|ERROR|CRITICAL)\s*\|/.test(l) || l.includes("❌") || l.includes("⚠️"))
    : lines;

  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "1.5rem", boxSizing: "border-box" }}>
      <div>
        <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0 }}>로그</h1>
        <p style={{ margin: "0.4rem 0 0", color: "#64748b", fontSize: "0.9rem" }}>최근 작업 기록과 프로그램 동작 기록을 확인합니다. 문제가 생기면 이 화면의 내용을 함께 알려주시면 원인 파악에 도움이 됩니다.</p>
      </div>

      {/* 1. 작업 기록 */}
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.8rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>최근 작업 기록 ({history.length})</h2>
          <button onClick={loadHistory} style={btn}>새로고침</button>
        </div>
        <p style={{ margin: "0 0 0.8rem", fontSize: "0.82rem", color: "#94a3b8" }}>각 메뉴에서 마친 작업이 이 PC에 저장된 기록입니다. (메뉴마다 최근 30건)</p>
        {history.length === 0 ? (
          <div style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8", border: "2px dashed #cbd5e1", borderRadius: "8px", fontSize: "0.9rem" }}>
            아직 작업 기록이 없습니다.
          </div>
        ) : (
          <div style={{ overflowX: "auto", maxHeight: "360px", overflowY: "auto" }}>
            <table style={{ width: "100%", minWidth: "520px", borderCollapse: "collapse", fontSize: "0.88rem" }}>
              <thead>
                <tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1", position: "sticky", top: 0 }}>
                  <th style={{ padding: "0.5rem", textAlign: "left", width: "160px", whiteSpace: "nowrap" }}>시간</th>
                  <th style={{ padding: "0.5rem", textAlign: "left", width: "140px", whiteSpace: "nowrap" }}>메뉴</th>
                  <th style={{ padding: "0.5rem", textAlign: "left" }}>내용</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 200).map(r => (
                  <tr key={r.menuKey + ":" + r.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                    <td style={{ padding: "0.5rem", whiteSpace: "nowrap", color: "#475569" }}>{fmtTime(r.time)}</td>
                    <td style={{ padding: "0.5rem", whiteSpace: "nowrap", fontWeight: "bold", color: "#2563eb" }}>{MENU_LABELS[r.menuKey] || r.menuKey}</td>
                    <td style={{ padding: "0.5rem", overflowWrap: "anywhere" }}>{r.summary || "(내용 없음)"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 2. 앱 로그 */}
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.8rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>프로그램 동작 기록</h2>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontSize: "0.85rem", color: "#475569", cursor: "pointer" }}>
              <input type="checkbox" checked={onlyProblems} onChange={e => setOnlyProblems(e.target.checked)} />
              경고·오류만
            </label>
            <select value={lineCount} onChange={e => { const n = Number(e.target.value); setLineCount(n); loadLog(n); }}
              style={{ padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.85rem" }}>
              {[100, 200, 500, 1000].map(n => <option key={n} value={n}>최근 {n}줄</option>)}
            </select>
            <button onClick={() => loadLog()} disabled={logLoading} style={{ ...btn, cursor: logLoading ? "wait" : "pointer" }}>
              {logLoading ? "불러오는 중..." : "새로고침"}
            </button>
          </div>
        </div>
        <p style={{ margin: "0 0 0.8rem", fontSize: "0.82rem", color: "#94a3b8" }}>
          비밀번호·API 키 같은 값은 **** 로 가려서 보여줍니다.{loadedAt ? ` · ${loadedAt.toLocaleTimeString("ko-KR")} 기준` : ""}
        </p>
        {logError ? (
          <div style={{ padding: "1rem", background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", borderRadius: "6px", fontSize: "0.9rem" }}>{logError}</div>
        ) : (
          <div style={{ background: "#1e293b", borderRadius: "8px", padding: "1rem", maxHeight: "520px", overflow: "auto", fontFamily: "monospace", fontSize: "0.8rem", lineHeight: 1.6 }}>
            {shown.length === 0 ? (
              <div style={{ color: "#94a3b8" }}>{logLoading ? "불러오는 중..." : (onlyProblems ? "경고·오류 기록이 없습니다." : "기록이 없습니다.")}</div>
            ) : (
              shown.slice().reverse().map((l, i) => (
                <div key={i} style={{ color: lineColor(l), whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{l}</div>
              ))
            )}
          </div>
        )}
        <p style={{ margin: "0.5rem 0 0", fontSize: "0.78rem", color: "#94a3b8" }}>* 최신 기록이 맨 위에 있습니다.</p>
      </div>
    </div>
  );
}
