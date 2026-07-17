"use client";
// 카페 포스팅 탭 — 발행 계정 선택 / 계정별 카페·게시판 매칭 / 원고 작성·AI 생성 / 일괄 발행 대기열.
// 상태·핸들러는 page 에서 useCafeAuto() 로 만든 객체(s)를 받아 공유한다.
export default function PostTab({ s }) {
  const {
    mainTab,
    setMainTab,
    activeTab,
    setActiveTab,
    loginMode,
    setLoginMode,
    naverId,
    setNaverId,
    naverPw,
    setNaverPw,
    cafeUrl,
    setCafeUrl,
    boardName,
    setBoardName,
    actionType,
    setActionType,
    targetKeyword,
    setTargetKeyword,
    title,
    setTitle,
    content,
    setContent,
    sourceMode,
    setSourceMode,
    showAdvanced,
    setShowAdvanced,
    images,
    setImages,
    referenceData,
    setReferenceData,
    targetUrls,
    setTargetUrls,
    selectedAccounts,
    setSelectedAccounts,
    accSearch,
    setAccSearch,
    targetMultiKeyword,
    setTargetMultiKeyword,
    targetMultiLike,
    setTargetMultiLike,
    delayMin,
    setDelayMin,
    delayMax,
    setDelayMax,
    accounts,
    setAccounts,
    schedules,
    setSchedules,
    newAccId,
    setNewAccId,
    newAccPw,
    setNewAccPw,
    newCafeAccId,
    setNewCafeAccId,
    newCafeUrl,
    setNewCafeUrl,
    newCafeBoard,
    setNewCafeBoard,
    newSchAccId,
    setNewSchAccId,
    newSchCafeId,
    setNewSchCafeId,
    newSchTime,
    setNewSchTime,
    newSchCategory,
    setNewSchCategory,
    newSchContentItem,
    setNewSchContentItem,
    newSchContentItemTitle,
    setNewSchContentItemTitle,
    newSchCount,
    setNewSchCount,
    newSchQty,
    setNewSchQty,
    newSchPostUrl,
    setNewSchPostUrl,
    newSchInterval,
    setNewSchInterval,
    newSchDoView,
    setNewSchDoView,
    newSchDoLike,
    setNewSchDoLike,
    categories,
    setCategories,
    categoryItems,
    setCategoryItems,
    pickCategory,
    setPickCategory,
    pickItems,
    setPickItems,
    pickItemId,
    setPickItemId,
    loading,
    setLoading,
    registeredIds,
    setRegisteredIds,
    promptCategory,
    setPromptCategory,
    includeSourceLink,
    setIncludeSourceLink,
    isGenerating,
    setIsGenerating,
    cafeGenerated,
    setCafeGenerated,
    imageFiles,
    setImageFiles,
    imageFolder,
    setImageFolder,
    useTethering,
    setUseTethering,
    cafeCardNews,
    setCafeCardNews,
    cafeCardCount,
    setCafeCardCount,
    cafeTrackRank,
    setCafeTrackRank,
    cafeInsertMap,
    setCafeInsertMap,
    cafeMapQuery,
    setCafeMapQuery,
    subKeywords,
    setSubKeywords,
    showLibPicker,
    setShowLibPicker,
    accountDelay,
    setAccountDelay,
    accountTargets,
    setAccountTargets,
    savedManuscripts,
    setSavedManuscripts,
    batchPosting,
    setBatchPosting,
    batchCancelRef,
    editMs,
    setEditMs,
    loadRegistered,
    taskId,
    setTaskId,
    taskKind,
    setTaskKind,
    statusLogs,
    setStatusLogs,
    taskStatus,
    setTaskStatus,
    isModalOpen,
    setIsModalOpen,
    fetchAccounts,
    fetchSchedules,
    saveCafeDraft,
    pollGeneration,
    handleDescribeImages,
    handleGenerateCafe,
    setAccTarget,
    prefillTargets,
    fetchManuscripts,
    handleSaveManuscripts,
    handleDeleteManuscript,
    handleUpdateManuscript,
    handleBatchPublish,
    handleStartSingle,
    handleLoadManuscript,
    handleStartTargetMulti,
    handleCancelTask,
    toggleAccountSelection,
    handleRegisterAccount,
    handleAddAccount,
    handleDeleteAccount,
    handleAddCafe,
    importCafeExcel,
    handleAddSchedule,
    handleDeleteSchedule,
    placeUrl,
    setPlaceUrl,
    collectingMatjip,
    collectMatjipSource,
    handlePickFolder,
  } = s;

  const matjip = mainTab === "matjip";

  return (
            <>
            {/* 블로그 발행과 동일한 2단 레이아웃: 좌측 = 설정(계정→카페→원고→발행), 우측 = 원고 검토·수정 */}
            <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start", flexWrap: "wrap" }}>
            <div style={{ flex: "1.5 1 480px", minWidth: 0, display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#334155" }}>1. 발행 계정 선택</h2>
                <p style={{ margin: "0 0 0.8rem", fontSize: "0.82rem", color: "#64748b" }}>하단 <b>1. 네이버 아이디 풀</b>에서 등록·기기 인증한 계정 중 발행에 사용할 계정을 고르세요. (인증된 계정은 자동 로그인)</p>
                {/* 계정이 많을 때: 검색 + 전체선택/해제 + 선택 수 */}
                {accounts.length > 0 && (() => {
                  const filtered = accounts.filter(a => a.naver_id.toLowerCase().includes(accSearch.toLowerCase()));
                  const filteredIds = filtered.map(a => a.id);
                  const allSel = filteredIds.length > 0 && filteredIds.every(id => selectedAccounts.includes(id));
                  return (
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.7rem", flexWrap: "wrap" }}>
                      <input type="text" placeholder="🔍 계정 검색" value={accSearch} onChange={e => setAccSearch(e.target.value)} style={{ padding: "0.45rem 0.7rem", border: "1px solid #cbd5e1", borderRadius: "20px", width: "180px" }} />
                      <button onClick={() => setSelectedAccounts(prev => allSel ? prev.filter(id => !filteredIds.includes(id)) : Array.from(new Set([...prev, ...filteredIds])))}
                        style={{ padding: "0.4rem 0.8rem", background: allSel ? "#e2e8f0" : "#2563eb", color: allSel ? "#334155" : "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>
                        {allSel ? "전체 해제" : `전체 선택${accSearch ? " (검색결과)" : ""}`}
                      </button>
                      {selectedAccounts.length > 0 && (
                        <button onClick={() => setSelectedAccounts([])} style={{ padding: "0.4rem 0.8rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem" }}>선택 비우기</button>
                      )}
                      <span style={{ fontSize: "0.85rem", color: "#2563eb", fontWeight: "bold" }}>선택 {selectedAccounts.length} / 전체 {accounts.length}</span>
                    </div>
                  );
                })()}
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", maxHeight: "180px", overflowY: "auto", padding: "0.2rem" }}>
                  {accounts.filter(a => a.naver_id.toLowerCase().includes(accSearch.toLowerCase())).map(acc => (
                    <label key={acc.id} style={{ padding: "0.5rem 1rem", border: "1px solid #cbd5e1", borderRadius: "20px", cursor: "pointer", background: selectedAccounts.includes(acc.id) ? "#2563eb" : "white", color: selectedAccounts.includes(acc.id) ? "white" : "black", fontWeight: "bold" }}>
                      <input type="checkbox" style={{ display: "none" }} checked={selectedAccounts.includes(acc.id)} onChange={() => toggleAccountSelection(acc.id)} />
                      {acc.naver_id}
                    </label>
                  ))}
                  {accounts.length === 0 && <span style={{ color: "#94a3b8" }}>하단 '네이버 아이디 풀 관리'에서 계정을 먼저 등록·인증해주세요.</span>}
                </div>
                {selectedAccounts.length > 1 && (
                  <p style={{ margin: "0.8rem 0 0", fontSize: "0.82rem", color: "#2563eb" }}>* 계정별로 아래에서 카페·게시판을 따로 지정하고, 원고도 따로 생성·저장하여 일괄 발행할 수 있습니다.</p>
                )}
              </div>

              {/* 계정별 타겟 카페·게시판 매칭 */}
              {selectedAccounts.length > 0 && (
                <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
                    <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>2. 계정별 타겟 카페·게시판 매칭</h2>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <label style={{ padding: "0.4rem 0.8rem", background: "#2563eb", color: "white", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }} title="엑셀/CSV로 일괄 등록 (A열 아이디, B열 카페 URL, C열 게시판, D열 비밀번호)">
                        📄 엑셀 일괄등록
                        <input type="file" accept=".xlsx,.csv" style={{ display: "none" }} onChange={e => { const f = e.target.files[0]; e.target.value = ""; if (f) importCafeExcel(f); }} />
                      </label>
                      <button onClick={prefillTargets} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>📥 가입 카페 매핑 불러오기</button>
                    </div>
                  </div>
                  <p style={{ margin: "0 0 0.8rem", fontSize: "0.78rem", color: "#94a3b8" }}>엑셀 형식 — A열: 네이버 아이디, B열: 카페 URL, C열(선택): 게시판, D열(선택): 비밀번호. (없는 아이디는 자동 생성, 비번 있으면 함께 저장)</p>

                  {/* 카페 추가(매핑) — 여기서 바로 계정에 카페·게시판 등록 */}
                  <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.8rem", padding: "0.8rem", background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "6px", flexWrap: "wrap", alignItems: "center" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#334155" }}>➕ 카페 추가:</span>
                    <select value={newCafeAccId} onChange={e => setNewCafeAccId(e.target.value)} style={{ padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "4px" }}>
                      <option value="">계정 선택</option>
                      {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                    </select>
                    <input type="text" placeholder="카페 URL (예: https://cafe.naver.com/xxx)" value={newCafeUrl} onChange={e => setNewCafeUrl(e.target.value)} style={{ padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "4px", flex: 1, minWidth: "200px" }} />
                    <button onClick={handleAddCafe} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>등록</button>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                    <thead><tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "120px" }}>발행 계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "230px" }}>가입 카페 매핑에서 선택</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>카페 URL</th>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "160px" }}>게시판 이름</th>
                      <th style={{ padding: "0.5rem", textAlign: "center", width: "50px" }}>제외</th>
                    </tr></thead>
                    <tbody>
                      {selectedAccounts.map(id => {
                        const acc = accounts.find(a => a.id === id);
                        const t = accountTargets[id] || {};
                        const cafes = (acc && acc.cafes) || [];
                        const selIdx = cafes.findIndex(c => c.cafe_url === t.cafe_url && c.board_name === t.board_name);
                        return (
                          <tr key={id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                            <td style={{ padding: "0.5rem", fontWeight: "bold" }}>{acc ? acc.naver_id : id}</td>
                            <td style={{ padding: "0.5rem" }}>
                              <select value={selIdx >= 0 ? selIdx : ""} onChange={e => { const c = cafes[Number(e.target.value)]; if (c) setAccountTargets(prev => ({ ...prev, [id]: { cafe_url: c.cafe_url, board_name: c.board_name } })); }} style={{ width: "100%", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }}>
                                <option value="">{cafes.length ? "매핑 카페 선택…" : "(매핑 없음 — 소통·육성에서 등록)"}</option>
                                {cafes.map((c, ci) => <option key={ci} value={ci}>{(c.cafe_url || "").replace("https://cafe.naver.com/", "")} / {c.board_name}</option>)}
                              </select>
                            </td>
                            <td style={{ padding: "0.5rem" }}><input type="text" placeholder={cafeUrl || "카페 URL"} value={t.cafe_url || ""} onChange={e => setAccTarget(id, "cafe_url", e.target.value)} style={{ width: "100%", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} /></td>
                            <td style={{ padding: "0.5rem" }}><input type="text" placeholder={boardName || "게시판"} value={t.board_name || ""} onChange={e => setAccTarget(id, "board_name", e.target.value)} style={{ width: "100%", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} /></td>
                            <td style={{ padding: "0.5rem", textAlign: "center" }}>
                              <button onClick={() => toggleAccountSelection(id)} title="이 계정을 발행 대상에서 제외" style={{ padding: "0.3rem 0.55rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}>✕</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <p style={{ margin: "0.6rem 0 0", fontSize: "0.8rem", color: "#64748b" }}>* 계정별로 <b>가입 카페 매핑(여러 카페)</b>에서 선택하거나 직접 입력하세요. 매핑 추가/수정은 <b>소통·육성 &gt; 아이디별 가입 카페 매핑</b>에서. 비우면 위 '타겟 카페' 공통값 사용.</p>
                </div>
              )}

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>3. 원고 만들기</h2>
                  {/* 맛집 포스팅은 플레이스 URL로 소재를 모으므로 '웹에서 불러오기'는 정보성에서만 노출 */}
                  {!matjip && (
                    <button onClick={() => setIsModalOpen(true)} style={{ padding: '0.4rem 0.8rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                      ☁️ 웹에서 불러오기
                    </button>
                  )}
                </div>
                {/* 메인/서브 키워드 — 정보성·맛집 공통. 맛집은 플레이스 리뷰가 소스지만 제목·본문 SEO를 위해 메인 키워드를 받는다 */}
                <input type="text" placeholder={matjip ? "메인 키워드 (예: 부산 하모회 / 서면 맛집)" : "타겟(메인) 키워드"} value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "0.6rem", boxSizing: "border-box" }} />
                <input type="text" placeholder="서브 키워드 (쉼표로 구분, 최대 5개 — 본문에 자연스럽게 녹임)" value={subKeywords} onChange={e => setSubKeywords(e.target.value)} style={{ width: "100%", padding: "0.7rem", marginBottom: "1rem", boxSizing: "border-box", fontSize: "0.9rem" }} />

                {/* 맛집 포스팅: 플레이스 URL + 소재 자동 수집 */}
                {matjip && (
                  <div style={{ marginBottom: "1rem", padding: "0.9rem 1rem", background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: "8px" }}>
                    <div style={{ fontSize: "0.9rem", fontWeight: "bold", color: "#9a3412", marginBottom: "0.5rem" }}>🍜 맛집 소재 수집 (플레이스 리뷰 + 블로그 후기)</div>
                    <input type="text" placeholder="네이버 플레이스 URL (선택 — 방문자 리뷰 참고)" value={placeUrl} onChange={e => setPlaceUrl(e.target.value)} style={{ width: "100%", padding: "0.7rem", marginBottom: "0.6rem", boxSizing: "border-box", border: "1px solid #fdba74", borderRadius: "6px" }} />
                    <button onClick={collectMatjipSource} disabled={collectingMatjip} style={{ width: "100%", padding: "0.7rem", background: collectingMatjip ? "#94a3b8" : "#ea580c", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: collectingMatjip ? "wait" : "pointer" }}>
                      {collectingMatjip ? "소재 수집 중... (에이전트 실행 필요)" : "🔍 플레이스 리뷰·블로그 후기 수집"}
                    </button>
                    <p style={{ margin: "0.5rem 0 0", fontSize: "0.78rem", color: "#9a3412" }}>* 수집이 끝나면 아래 글감이 자동으로 채워집니다. 이후 <b>AI 원고 생성</b> → 검토 → 발행. (수집은 집 PC 에이전트가 수행)</p>
                  </div>
                )}

                {/* 맛집: 내 사진 폴더 지정 (업로드 X). 발행하는 내 PC(에이전트)의 폴더 사진을 글에 넣는다. */}
                {matjip && (
                  <div style={{ marginBottom: "1rem", padding: "0.8rem 1rem", background: "#eef2ff", border: "1px solid #c7d2fe", borderRadius: "8px" }}>
                    <div style={{ fontSize: "0.9rem", fontWeight: "bold", color: "#3730a3", marginBottom: "0.4rem" }}>🖼 내 사진 폴더 (선택)</div>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      <input type="text" placeholder="예: C:\사진\맛집  (또는 오른쪽 '폴더 찾기')" value={imageFolder || ""} onChange={e => setImageFolder(e.target.value)}
                        style={{ flex: 1, minWidth: "180px", padding: "0.6rem", border: "1px solid #c7d2fe", borderRadius: "6px", boxSizing: "border-box", fontSize: "0.9rem" }} />
                      <button type="button" onClick={handlePickFolder}
                        style={{ flexShrink: 0, padding: "0.6rem 1rem", background: "#4f46e5", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", whiteSpace: "nowrap" }}>
                        📁 폴더 찾기
                      </button>
                    </div>
                    <p style={{ margin: "0.45rem 0 0", fontSize: "0.78rem", color: "#4338ca" }}>
                      * <b>'폴더 찾기'</b>를 누르면 <b>내 PC에 폴더 선택창</b>이 뜹니다(에이전트 실행 중이어야 함). 고른 폴더의 사진(.jpg/.png)이 발행 글에 들어가요. 비워두면 AI 카드뉴스가 자동 생성됩니다.
                    </p>
                  </div>
                )}

                {/* 글감 소스 토글 — 3방식 중 하나만 노출 (블로그 발행과 통일된 방식)
                    맛집 포스팅은 위 '맛집 소재 수집'이 소스이므로 글감수집 토글은 숨긴다 */}
                {actionType === "post" && !matjip && (
                  <div style={{ display: "flex", gap: "0.4rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                    {[["collect", "📥 글감수집에서"], ["write", "✍️ 직접 작성"], ["image", "🖼 이미지로"]].map(([k, label]) => (
                      <button key={k} type="button" onClick={() => setSourceMode(k)}
                        style={{ padding: "0.5rem 1rem", borderRadius: "999px", border: sourceMode === k ? "1px solid #2563eb" : "1px solid #cbd5e1", background: sourceMode === k ? "#2563eb" : "white", color: sourceMode === k ? "white" : "#475569", fontWeight: "bold", fontSize: "0.88rem", cursor: "pointer" }}>
                        {label}
                      </button>
                    ))}
                  </div>
                )}

                {/* 글감수집에서 글감 선택 (제목/본문 자동 채움) — 맛집 모드에선 미노출 */}
                {actionType === "post" && !matjip && sourceMode === "collect" && (
                  <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", alignItems: "center", flexWrap: "wrap", padding: "0.7rem", background: "#eff6ff", border: "1px dashed #bfdbfe", borderRadius: "6px" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#1e40af" }}>📚 글감수집에서 선택:</span>
                    <select value={pickCategory} onChange={e => setPickCategory(e.target.value)} style={{ padding: "0.45rem", border: "1px solid #cbd5e1", borderRadius: "4px" }}>
                      <option value="">카테고리 선택</option>
                      {categories.map((c, i) => <option key={i} value={c}>{c}</option>)}
                    </select>
                    <select value={pickItemId} onChange={e => {
                        setPickItemId(e.target.value);
                        const it = pickItems.find(x => String(x.id) === e.target.value);
                        if (it) { setTitle(it.title || ""); setContent(it.content || it.body || ""); setTargetKeyword(prev => prev || it.title || ""); }
                      }} disabled={!pickCategory} style={{ padding: "0.45rem", border: "1px solid #cbd5e1", borderRadius: "4px", flex: 1, minWidth: "220px" }}>
                      <option value="">{pickCategory ? (pickItems.length ? "글감 선택 → 제목·본문 채움" : "글감 없음") : "먼저 카테고리 선택"}</option>
                      {pickItems.map(it => <option key={it.id} value={it.id}>{it.title}</option>)}
                    </select>
                    <span style={{ fontSize: "0.78rem", color: "#64748b" }}>* 선택하면 아래 제목·본문에 채워집니다(이후 AI 원고 생성도 가능).</span>
                  </div>
                )}
                {/* 제목/본문(글감) — 생성된 원고 검토는 우측 패널에서 (블로그 발행과 동일) */}
                {actionType === "post" && sourceMode !== "image" && <input type="text" placeholder="직접 제목 작성 시" value={title} onChange={e => setTitle(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem", boxSizing: "border-box" }} />}
                {sourceMode !== "image" && <textarea placeholder="직접 본문 작성 시 (또는 'AI 원고 생성'으로 미리보기 후 검토)" value={content} onChange={e => setContent(e.target.value)} style={{ width: "100%", height: content ? "260px" : "100px", padding: "0.8rem", boxSizing: "border-box" }} />}
                {actionType === "post" && sourceMode === "image" && (
                  <div style={{ marginTop: "0.8rem", padding: "0.8rem", background: "#f0fdf4", border: "1px dashed #86efac", borderRadius: "8px" }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#166534", marginBottom: "0.4rem" }}>🖼️ 이미지 + 키워드로 글감 만들기</div>
                    <input type="file" accept="image/*" multiple onChange={e => setImageFiles(e.target.files)} style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }} />
                    <button type="button" onClick={() => setShowLibPicker(true)} style={{ padding: "0.5rem 1rem", background: "#0ea5e9", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", width: "100%" }}>
                      🗂️ 이미지 보관함에서 가져오기
                    </button>
                    {imageFolder && <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#16a34a" }}>✅ 첨부 이미지가 발행 글에도 함께 들어갑니다.</p>}
                    <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#64748b" }}>키워드(위 '타겟 키워드') + 첨부 이미지를 넣고 아래 <b>'AI 원고 생성'</b>을 누르면, AI가 이미지를 분석해 글감을 만든 뒤 곧바로 원고까지 만듭니다.</p>
                  </div>
                )}
                {actionType === "post" && (
                  <div style={{ marginTop: "0.7rem", padding: "0.7rem 0.9rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.88rem", cursor: "pointer", color: cafeCardNews ? "#2563eb" : "#64748b", fontWeight: "bold" }}>
                      <input type="checkbox" checked={cafeCardNews} onChange={e => setCafeCardNews(e.target.checked)} style={{ width: 16, height: 16 }} />
                      🎨 첨부 이미지가 없을 때 AI 카드뉴스 자동 생성
                    </label>
                    {cafeCardNews && (
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "0.5rem", fontSize: "0.83rem", color: "#475569" }}>
                        카드뉴스 장수
                        <input type="number" min="1" max="5" value={cafeCardCount} onChange={e => setCafeCardCount(e.target.value)} style={{ width: "60px", padding: "0.3rem 0.5rem", border: "1px solid #cbd5e1", borderRadius: "5px" }} />
                        장 (본문 [이미지] 위치·소제목에 분산 배치)
                      </div>
                    )}
                    {!cafeCardNews && <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#94a3b8" }}>* 끄면 첨부 이미지가 없을 때 이미지 없이 텍스트만 발행됩니다.</p>}
                    <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.6rem", paddingTop: "0.6rem", borderTop: "1px dashed #e2e8f0", fontSize: "0.88rem", cursor: "pointer", color: cafeTrackRank ? "#16a34a" : "#64748b", fontWeight: "bold" }}>
                      <input type="checkbox" checked={cafeTrackRank} onChange={e => setCafeTrackRank(e.target.checked)} style={{ width: 16, height: 16 }} />
                      📈 발행 후 이 글을 카페 통검 순위 추적에 자동 등록
                    </label>
                    <p style={{ margin: "0.3rem 0 0", fontSize: "0.76rem", color: "#94a3b8" }}>* 발행 성공 시 (타겟 키워드 + 글 URL)이 '카페 통검 순위'에 등록돼 매일 자동 체크됩니다.</p>
                    <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.6rem", paddingTop: "0.6rem", borderTop: "1px dashed #e2e8f0", fontSize: "0.88rem", cursor: "pointer", color: cafeInsertMap ? "#0ea5e9" : "#64748b", fontWeight: "bold" }}>
                      <input type="checkbox" checked={cafeInsertMap} onChange={e => setCafeInsertMap(e.target.checked)} style={{ width: 16, height: 16 }} />
                      🗺️ 본문 하단에 네이버 지도(장소) 첨부
                    </label>
                    {cafeInsertMap && (
                      <input type="text" value={cafeMapQuery} onChange={e => setCafeMapQuery(e.target.value)} placeholder="삽입할 장소명 또는 주소 (예: 부산 하모회 000점)" style={{ width: "100%", marginTop: "0.5rem", padding: "0.5rem 0.7rem", border: "1px solid #cbd5e1", borderRadius: "6px", boxSizing: "border-box", fontSize: "0.85rem" }} />
                    )}
                    <p style={{ margin: "0.3rem 0 0", fontSize: "0.76rem", color: "#94a3b8" }}>* 작성한 글 맨 아래에 네이버 검색 결과 첫 장소가 지도로 삽입됩니다. (장소명이 정확할수록 정확히 잡힙니다)</p>
                  </div>
                )}
                {actionType === "post" && (
                  <button onClick={handleGenerateCafe} disabled={isGenerating} style={{ marginTop: "0.6rem", padding: "0.7rem 1rem", background: isGenerating ? "#94a3b8" : "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: isGenerating ? "wait" : "pointer", width: "100%" }}>
                    {isGenerating ? "AI 원고 생성 중... (최대 1~2분)" : "✨ AI 원고 생성 (미리보기·검토)"}
                  </button>
                )}
                {actionType === "post" && (
                  <p style={{ margin: "0.5rem 0 0", fontSize: "0.82rem", color: "#64748b" }}>
                    * 글감수집에서 넘어온 경우, 위 내용은 <b>참고 글감</b>입니다. <b>AI 원고 생성</b>을 눌러 실제 카페 원고를 만든 뒤 검토·수정하고 발행하세요. (생성 없이 발행하면 발행 시점에 자동 작성됩니다)
                  </p>
                )}
                {content && content.includes("[링크] http") && (
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", marginTop: "0.8rem", fontSize: "0.9rem", color: "#1e40af", fontWeight: "bold" }}>
                    <input type="checkbox" checked={includeSourceLink} onChange={e => setIncludeSourceLink(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                    🔗 글 끝에 출처(원문) 링크 추가
                  </label>
                )}

                {/* 고급 설정 접기: 계정 간 발행 텀 + USB 테더링 (블로그 발행과 통일) */}
                <button type="button" onClick={() => setShowAdvanced(v => !v)} style={{ marginTop: "1rem", padding: "0.6rem 0.9rem", width: "100%", textAlign: "left", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px", cursor: "pointer", fontWeight: "bold", color: "#475569", fontSize: "0.9rem" }}>
                  ⚙️ 고급 설정 (발행 텀 · USB 테더링) {showAdvanced ? "▲" : "▼"}
                </button>
                {showAdvanced && (
                <div style={{ marginTop: "0.5rem", padding: "1rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.8rem" }}>
                    <span style={{ fontWeight: "bold", color: "#475569" }}>계정 간 발행 텀 (딜레이):</span>
                    <input type="number" min="0" value={accountDelay} onChange={e => setAccountDelay(Number(e.target.value))} style={{ width: "60px", padding: "0.4rem", border: "1px solid #cbd5e1", borderRadius: "4px", textAlign: "center" }} />
                    <span style={{ color: "#64748b" }}>분 대기 후 다음 계정 발행</span>
                  </div>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontWeight: "bold", color: useTethering ? "#3b82f6" : "#64748b", flexWrap: "wrap" }}>
                    <input type="checkbox" checked={useTethering} onChange={e => setUseTethering(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                    <span style={{ whiteSpace: "nowrap" }}>📱 안드로이드 USB 테더링 (비행기 모드 자동 토글) 사용</span>
                    <span style={{ fontSize: "0.8rem", color: "#94a3b8", fontWeight: "normal" }}>* PC와 폰이 USB로 연결되어 있고, USB 테더링이 켜져 있어야 합니다.</span>
                  </label>
                </div>
                )}

                {actionType === "post" && (
                  <button onClick={handleSaveManuscripts} style={{ marginTop: "0.8rem", padding: "0.7rem 1rem", background: "#0ea5e9", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", width: "100%" }}>
                    💾 계정별 원고 + 카페/게시판 저장 (일괄 발행 대기열에 등록)
                  </button>
                )}
              </div>

              {/* 발행 시작 (좌측 하단) */}
              <div style={{ display: "flex", gap: "1rem" }}>
                <button onClick={handleStartSingle} disabled={loading} style={{ flex: 1, padding: "1rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: loading ? "wait" : "pointer" }}>
                  {loading ? "작업 중..." : "🚀 발행 시작하기"}
                </button>
                {loading && (
                  <button onClick={handleCancelTask} style={{ padding: "1rem 2rem", background: "#ef4444", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer" }}>
                    ■ 작업 강제 중지
                  </button>
                )}
              </div>
            </div>

            {/* ── 우측: 생성된 계정별 원고 검토·수정 + 발행 대기열 (블로그 발행과 동일 위치) ── */}
            <div style={{ flex: "1 1 380px", minWidth: 0, display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: "0 0 1rem" }}>✅ 생성된 계정별 원고 검토·수정</h2>
                {cafeGenerated.length === 0 ? (
                  <div style={{ padding: "2.5rem 1rem", textAlign: "center", color: "#94a3b8", border: "2px dashed #cbd5e1", borderRadius: "8px", fontSize: "0.9rem" }}>
                    좌측에서 '✨ AI 원고 생성'을 누르면<br />선택한 계정 수만큼 원고가 생성되어 여기에 표시됩니다.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <p style={{ margin: 0, fontSize: "0.85rem", color: "#7c3aed", fontWeight: "bold" }}>✨ 계정별로 검토·수정한 뒤 저장·발행하세요.</p>
                    {cafeGenerated.map((g, idx) => (
                      <div key={idx} style={{ border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1rem", background: "#faf5ff" }}>
                        <div style={{ fontWeight: "bold", color: "#2563eb", marginBottom: "0.5rem" }}>📝 {g.account_id} 계정 원고</div>
                        <input type="text" value={g.title || ""} placeholder="제목"
                          onChange={e => setCafeGenerated(prev => prev.map((x, i) => i === idx ? { ...x, title: e.target.value } : x))}
                          style={{ width: "100%", padding: "0.6rem", marginBottom: "0.5rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                        <textarea value={g.content || ""}
                          onChange={e => setCafeGenerated(prev => prev.map((x, i) => i === idx ? { ...x, content: e.target.value } : x))}
                          style={{ width: "100%", height: "240px", padding: "0.8rem", border: "1px solid #cbd5e1", boxSizing: "border-box" }} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 저장된 원고 / 일괄 작업 시작 */}
              {actionType === "post" && savedManuscripts.length > 0 && (
                <div style={{ background: "white", padding: "1.5rem", border: "2px solid #0ea5e9", borderRadius: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
                    <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#0c4a6e", margin: 0 }}>📋 저장된 원고 ({savedManuscripts.length}) — 일괄 발행 대기열</h2>
                    <button onClick={handleBatchPublish} disabled={batchPosting || loading} style={{ padding: "0.6rem 1.2rem", background: (batchPosting || loading) ? "#94a3b8" : "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: (batchPosting || loading) ? "wait" : "pointer" }}>
                      {batchPosting ? "발행 시작 중..." : "🚀 일괄 작업 시작"}
                    </button>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
                    <thead><tr style={{ background: "#f0f9ff", borderBottom: "2px solid #bae6fd" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left", width: "120px" }}>계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>카페 / 게시판</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>제목</th>
                      <th style={{ padding: "0.5rem", textAlign: "center", width: "110px" }}>관리</th>
                    </tr></thead>
                    <tbody>
                      {savedManuscripts.map(m => (
                        <tr key={m.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                          <td style={{ padding: "0.5rem", fontWeight: "bold" }}>{m.account_id}</td>
                          <td style={{ padding: "0.5rem", fontSize: "0.8rem", color: "#475569", wordBreak: "break-all" }}>{m.cafe_url || "(공통)"}<br/>{m.board_name}</td>
                          <td style={{ padding: "0.5rem" }}>{m.title || "(자동)"}</td>
                          <td style={{ padding: "0.5rem", textAlign: "center", whiteSpace: "nowrap" }}>
                            <button onClick={() => setEditMs({ ...m })} style={{ padding: "0.25rem 0.5rem", background: "white", color: "#2563eb", border: "1px solid #2563eb", borderRadius: "4px", cursor: "pointer", marginRight: "0.3rem" }}>수정</button>
                            <button onClick={() => handleDeleteManuscript(m.id)} style={{ padding: "0.25rem 0.5rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer" }}>삭제</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p style={{ margin: "0.6rem 0 0", fontSize: "0.8rem", color: "#64748b" }}>* 각 계정의 저장된 카페·게시판으로 순차 발행됩니다(계정 간 {accountDelay}분 텀{useTethering ? ", 테더링 IP 회전" : ""}).</p>
                </div>
              )}
            </div>
            </div>

              {/* 저장 원고 수정 모달 */}
              {editMs && (
                <div onClick={() => setEditMs(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
                  <div onClick={e => e.stopPropagation()} style={{ background: "white", borderRadius: "10px", padding: "1.5rem", width: "min(700px, 92vw)", maxHeight: "88vh", overflowY: "auto" }}>
                    <h3 style={{ margin: "0 0 1rem", fontSize: "1.15rem" }}>✏️ 저장 원고 수정 — <span style={{ color: "#2563eb" }}>{editMs.account_id}</span></h3>
                    <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem" }}>
                      <input type="text" placeholder="카페 URL" value={editMs.cafe_url || ""} onChange={e => setEditMs({ ...editMs, cafe_url: e.target.value })} style={{ flex: 1, padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                      <input type="text" placeholder="게시판" value={editMs.board_name || ""} onChange={e => setEditMs({ ...editMs, board_name: e.target.value })} style={{ width: "180px", padding: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px" }} />
                    </div>
                    <input type="text" placeholder="제목" value={editMs.title || ""} onChange={e => setEditMs({ ...editMs, title: e.target.value })} style={{ width: "100%", padding: "0.6rem", marginBottom: "0.6rem", border: "1px solid #cbd5e1", borderRadius: "4px", boxSizing: "border-box" }} />
                    <textarea value={editMs.content || ""} onChange={e => setEditMs({ ...editMs, content: e.target.value })} style={{ width: "100%", height: "320px", padding: "0.8rem", border: "1px solid #cbd5e1", borderRadius: "4px", boxSizing: "border-box" }} />
                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1rem" }}>
                      <button onClick={() => setEditMs(null)} style={{ padding: "0.6rem 1.2rem", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer" }}>취소</button>
                      <button onClick={handleUpdateManuscript} style={{ padding: "0.6rem 1.2rem", background: "#2563eb", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>저장</button>
                    </div>
                  </div>
                </div>
              )}

            </>
  );
}
