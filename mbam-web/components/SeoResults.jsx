import React, { useState } from 'react';

const GRADE_COLORS = {
  S: { bg: '#fef3c7', fg: '#92400e' },  // gold
  A: { bg: '#d1fae5', fg: '#065f46' },  // green
  B: { bg: '#dbeafe', fg: '#1e40af' },  // blue
  C: { bg: '#fed7aa', fg: '#9a3412' },  // orange
  D: { bg: '#e2e8f0', fg: '#475569' },  // gray
};

function GradeBadge({ grade, score, title }) {
  const c = GRADE_COLORS[grade] || GRADE_COLORS.D;
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex', alignItems: 'baseline', gap: '4px',
        padding: '3px 10px', borderRadius: '14px',
        backgroundColor: c.bg, color: c.fg,
        fontSize: '0.75rem', fontWeight: 'bold', letterSpacing: '0.02em',
      }}
    >
      <span style={{ fontSize: '0.9rem' }}>{grade}</span>
      <span style={{ opacity: 0.8 }}>{Number(score).toFixed(0)}</span>
    </span>
  );
}

export default function SeoResults({ data }) {
  const [expandedRows, setExpandedRows] = useState({});
  const [selectedBlogs, setSelectedBlogs] = useState([]);

  if (!data) return null;

  const { keyword, metrics = [], top_keywords = [], formula, smart_blocks } = data;

  const cafePopularBlocks = smart_blocks?.blocks?.filter(b => b.block_title?.includes("카페")) || [];
  
  const toggleRow = (idx) => {
    setExpandedRows(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleCheckboxChange = (e, m) => {
    e.stopPropagation();
    if (e.target.checked) {
      if (selectedBlogs.length >= 3) {
        alert("최대 3개까지만 선택할 수 있습니다.");
        return;
      }
      setSelectedBlogs([...selectedBlogs, m]);
    } else {
      setSelectedBlogs(selectedBlogs.filter(b => b.url !== m.url));
    }
  };

  const handleAutoWrite = (type) => {
    if (selectedBlogs.length === 0) {
      alert("글쓰기에 참고할 블로그/카페 글을 먼저 선택해 주세요.");
      return;
    }
    
    const refData = {
      keyword: keyword,
      formula: formula,
      references: selectedBlogs
    };
    localStorage.setItem('autoWriteRefData', JSON.stringify(refData));
    
    if (type === 'blog') {
      window.location.href = '/blog-auto';
    } else {
      window.location.href = '/cafe-auto';
    }
  };

  // 계산
  const avgChar = metrics.length ? Math.floor(metrics.reduce((acc, cur) => acc + (cur.char_count || 0), 0) / metrics.length) : 0;
  const avgImg = metrics.length ? Math.floor(metrics.reduce((acc, cur) => acc + (cur.img_count || 0), 0) / metrics.length) : 0;

  return (
    <div style={{ animation: "fadeIn 0.5s" }}>
      {/* Competitor Data Summary */}
      <div className="glass-card mb-4">
        <h2 className="mb-2">📊 경쟁 데이터 요약</h2>
        <div className="grid-3">
          <div>
            <div className="text-sm">분석 포스팅</div>
            <div style={{ fontSize: "2rem", fontWeight: "bold", color: "var(--primary)" }}>{metrics.length}개</div>
          </div>
          <div>
            <div className="text-sm">평균 글자수</div>
            <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{avgChar.toLocaleString()}자</div>
          </div>
          <div>
            <div className="text-sm">평균 이미지</div>
            <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{avgImg}장</div>
          </div>
        </div>
      </div>

      {/* Selected Blogs Summary Table */}
      <div className="glass-card mb-4" style={{ marginTop: "1rem" }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h2 style={{ fontSize: "1.1rem", margin: 0 }}>📝 선택한 글감 상세 분석</h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button 
              onClick={() => handleAutoWrite('blog')}
              style={{ background: "#3b82f6", color: "white", padding: "0.5rem 1rem", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: "bold", fontSize: "0.9rem" }}
            >
              ✍️ 블로그 자동 글쓰기
            </button>
            <button 
              onClick={() => handleAutoWrite('cafe')}
              style={{ background: "#10b981", color: "white", padding: "0.5rem 1rem", borderRadius: "6px", border: "none", cursor: "pointer", fontWeight: "bold", fontSize: "0.9rem" }}
            >
              ☕ 카페 자동 글쓰기
            </button>
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.95rem" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                <th style={{ padding: "0.8rem 0.5rem", color: "#64748b", width: "40px", textAlign: "center" }}>선택</th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b" }}>분류</th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b", minWidth: "180px" }}>포스팅 제목</th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b" }}>전체 글자수<br/><span style={{fontSize: "0.75rem"}}>(공백포함)</span></th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b" }}>띄어쓰기 수</th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b" }}>메인 키워드<br/><span style={{fontSize: "0.75rem"}}>(사용 횟수)</span></th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b" }}>서브 키워드<br/><span style={{fontSize: "0.75rem"}}>(사용 횟수)</span></th>
                <th style={{ padding: "0.8rem 1rem", color: "#64748b" }}>이미지 수</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, idx) => (
                <React.Fragment key={idx}>
                  <tr style={{ borderBottom: "1px solid #f1f5f9", cursor: "pointer", backgroundColor: expandedRows[idx] ? "#f8fafc" : (selectedBlogs.some(b => b.url === m.url) ? "#f0fdf4" : "transparent") }} onClick={() => toggleRow(idx)}>
                    <td style={{ padding: "0.8rem 0.5rem", textAlign: "center" }} onClick={e => e.stopPropagation()}>
                      <input 
                        type="checkbox" 
                        checked={selectedBlogs.some(b => b.url === m.url)}
                        onChange={(e) => handleCheckboxChange(e, m)}
                        style={{ transform: "scale(1.2)", cursor: "pointer" }}
                      />
                    </td>
                    <td style={{ padding: "0.8rem 1rem" }}>
                      <span style={{ 
                        fontSize: "0.75rem", padding: "4px 8px", borderRadius: "4px", 
                        backgroundColor: m.type === "인플루언서" ? "#fef08a" : m.type === "인기글" ? "#bfdbfe" : "#e2e8f0", 
                        color: "#1e293b", fontWeight: "bold" 
                      }}>
                        {m.type}
                      </span>
                    </td>
                    <td style={{ padding: "0.8rem 1rem", maxWidth: "250px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      <a href={m.url} target="_blank" rel="noreferrer" style={{ color: "#3b82f6", textDecoration: "none" }} onClick={e => e.stopPropagation()}>{m.title}</a>
                    </td>
                    <td style={{ padding: "0.8rem 1rem", fontWeight: "bold" }}>
                      {m.char_count_with_spaces?.toLocaleString() || 0}자
                      <div style={{fontSize: "0.75rem", color: "#64748b", fontWeight: "normal"}}>공백제외: {m.char_count?.toLocaleString() || 0}자</div>
                    </td>
                    <td style={{ padding: "0.8rem 1rem" }}>{m.space_count?.toLocaleString() || 0}개</td>
                    <td style={{ padding: "0.8rem 1rem" }}>
                      <div style={{color: "#3b82f6", fontWeight: "bold"}}>{m.main_kw}</div>
                      <div style={{fontSize: "0.85rem", color: "#64748b"}}>{m.main_kw_count || 0}회 사용</div>
                    </td>
                    <td style={{ padding: "0.8rem 1rem" }}>
                      <div style={{color: "#10b981", fontWeight: "bold"}}>{m.sub_kw || "-"}</div>
                      <div style={{fontSize: "0.85rem", color: "#64748b"}}>{m.sub_kw_count || 0}회 사용</div>
                    </td>
                    <td style={{ padding: "0.8rem 1rem", fontWeight: "bold" }}>{m.img_count}장</td>
                  </tr>
                  
                  {expandedRows[idx] && (
                    <tr style={{ backgroundColor: "#f8fafc", borderBottom: "2px solid #e2e8f0" }}>
                      <td colSpan="8" style={{ padding: "1.5rem" }}>

                        {/* 카페 작성자/카페 권위 카드 — 카페 글일 때만 노출 */}
                        {(m.cafe_author_info?.nickname || m.blog_info?.blog_id) && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", marginBottom: "1.5rem" }}>

                            {/* 1) 작성자 카드 */}
                            <div style={{ flex: "1 1 260px", border: "1px solid #e2e8f0", backgroundColor: "white", borderRadius: "10px", padding: "1.2rem" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                                <div style={{ fontSize: "0.8rem", color: "#7c3aed", fontWeight: "bold", letterSpacing: "0.02em" }}>👤 작성자</div>
                                {m.cafe_author_info.author_grade && (
                                  <GradeBadge
                                    grade={m.cafe_author_info.author_grade}
                                    score={m.cafe_author_info.author_score}
                                    title={`등급 ${m.cafe_author_info.score_breakdown?.tier_pts ?? 0}pt + 인기멤버 ${m.cafe_author_info.score_breakdown?.popular_bonus ?? 0}pt + 호응도 ${m.cafe_author_info.score_breakdown?.engagement ?? 0}pt`}
                                  />
                                )}
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                                <span style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#0f172a" }}>{m.cafe_author_info.nickname}</span>
                                {m.cafe_author_info.is_popular && (
                                  <span style={{ fontSize: "0.7rem", padding: "2px 8px", borderRadius: "12px", backgroundColor: "#fef3c7", color: "#92400e", fontWeight: "bold" }}>🌟 인기멤버</span>
                                )}
                              </div>
                              <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.3rem" }}>
                                <span style={{ fontWeight: "600" }}>{m.cafe_author_info.level_name || "-"}</span>
                                {m.cafe_author_info.level_tier != null && (
                                  <span style={{ marginLeft: "6px", fontSize: "0.75rem", color: "#94a3b8" }}>tier {m.cafe_author_info.level_tier}</span>
                                )}
                              </div>
                              <div style={{ fontSize: "0.8rem", color: "#64748b" }}>📅 {m.cafe_author_info.post_date || "-"}</div>
                            </div>

                            {/* 2) 카페 카드 */}
                            <div style={{ flex: "1 1 260px", border: "1px solid #e2e8f0", backgroundColor: "white", borderRadius: "10px", padding: "1.2rem" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                                <div style={{ fontSize: "0.8rem", color: "#0ea5e9", fontWeight: "bold", letterSpacing: "0.02em" }}>☕ 카페</div>
                                {m.cafe_author_info.cafe_grade && (
                                  <GradeBadge
                                    grade={m.cafe_author_info.cafe_grade}
                                    score={m.cafe_author_info.cafe_score}
                                    title={`회원수 ${m.cafe_author_info.score_breakdown?.cafe_member_pts ?? 0}pt (랭킹/활성도 미수집)`}
                                  />
                                )}
                              </div>
                              <div style={{ fontSize: "1rem", fontWeight: "bold", color: "#0f172a", marginBottom: "0.5rem", lineHeight: "1.35", maxHeight: "2.7em", overflow: "hidden" }}>
                                {m.cafe_author_info.cafe_name || "-"}
                              </div>
                              <div style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.3rem" }}>
                                👥 멤버 <span style={{ fontWeight: "bold" }}>{(m.cafe_author_info.cafe_member || 0).toLocaleString()}</span>명
                              </div>
                              {m.cafe_author_info.club_id && (
                                <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>🆔 클럽 {m.cafe_author_info.club_id}</div>
                              )}
                            </div>

                            {/* 3) 글 호응도 카드 */}
                            <div style={{ flex: "1 1 260px", border: "1px solid #e2e8f0", backgroundColor: "white", borderRadius: "10px", padding: "1.2rem" }}>
                              <div style={{ fontSize: "0.8rem", color: "#10b981", fontWeight: "bold", marginBottom: "0.6rem", letterSpacing: "0.02em" }}>📊 글 호응도</div>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
                                <div style={{ textAlign: "center" }}>
                                  <div style={{ fontSize: "0.75rem", color: "#64748b" }}>👁 조회</div>
                                  <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#0f172a" }}>{(m.cafe_author_info.view_count || 0).toLocaleString()}</div>
                                </div>
                                <div style={{ textAlign: "center" }}>
                                  <div style={{ fontSize: "0.75rem", color: "#64748b" }}>❤ 좋아요</div>
                                  <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#ef4444" }}>{(m.cafe_author_info.like_count || 0).toLocaleString()}</div>
                                </div>
                                <div style={{ textAlign: "center" }}>
                                  <div style={{ fontSize: "0.75rem", color: "#64748b" }}>💬 댓글</div>
                                  <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#3b82f6" }}>{(m.cafe_author_info.comment_count || 0).toLocaleString()}</div>
                                </div>
                              </div>
                            </div>

                          </div>
                        )}

                        {/* 키워드 분석내역 리스트 — 기존 */}
                        <div style={{ border: "1px solid #cbd5e1", backgroundColor: "white", borderRadius: "8px", padding: "1.2rem" }}>
                          <h3 style={{ fontSize: "1rem", marginBottom: "1rem", color: "#334155" }}>키워드 분석내역 리스트</h3>
                          {m.top_keywords && m.top_keywords.length > 0 ? (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.8rem" }}>
                              {m.top_keywords.map((kw, kwIdx) => (
                                <div key={kwIdx} style={{ backgroundColor: "#f1f5f9", padding: "0.5rem 1rem", borderRadius: "20px", fontSize: "0.85rem", border: "1px solid #e2e8f0" }}>
                                  <span style={{ fontWeight: "bold", color: "#334155" }}>{kw.keyword}</span>
                                  <span style={{ marginLeft: "6px", color: "#64748b" }}>{kw.count}회</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div style={{ color: "#94a3b8", fontSize: "0.9rem" }}>키워드 추출 데이터가 없습니다. 본문이 너무 짧거나 분석에 실패했을 수 있습니다.</div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>

        {/* Cafe Popular Posts from Smart Blocks */}
        {cafePopularBlocks.length > 0 && (
          <div className="glass-card mb-4" style={{ marginTop: "1rem" }}>
            <h2 className="mb-3" style={{ color: "#059669" }}>🔥 통합검색 카페 인기글 발견!</h2>
            <div style={{ display: "grid", gap: "10px" }}>
              {cafePopularBlocks.map((block, bIdx) => (
                <div key={bIdx} style={{ backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", padding: "15px", borderRadius: "8px" }}>
                  <h3 style={{ fontSize: "1rem", marginBottom: "10px", color: "#166534" }}>{block.block_title}</h3>
                  <ul style={{ margin: 0, paddingLeft: "20px", color: "#374151", fontSize: "0.9rem" }}>
                    {block.links.map((link, lIdx) => (
                      <li key={lIdx} style={{ marginBottom: "5px" }}>
                        <a href={link.url} target="_blank" rel="noreferrer" style={{ color: "#2563eb", textDecoration: "none" }}>
                          {link.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}

      <div className="grid-2">
        {/* Top Keywords */}
        <div className="glass-card">
          <h2 className="mb-2">💡 키워드 사용 빈도 TOP 10</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
            {top_keywords && top_keywords.length > 0 ? (
              top_keywords.map((kw, idx) => {
                const maxCount = Math.max(...top_keywords.map(k => k.count), 1);
                const widthPercent = Math.max(10, (kw.count / maxCount) * 100);
                return (
                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <div style={{ width: "80px", fontWeight: "bold", textAlign: "right" }}>{kw.keyword}</div>
                    <div style={{ flex: 1, backgroundColor: "#e2e8f0", borderRadius: "12px", height: "24px", overflow: "hidden" }}>
                      <div 
                        style={{ 
                          width: `${widthPercent}%`, 
                          height: "100%", 
                          background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
                          transition: "width 1s ease-out"
                        }}
                      ></div>
                    </div>
                    <div style={{ width: "40px", textAlign: "left", color: "var(--text-sub)" }}>{kw.count}회</div>
                  </div>
                );
              })
            ) : (
              <p>키워드 데이터가 없습니다.</p>
            )}
          </div>
        </div>

        {/* Winning Formula AI Report */}
        <div className="glass-card">
          <h2 className="mb-2">🏆 상위노출 공식 (Winning Formula)</h2>
          <div 
            style={{ 
              lineHeight: "1.6", 
              backgroundColor: "rgba(255,255,255,0.5)", 
              padding: "1rem", 
              borderRadius: "8px",
              whiteSpace: "pre-wrap"
            }}
          >
            {formula || "가이드라인을 생성하지 못했습니다."}
          </div>
        </div>
      </div>
    </div>
  );
}
