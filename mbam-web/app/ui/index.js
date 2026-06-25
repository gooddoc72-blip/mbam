'use client';
import React from 'react';

/* ============================================================
   리디자인 디자인 시스템 — "절제된 프로 SaaS"
   뉴트럴 그레이 + 단일 액센트, 플랫 솔리드, 1px 보더, 옅은 그림자.
   다른 페이지에 영향 없는 자기완결형 컴포넌트.
   ============================================================ */

export const t = {
  bg: '#f6f7f9',
  surface: '#ffffff',
  surfaceAlt: '#fafbfc',
  border: '#e6e8eb',
  borderStrong: '#d6d9de',
  text: '#16181d',
  textSub: '#697077',
  textMuted: '#9aa1ac',
  accent: '#3b82f6',
  accentInk: '#2563eb',
  ink: '#18181b',          // 거의 검정 (primary 버튼)
  radius: 12,
  radiusSm: 8,
  shadow: '0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.03)',
  shadowHover: '0 6px 16px rgba(16,24,40,0.08)',
};

export const tone = {
  success: { bg: '#effdf3', fg: '#15803d' },
  info: { bg: '#eff5ff', fg: '#1d4ed8' },
  warn: { bg: '#fff8eb', fg: '#b45309' },
  danger: { bg: '#fef2f2', fg: '#b91c1c' },
  neutral: { bg: '#f3f4f6', fg: '#52555c' },
};

export function Card({ children, style = {}, padding = 20, hover = false, ...rest }) {
  const [h, setH] = React.useState(false);
  return (
    <div
      onMouseEnter={() => hover && setH(true)}
      onMouseLeave={() => hover && setH(false)}
      style={{
        background: t.surface,
        border: `1px solid ${t.border}`,
        borderRadius: t.radius,
        boxShadow: hover && h ? t.shadowHover : t.shadow,
        padding,
        transition: 'box-shadow .18s ease, transform .18s ease',
        transform: hover && h ? 'translateY(-2px)' : 'none',
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Button({ children, variant = 'primary', size = 'md', style = {}, ...rest }) {
  const pads = { sm: '6px 12px', md: '9px 16px', lg: '12px 20px' };
  const fonts = { sm: 13, md: 14, lg: 15 };
  const variants = {
    primary: { background: t.ink, color: '#fff', border: `1px solid ${t.ink}` },
    secondary: { background: '#fff', color: t.text, border: `1px solid ${t.borderStrong}` },
    accent: { background: t.accent, color: '#fff', border: `1px solid ${t.accent}` },
    ghost: { background: 'transparent', color: t.textSub, border: '1px solid transparent' },
  };
  return (
    <button
      style={{
        ...variants[variant],
        padding: pads[size],
        fontSize: fonts[size],
        fontWeight: 600,
        borderRadius: t.radiusSm,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        lineHeight: 1.2,
        transition: 'opacity .15s ease',
        ...style,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.88')}
      onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Badge({ children, t: toneKey = 'neutral', style = {} }) {
  const c = tone[toneKey] || tone.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 999, fontSize: 12, fontWeight: 600,
      background: c.bg, color: c.fg, lineHeight: 1.4, ...style,
    }}>
      {children}
    </span>
  );
}

export function PageHeader({ title, subtitle, right }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', margin: '0 0 6px' }}>{title}</h1>
        {subtitle && <p style={{ color: t.textSub, margin: 0, fontSize: 14 }}>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function SectionTitle({ children, style = {} }) {
  return <h2 style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.01em', margin: '0 0 14px', ...style }}>{children}</h2>;
}

/* 메뉴/통계 타일의 아이콘 컨테이너 — 무지개 그라데이션 대신 중립 톤 */
export function IconTile({ icon: Icon, accent = false, size = 40 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: 10, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: accent ? '#eef4ff' : '#f3f4f6',
      color: accent ? t.accentInk : '#3f434b',
      border: `1px solid ${accent ? '#dbe7ff' : '#eceef1'}`,
    }}>
      <Icon size={Math.round(size * 0.5)} strokeWidth={1.9} />
    </div>
  );
}
