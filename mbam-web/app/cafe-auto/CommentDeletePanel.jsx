"use client";
// 댓글 삭제 — 원글 URL 입력 → 그 글에 댓글 단 계정 체크 → 삭제 실행.
// 삭제는 체크한 계정으로 로그인해 그 글에서 '내 댓글'을 찾아 지운다(작성 이력 없이도 동작).
// 작성 이력은 '어느 계정이 댓글을 달았는지' 자동 체크하는 데만 쓴다.
import { useState } from "react";
import { fetchWithAuth } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";

export default function CommentDeletePanel({ s }) {
  const { accounts, loading, setLoading, setStatusLogs, setTaskStatus, setTaskId, setTaskKind, targetMultiProxy } = s;
  const [delUrls, setDelUrls] = usePersistentState("cafe-auto:delUrls", "");
  const [delAccounts, setDelAccounts] = useState([]);   // NaverAccount.id
  const [history, setHistory] = useState(null);         // 이 글들에 대한 작성 이력
  const [finding, setFinding] = useState(false);

  const urlList = () => delUrls.split("\n").map(u => u.trim()).filter(u => u);

  const toggle = (id) =>
    setDelAccounts(prev => prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]);

  // 작성 이력에서 이 글에 댓글을 단 계정을 찾아 자동 체크한다.
  const handleFindAccounts = async () => {
    const urls = urlList();
    if (urls.length === 0) return alert("댓글을 달았던 원글 URL을 입력하세요.");
    setFinding(true);
    try {
      const res = await fetchWithAuth(`/api/cafe-nurture/comment-history?url=${encodeURIComponent(urls.join("\n"))}`);
      const d = await res.json().catch(() => ({}));
      if (!res.ok) return alert("이력 조회 실패: " + (d.detail || `HTTP ${res.status}`));
      const items = d.items || [];
      setHistory(items);
      const naverIds = new Set(items.filter(it => it.status === "posted").map(it => it.account_id));
      const ids = accounts.filter(a => naverIds.has(a.naver_id)).map(a => a.id);
      setDelAccounts(ids);
      if (ids.length === 0) {
        alert("이 글에 대한 댓글 작성 기록이 없습니다.\n(기록 기능 이전에 단 댓글일 수 있습니다 — 댓글을 단 계정을 직접 체크해서 삭제하세요)");
      }
    } catch (e) { alert("서버 오류 (백엔드 서버가 켜져 있는지 확인해주세요)"); }
    finally { setFinding(false); }
  };

  const handleDelete = async () => {
    const urls = urlList();
    if (urls.length === 0) return alert("댓글을 달았던 원글 URL을 입력하세요.");
    if (delAccounts.length === 0) return alert("삭제할 계정을 체크하세요.");
    const names = accounts.filter(a => delAccounts.includes(a.id)).map(a => a.naver_id);
    if (!window.confirm(
      `글 ${urls.length}개에서 아래 계정이 단 댓글을 모두 삭제합니다.\n\n${names.join(", ")}\n\n` +
      `삭제한 댓글은 되돌릴 수 없습니다. 계속할까요?`)) return;

    setLoading(true); setStatusLogs([]); setTaskStatus("running"); setTaskId(null); setTaskKind("comment");
    try {
      const res = await fetchWithAuth("/api/cafe-nurture/delete-comments", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls, account_ids: delAccounts, use_proxy: targetMultiProxy }),
      });
      const d = await res.json().catch(() => ({}));
      if (res.ok && d.success) {
        setTaskId(d.task_id);
        setHistory(null);
      } else {
        alert(d.detail || "삭제 시작에 실패했습니다."); setLoading(false); setTaskStatus("failed");
      }
    } catch (e) { alert("서버 오류"); setLoading(false); setTaskStatus("failed"); }
  };

  // 계정별 이력 요약 (자동 체크 근거를 보여준다)
  const countBy = {};
  (history || []).forEach(it => {
    const k = it.account_id;
    countBy[k] = countBy[k] || { posted: 0, deleted: 0 };
    countBy[k][it.status === "deleted" ? "deleted" : "posted"] += 1;
  });

  return (
    <div style={{ background: "white", padding: "1.5rem", border: "1px solid #fecaca" }}>
      <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#b91c1c" }}>🗑 작성한 댓글 삭제</h2>
      <p style={{ margin: "0 0 0.8rem", fontSize: "0.85rem", color: "#64748b" }}>
        댓글을 달았던 <b>원글 링크</b>를 넣고 <b>삭제할 계정을 체크</b>하세요. 체크한 계정으로 로그인해 그 글에서
        <b> 그 계정이 쓴 댓글만</b> 지웁니다. (다른 사람 댓글은 건드리지 않습니다)
      </p>

      <textarea placeholder="댓글을 달았던 원글 URL을 한 줄에 하나씩 입력하세요." value={delUrls}
        onChange={e => setDelUrls(e.target.value)}
        style={{ width: "100%", height: "80px", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "0.8rem 0 0.5rem", gap: "0.5rem", flexWrap: "wrap" }}>
        <span style={{ fontWeight: "bold", fontSize: "0.9rem" }}>삭제할 계정 ({delAccounts.length}개 체크)</span>
        <div style={{ display: "flex", gap: "0.4rem" }}>
          <button onClick={handleFindAccounts} disabled={finding || loading}
            style={{ padding: "0.4rem 0.8rem", background: "#0ea5e9", color: "white", border: "none", borderRadius: "4px", cursor: finding ? "wait" : "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>
            {finding ? "찾는 중..." : "🔎 댓글 단 계정 자동 체크"}
          </button>
          <button onClick={() => setDelAccounts(accounts.map(a => a.id))} disabled={loading}
            style={{ padding: "0.4rem 0.8rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "4px", cursor: "pointer", fontSize: "0.85rem" }}>전체</button>
          <button onClick={() => setDelAccounts([])} disabled={loading}
            style={{ padding: "0.4rem 0.8rem", background: "white", border: "1px solid #cbd5e1", borderRadius: "4px", cursor: "pointer", fontSize: "0.85rem" }}>해제</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {accounts.map(acc => {
          const on = delAccounts.includes(acc.id);
          const c = countBy[acc.naver_id];
          return (
            <label key={acc.id} style={{ padding: "0.45rem 0.9rem", border: "1px solid #cbd5e1", borderRadius: "20px", cursor: "pointer", background: on ? "#dc2626" : "white", color: on ? "white" : "black", fontSize: "0.9rem" }}>
              <input type="checkbox" style={{ display: "none" }} checked={on} onChange={() => toggle(acc.id)} />
              {acc.naver_id}
              {c && <span style={{ marginLeft: "0.35rem", fontSize: "0.75rem", opacity: 0.85 }}>
                (댓글 {c.posted}{c.deleted ? ` · 삭제됨 ${c.deleted}` : ""})
              </span>}
            </label>
          );
        })}
        {accounts.length === 0 && <span style={{ color: "#94a3b8" }}>등록된 계정이 없습니다.</span>}
      </div>

      {history && history.length > 0 && (
        <details style={{ marginTop: "0.8rem", fontSize: "0.82rem", color: "#475569" }}>
          <summary style={{ cursor: "pointer" }}>이 글에 기록된 댓글 {history.length}건 보기</summary>
          <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.2rem" }}>
            {history.map(it => (
              <li key={it.id} style={{ marginBottom: "0.25rem", textDecoration: it.status === "deleted" ? "line-through" : "none", color: it.status === "deleted" ? "#94a3b8" : "inherit" }}>
                <b>{it.account_id}</b>: {it.comment_text}
                <span style={{ color: "#94a3b8" }}> · {(it.created_at || "").slice(0, 16).replace("T", " ")}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <button onClick={handleDelete} disabled={loading}
        style={{ width: "100%", marginTop: "1rem", padding: "0.8rem", background: loading ? "#94a3b8" : "#dc2626", color: "white", fontWeight: "bold", fontSize: "1rem", border: "none", cursor: loading ? "wait" : "pointer" }}>
        {loading ? "작업 중..." : "🗑 체크한 계정의 댓글 삭제"}
      </button>
      <div style={{ marginTop: "0.4rem", fontSize: "0.78rem", color: "#94a3b8" }}>
        진행 상황은 아래 작업 로그에 표시됩니다. 계정마다 브라우저가 열려 처리되며, 댓글 작업과 같은 프록시 설정을 따릅니다.
      </div>
    </div>
  );
}
