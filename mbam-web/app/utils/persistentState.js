"use client";
import { useState, useEffect } from "react";

/**
 * 모듈 전역(메모리) 분석 상태 보관소.
 * - 사이드바로 다른 메뉴 이동 시 페이지 컴포넌트는 언마운트되지만, 이 모듈 스코프 값은
 *   살아있어서 돌아오면 상태가 복원된다. (진행 중이던 fetch 결과도 전역에 기록되므로 유지)
 * - 한계: 브라우저 새로고침(F5)으로 JS 모듈이 다시 로드되면 초기화된다. (메뉴 이동 한정)
 */
const _stores = {}; // key -> { value, listeners:Set }

function _ensure(key, initial) {
  if (!_stores[key]) _stores[key] = { value: initial, listeners: new Set() };
  return _stores[key];
}

/** 모듈 외부(핸들러 등)에서 직접 현재 값 읽기 */
export function getPersisted(key) {
  return _stores[key] ? _stores[key].value : undefined;
}

/** 모듈 외부에서 직접 값 설정 + 구독자 통지 (언마운트 상태에서도 안전) */
export function setPersisted(key, patch) {
  const store = _ensure(key, undefined);
  const next = typeof patch === "function" ? patch(store.value) : patch;
  store.value = next;
  store.listeners.forEach((l) => l(next));
  return next;
}

/**
 * useState 드롭인 대체. 같은 key를 쓰는 모든 마운트가 같은 전역 값을 공유한다.
 * setter는 값/업데이터 함수 모두 지원하며, 컴포넌트가 언마운트된 뒤 호출해도
 * 전역 값을 갱신하고 (이후 마운트된) 구독자에게 통지한다.
 */
export function usePersistentState(key, initial) {
  const store = _ensure(key, initial);
  const [value, setLocal] = useState(store.value);

  useEffect(() => {
    const listener = (v) => setLocal(v);
    store.listeners.add(listener);
    // (재)마운트 시 떠나 있는 동안 바뀐 값과 동기화
    setLocal(store.value);
    return () => store.listeners.delete(listener);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const setValue = (patch) => setPersisted(key, patch);
  return [value, setValue];
}
