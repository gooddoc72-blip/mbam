"use client";
/**
 * 메뉴별 작업내역(localStorage) 저장소.
 * - 각 메뉴에서 분석/작업이 완료될 때 addHistory(menuKey, {summary, payload})로 누적.
 * - 메뉴 하단 <WorkHistory menuKey=.../>가 이 목록을 표시(다시 보기/삭제).
 * - 브라우저(그 PC)에 저장되며 새로고침해도 유지. 메뉴당 최근 MAX건만 보관.
 */
const PREFIX = "mbam_history:";
const MAX = 30;

function _key(menuKey) {
  return PREFIX + menuKey;
}

export function getHistory(menuKey) {
  try {
    return JSON.parse(localStorage.getItem(_key(menuKey)) || "[]");
  } catch (e) {
    return [];
  }
}

export function addHistory(menuKey, record) {
  try {
    const list = getHistory(menuKey);
    const entry = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      time: new Date().toISOString(),
      ...record, // { summary, payload? }
    };
    list.unshift(entry);
    localStorage.setItem(_key(menuKey), JSON.stringify(list.slice(0, MAX)));
    // 같은 페이지의 리스트가 즉시 갱신되도록 알림
    try { window.dispatchEvent(new CustomEvent("mbam-history-updated", { detail: { menuKey } })); } catch (e) {}
    return entry;
  } catch (e) {
    return null;
  }
}

export function removeHistory(menuKey, id) {
  try {
    const list = getHistory(menuKey).filter((x) => x.id !== id);
    localStorage.setItem(_key(menuKey), JSON.stringify(list));
    try { window.dispatchEvent(new CustomEvent("mbam-history-updated", { detail: { menuKey } })); } catch (e) {}
    return list;
  } catch (e) {
    return [];
  }
}

export function clearHistory(menuKey) {
  try {
    localStorage.removeItem(_key(menuKey));
    try { window.dispatchEvent(new CustomEvent("mbam-history-updated", { detail: { menuKey } })); } catch (e) {}
  } catch (e) {}
}
