"use client";
import { fetchWithAuth } from "../utils/api";
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  TrendingUp, MapPin, PenTool, Coffee, Search, Zap, ArrowUpRight, ArrowRight
} from 'lucide-react';
import { t, tone, Card, Button, Badge, PageHeader, SectionTitle, IconTile } from '../ui';

export default function SaaS_Dashboard() {
  const [activeTab, setActiveTab] = useState("history_blog");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [userInfo, setUserInfo] = useState(null);

  const tabs = [
    { id: "history_blog", label: "블로그 자동화" },
    { id: "history_cafe", label: "카페 자동화" },
    { id: "scraped_trends", label: "쇼핑 트렌드" },
    { id: "place_rank_history", label: "플레이스 진단" },
    { id: "history_analysis", label: "정밀 분석 리포트" },
  ];

  const fetchHistory = async (tableName) => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/history/${tableName}`);
      if (res.status === 401) return;
      const json = await res.json();
      setData(json.success ? json.data : []);
    } catch (err) {
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserInfo = async () => {
    try {
      const res = await fetchWithAuth('/api/auth/me');
      if (res.ok) setUserInfo(await res.json());
    } catch (err) { console.error(err); }
  };

  useEffect(() => {
    fetchUserInfo();
    fetchHistory(activeTab);
  }, [activeTab]);

  const quotaPct = userInfo && userInfo.max_usage > 0
    ? Math.min((userInfo.usage_count / userInfo.max_usage) * 100, 100)
    : 0;
  const isTrial = userInfo?.plan_type === "trial";
  const isAdmin = userInfo?.role === "admin";

  const MENU = [
    { title: "SEO 정밀 분석", desc: "검색 상위 노출 벤치마킹", icon: TrendingUp, path: "/seo-analysis" },
    { title: "플레이스 진단", desc: "네이버 플레이스 순위 추적", icon: MapPin, path: "/place-seo" },
    { title: "쇼핑 순위 검색", desc: "상품 순위 트렌드 분석", icon: Search, path: "/shopping/rank" },
    { title: "블로그 자동화", desc: "AI 원고 생성·다중 발행", icon: PenTool, path: "/blog-posting" },
    { title: "카페 자동화", desc: "카페 포스팅·댓글 소통", icon: Coffee, path: "/cafe-auto" },
    { title: "계정 관리", desc: "네이버 계정 저장·인증", icon: Zap, path: "/multi-task" },
  ];

  const th = { padding: "11px 20px", fontWeight: 600, fontSize: 12.5, color: t.textSub, textAlign: "left", whiteSpace: "nowrap" };
  const td = { padding: "13px 20px", fontSize: 13.5, color: t.text, verticalAlign: "middle" };

  // 블로그/카페 탭은 사용계정·포스팅 제목 컬럼을 추가로 보여준다.
  const isPostTab = activeTab === "history_blog" || activeTab === "history_cafe";
  const colCount = isPostTab ? 6 : 4;

  const rows = () => {
    if (!data.length) return (
      <tr><td colSpan={colCount} style={{ textAlign: "center", padding: "44px", color: t.textMuted, fontSize: 13.5 }}>최근 기록이 없습니다.</td></tr>
    );
    return data.slice(0, 10).map((row, i) => {
      const url = row.result_url || row.post_url || "";
      const ok = row.status?.includes('성공');
      const keywordCell = row.target_keyword || row.action_type || row.cafe_name || row.place_name || row.keyword || "-";
      return (
        <tr key={i} style={{ borderTop: `1px solid ${t.border}` }}
          onMouseOver={e => e.currentTarget.style.background = t.surfaceAlt}
          onMouseOut={e => e.currentTarget.style.background = "transparent"}>
          <td style={{ ...td, color: t.textSub, whiteSpace: "nowrap" }}>{row.created_at}</td>
          {isPostTab && <td style={{ ...td, fontWeight: 600 }}>{row.account_id || "-"}</td>}
          {isPostTab && <td style={td} title={row.post_title || ""}>{row.post_title || "-"}</td>}
          <td style={{ ...td, fontWeight: isPostTab ? 400 : 600 }}>{keywordCell}</td>
          <td style={td}><Badge t={ok ? 'success' : 'info'}>{row.status || '완료'}</Badge></td>
          <td style={td}>
            {url
              ? <a href={url} target="_blank" rel="noreferrer" style={{ color: t.accentInk, fontWeight: 600, fontSize: 13, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 3 }}>결과 보기 <ArrowUpRight size={13} /></a>
              : <span style={{ color: t.textMuted }}>-</span>}
          </td>
        </tr>
      );
    });
  };

  return (
    <div className="ds-page" style={{ padding: "32px", margin: "-2rem", minHeight: "calc(100vh + 0px)" }}>
      <div style={{ maxWidth: 1160, margin: "0 auto" }}>

        <PageHeader
          title="대시보드"
          subtitle="마케팅 자동화 현황을 한눈에 확인하세요."
          right={userInfo && (
            <Badge t={isAdmin ? 'info' : isTrial ? 'warn' : 'success'} style={{ fontSize: 12.5, padding: '5px 11px' }}>
              {isAdmin ? '최고 관리자' : isTrial ? '무료 체험판' : `유료 플랜 · ${userInfo.plan_type}`}
            </Badge>
          )}
        />

        {/* 쿼터 / 관리자 배너 */}
        {userInfo && !isAdmin && (
          <Card style={{ marginBottom: 28 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>이번 달 쿼터 사용량</span>
              <span style={{ fontSize: 13.5, color: t.textSub }}>
                <b style={{ color: t.text, fontSize: 16 }}>{userInfo.usage_count}</b> / {userInfo.max_usage} 회
              </span>
            </div>
            <div style={{ width: "100%", background: "#eef0f3", borderRadius: 999, height: 8, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 999, transition: "width .8s ease", width: `${quotaPct}%`,
                background: quotaPct >= 90 ? "#ef4444" : quotaPct >= 70 ? "#f59e0b" : t.accent,
              }} />
            </div>
            {isTrial && userInfo.trial_ends_at && (
              <p style={{ margin: "10px 0 0", fontSize: 12.5, color: t.textMuted, textAlign: "right" }}>
                무료체험 만료: {new Date(userInfo.trial_ends_at).toLocaleDateString()}
              </p>
            )}
          </Card>
        )}
        {userInfo && isAdmin && (
          <Card style={{ marginBottom: 28, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 3 }}>최고 관리자 계정</div>
              <div style={{ fontSize: 13, color: t.textSub }}>모든 기능을 무제한으로 사용할 수 있습니다.</div>
            </div>
            <Link href="/admin" style={{ textDecoration: "none" }}><Button variant="secondary" size="sm">관리자 콘솔 <ArrowRight size={14} /></Button></Link>
          </Card>
        )}

        {/* 빠른 실행 */}
        <SectionTitle style={{ marginTop: 8 }}>빠른 실행</SectionTitle>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14, marginBottom: 36 }}>
          {MENU.map((m, i) => (
            <Link href={m.path} key={i} style={{ textDecoration: "none", color: "inherit" }}>
              <Card hover padding={16} style={{ display: "flex", alignItems: "center", gap: 13, cursor: "pointer" }}>
                <IconTile icon={m.icon} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14.5, marginBottom: 2 }}>{m.title}</div>
                  <div style={{ fontSize: 12.5, color: t.textSub, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{m.desc}</div>
                </div>
              </Card>
            </Link>
          ))}
        </div>

        {/* 최근 작업 내역 */}
        <Card padding={0} style={{ overflow: "hidden" }}>
          <div style={{ padding: "18px 20px 14px" }}>
            <SectionTitle style={{ marginBottom: 12 }}>최근 작업 내역</SectionTitle>
            <div style={{ display: "flex", gap: 7, overflowX: "auto", paddingBottom: 2 }}>
              {tabs.map(tab => {
                const on = activeTab === tab.id;
                return (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                    style={{
                      padding: "6px 13px", borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: "pointer",
                      border: `1px solid ${on ? t.ink : t.border}`, whiteSpace: "nowrap",
                      background: on ? t.ink : "#fff", color: on ? "#fff" : t.textSub, transition: "all .15s",
                    }}>
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr style={{ background: t.surfaceAlt, borderTop: `1px solid ${t.border}` }}>
                <th style={th}>일시</th>
                {isPostTab && <th style={th}>사용계정</th>}
                {isPostTab && <th style={th}>포스팅 제목</th>}
                <th style={th}>{isPostTab ? "대상 키워드" : "대상 키워드 / 상호명"}</th>
                <th style={th}>상태</th><th style={th}>결과</th>
              </tr></thead>
              <tbody>
                {loading
                  ? <tr><td colSpan={colCount} style={{ textAlign: "center", padding: "44px", color: t.textMuted, fontSize: 13.5 }}>불러오는 중…</td></tr>
                  : rows()}
              </tbody>
            </table>
          </div>
        </Card>

      </div>
    </div>
  );
}
