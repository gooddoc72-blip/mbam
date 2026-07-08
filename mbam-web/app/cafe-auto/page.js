"use client";
import WorkHistory from "../components/WorkHistory";
import ManuscriptLoaderModal from "../components/ManuscriptLoaderModal";
import LibraryPickerModal from "../components/LibraryPickerModal";
import { useCafeAuto } from "./useCafeAuto";

export default function CafeAutoPage() {
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
    handleAddSchedule,
    handleDeleteSchedule,
  } = useCafeAuto();

  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "1.5rem", boxSizing: "border-box" }}>
      {/* 이미지 보관함 선택 모달 (공용 컴포넌트) */}
      <LibraryPickerModal
        open={showLibPicker}
        onClose={() => setShowLibPicker(false)}
        onUse={(folder, count) => { setImageFolder(folder); setShowLibPicker(false); alert(`✅ 보관함에서 ${count}장을 발행 이미지로 지정했습니다.`); }}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        
        {/* Header Tabs */}
        <div>
          <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "1rem" }}>카페 포스팅</h1>
          <div style={{ display: "flex", gap: "1rem", borderBottom: "2px solid #e2e8f0" }}>
            {[
              { id: "post", label: "카페 포스팅" },
              { id: "nurture", label: "카페 소통·육성" }
            ].map(tab => (
              <button key={tab.id} onClick={() => setMainTab(tab.id)}
                style={{
                  padding: "0.8rem 1.5rem", border: "none", background: "none",
                  fontWeight: "bold", fontSize: "1.05rem", cursor: "pointer",
                  color: mainTab === tab.id ? "#2563eb" : "#64748b",
                  borderBottom: mainTab === tab.id ? "3px solid #2563eb" : "3px solid transparent",
                  marginBottom: "-2px"
                }}>
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", overflowY: "auto" }}>
          
          {/* TAB 1(병합): 즉시 포스팅 + 계정/카페/예약 육성 */}
          {mainTab === "post" && (
            <>
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#334155" }}>발행 계정 선택</h2>
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
                    <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>계정별 타겟 카페·게시판 매칭</h2>
                    <button onClick={prefillTargets} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>📥 가입 카페 매핑 불러오기</button>
                  </div>

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
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#334155", margin: 0 }}>원고 (키워드)</h2>
                  <button onClick={() => setIsModalOpen(true)} style={{ padding: '0.4rem 0.8rem', background: '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 'bold' }}>
                    ☁️ 웹에서 불러오기
                  </button>
                </div>
                <input type="text" placeholder="타겟 키워드" value={targetKeyword} onChange={e => setTargetKeyword(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem" }} />

                {/* 글감 소스 토글 — 3방식 중 하나만 노출 (블로그 발행과 통일된 방식) */}
                {actionType === "post" && (
                  <div style={{ display: "flex", gap: "0.4rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                    {[["collect", "📥 글감수집에서"], ["write", "✍️ 직접 작성"], ["image", "🖼 이미지로"]].map(([k, label]) => (
                      <button key={k} type="button" onClick={() => setSourceMode(k)}
                        style={{ padding: "0.5rem 1rem", borderRadius: "999px", border: sourceMode === k ? "1px solid #2563eb" : "1px solid #cbd5e1", background: sourceMode === k ? "#2563eb" : "white", color: sourceMode === k ? "white" : "#475569", fontWeight: "bold", fontSize: "0.88rem", cursor: "pointer" }}>
                        {label}
                      </button>
                    ))}
                  </div>
                )}

                {/* 글감수집에서 글감 선택 (제목/본문 자동 채움) */}
                {actionType === "post" && sourceMode === "collect" && (
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
                {actionType === "post" && cafeGenerated.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <p style={{ margin: 0, fontSize: "0.85rem", color: "#7c3aed", fontWeight: "bold" }}>✨ 선택한 계정 수만큼 원고를 생성했습니다. 계정별로 검토·수정 후 발행하세요.</p>
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
                ) : (
                  <>
                    {actionType === "post" && <input type="text" placeholder="직접 제목 작성 시" value={title} onChange={e => setTitle(e.target.value)} style={{ width: "100%", padding: "0.8rem", marginBottom: "1rem" }} />}
                    <textarea placeholder="직접 본문 작성 시 (또는 'AI 원고 생성'으로 미리보기 후 검토)" value={content} onChange={e => setContent(e.target.value)} style={{ width: "100%", height: content ? "260px" : "100px", padding: "0.8rem" }} />
                  </>
                )}
                {actionType === "post" && sourceMode === "image" && (
                  <div style={{ marginTop: "0.8rem", padding: "0.8rem", background: "#f0fdf4", border: "1px dashed #86efac", borderRadius: "8px" }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#166534", marginBottom: "0.4rem" }}>🖼️ 이미지 + 키워드로 글감 만들기</div>
                    <input type="file" accept="image/*" multiple onChange={e => setImageFiles(e.target.files)} style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }} />
                    <button onClick={handleDescribeImages} disabled={isGenerating} style={{ padding: "0.5rem 1rem", background: isGenerating ? "#94a3b8" : "#10b981", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: isGenerating ? "wait" : "pointer", width: "100%" }}>
                      {isGenerating ? "분석 중..." : "🔍 이미지 분석 → 글감 생성"}
                    </button>
                    <button type="button" onClick={() => setShowLibPicker(true)} style={{ marginTop: "0.5rem", padding: "0.5rem 1rem", background: "#7c3aed", color: "white", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer", width: "100%" }}>
                      🗂️ 이미지 보관함에서 가져오기
                    </button>
                    {imageFolder && <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#16a34a" }}>✅ 첨부 이미지가 발행 글에도 함께 들어갑니다.</p>}
                    <p style={{ margin: "0.4rem 0 0", fontSize: "0.78rem", color: "#64748b" }}>키워드(위 '타겟 키워드') + 첨부 이미지를 AI가 보고 글감을 만든 뒤, 아래 'AI 원고 생성'으로 원고를 만듭니다.</p>
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

              <div style={{ display: "flex", gap: "1rem" }}>
                <button onClick={handleStartSingle} disabled={loading} style={{ flex: 1, padding: "1rem", background: loading ? "#94a3b8" : "#2563eb", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: loading ? "wait" : "pointer" }}>
                  {loading ? "작업 중..." : "일반 작업 시작하기"}
                </button>
                {loading && (
                  <button onClick={handleCancelTask} style={{ padding: "1rem 2rem", background: "#ef4444", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer" }}>
                    ■ 작업 강제 중지
                  </button>
                )}
              </div>
            </>
          )}

          {/* TAB 2: TARGET MULTI */}
          {mainTab === "nurture" && (
            <>
              <div style={{ padding: "1rem", background: "#eff6ff", color: "#1e3a8a", border: "1px solid #bfdbfe", borderRadius: "8px" }}>
                💬 <b>댓글 작업(여론 형성·품앗이)</b>: 입력된 게시글 URL들을 선택한 여러 네이버 아이디로 차례대로 방문하여, 지정된 키워드의 뉘앙스로 자연스러운 호응 댓글을 작성합니다. <span style={{ color: "#64748b" }}>(아래에 좋아요·조회수 부스트 / 가입 카페 매핑 / 예약 육성도 함께 있습니다)</span>
              </div>
              
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>1. 참여할 계정 선택</h2>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {accounts.map(acc => (
                    <label key={acc.id} style={{ padding: "0.5rem 1rem", border: "1px solid #cbd5e1", borderRadius: "20px", cursor: "pointer", background: selectedAccounts.includes(acc.id) ? "#2563eb" : "white", color: selectedAccounts.includes(acc.id) ? "white" : "black" }}>
                      <input type="checkbox" style={{ display: "none" }} checked={selectedAccounts.includes(acc.id)} onChange={() => toggleAccountSelection(acc.id)} />
                      {acc.naver_id}
                    </label>
                  ))}
                  {accounts.length === 0 && <span style={{ color: "#94a3b8" }}>'아이디 육성' 탭(또는 설정 &gt; 계정관리)에서 아이디를 먼저 등록해주세요.</span>}
                </div>
              </div>

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>2. 타겟 게시글 URL 입력</h2>
                <textarea placeholder="댓글을 달 게시글 URL을 한 줄에 하나씩 입력하세요." value={targetUrls} onChange={e => setTargetUrls(e.target.value)} style={{ width: "100%", height: "120px", padding: "0.8rem", border: "1px solid #cbd5e1" }} />
              </div>

              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "0.5rem" }}>3. 댓글 내용 (직접 입력)</h2>
                <p style={{ margin: "0 0 0.6rem", fontSize: "0.85rem", color: "#64748b" }}>달 댓글을 직접 입력하세요. <b>한 줄에 하나씩 여러 개</b>를 넣으면 게시글마다 <b>무작위로 하나</b>를 골라 자연스럽게 답니다. (비워두면 AI가 자동 생성)</p>
                <textarea placeholder={"예시(한 줄에 하나씩):\n너무 맛있어 보이네요 저도 가보고 싶어요\n사진만 봐도 군침 도네요 ㅎㅎ\n정보 감사합니다 꼭 가볼게요"} value={targetMultiKeyword} onChange={e => setTargetMultiKeyword(e.target.value)} style={{ width: "100%", height: "110px", padding: "0.8rem", marginBottom: "1rem", border: "1px solid #cbd5e1", borderRadius: "4px", fontFamily: "inherit" }} />
                
                <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                  <span>게시글 간 대기시간 (초):</span>
                  <input type="number" value={delayMin} onChange={e => setDelayMin(e.target.value)} style={{ width: "80px", padding: "0.5rem" }} />
                  <span>~</span>
                  <input type="number" value={delayMax} onChange={e => setDelayMax(e.target.value)} style={{ width: "80px", padding: "0.5rem" }} />
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem", cursor: "pointer", fontWeight: "bold", color: targetMultiLike ? "#e11d48" : "#64748b" }}>
                  <input type="checkbox" checked={targetMultiLike} onChange={e => setTargetMultiLike(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                  ❤️ 댓글과 함께 좋아요 누르기 (게시글에 공감 + 댓글)
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.6rem", cursor: "pointer", fontWeight: "bold", color: useTethering ? "#3b82f6" : "#64748b" }}>
                  <input type="checkbox" checked={useTethering} onChange={e => setUseTethering(e.target.checked)} style={{ transform: "scale(1.2)" }} />
                  📶 USB 테더링 IP 우회 (계정마다 비행기모드 토글로 새 IP 할당 — ADB 연결된 폰 필요)
                </label>
              </div>
              
              <div style={{ display: "flex", gap: "1rem" }}>
                <button onClick={handleStartTargetMulti} disabled={loading} style={{ flex: 1, padding: "1rem", background: loading ? "#94a3b8" : "#0f172a", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: loading ? "wait" : "pointer" }}>
                  {loading ? "작업 중..." : "다중 타겟 댓글 작업 시작"}
                </button>
                {loading && (
                  <button onClick={handleCancelTask} style={{ padding: "1rem 2rem", background: "#ef4444", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer" }}>
                    ■ 작업 강제 중지
                  </button>
                )}
              </div>
            </>
          )}

          {/* 아이디 육성: 계정 풀/가입 카페 매핑 + 일일 자동 방문(육성) 스케줄 */}
          {mainTab === "nurture" && (
            <>
              <div style={{ padding: "1rem", background: "#fdf2f8", color: "#831843", border: "1px solid #fbcfe8", borderRadius: "8px" }}>
⚙️ <b>육성 설정 & 예약</b>: 아래에서 네이버 아이디 풀을 관리하고 가입 카페를 매핑한 뒤, 예약을 등록하면 백그라운드 서버가 매일 자동으로 게시글 방문(조회수)·좋아요 등 육성 작업을 수행합니다.
              </div>

              {/* 1. Account Management */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0 }}>1. 네이버 아이디 풀 관리</h2>
                  <button onClick={fetchAccounts} style={{ padding: "0.4rem 0.8rem", background: "#10b981", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold", fontSize: "0.85rem" }}>📥 계정관리에서 불러오기</button>
                </div>
                <p style={{ margin: "0 0 0.8rem", fontSize: "0.82rem", color: "#64748b" }}>여기 목록은 <b>계정관리(전체 계정)</b>와 동일합니다. 여기서 추가/삭제하면 계정관리에도 반영됩니다.</p>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                  <input type="text" placeholder="네이버 아이디" value={newAccId} onChange={e => setNewAccId(e.target.value)} style={{ padding: "0.5rem" }} />
                  <input type="password" placeholder="비밀번호" value={newAccPw} onChange={e => setNewAccPw(e.target.value)} style={{ padding: "0.5rem" }} />
                  <button onClick={handleAddAccount} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none" }}>추가</button>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>ID</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>상태</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>기기 인증</th>
                      <th style={{ padding: "0.5rem", textAlign: "center" }}>관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map(acc => (
                      <tr key={acc.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                        <td style={{ padding: "0.5rem" }}>{acc.naver_id}</td>
                        <td style={{ padding: "0.5rem" }}>
                          <span style={{ background: "#dcfce7", color: "#166534", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>{acc.status}</span>
                        </td>
                        <td style={{ padding: "0.5rem" }}>
                          {registeredIds.includes(acc.naver_id) ? (
                            <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="기기 인증 완료됨. 다시 인증하려면 클릭하세요." style={{ padding: "0.3rem 0.6rem", background: "#dcfce7", color: "#166534", border: "1px solid #86efac", borderRadius: "4px", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap", fontWeight: "bold" }}>✅ 인증완료</button>
                          ) : (
                            <button onClick={() => handleRegisterAccount(acc)} disabled={loading} title="최초 1회 수동 로그인+2단계 인증으로 기기를 등록하면 이후 자동 로그인됩니다." style={{ padding: "0.3rem 0.6rem", background: "#fef3c7", color: "#b45309", border: "1px solid #fcd34d", borderRadius: "4px", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap" }}>🔐 기기 인증</button>
                          )}
                        </td>
                        <td style={{ padding: "0.5rem", textAlign: "center" }}>
                          <button onClick={() => handleDeleteAccount(acc)} title="계정을 풀에서 삭제" style={{ padding: "0.3rem 0.6rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer", whiteSpace: "nowrap" }}>삭제</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 2. Cafe Mapping */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>2. 아이디별 가입 카페 매핑</h2>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                  <select value={newCafeAccId} onChange={e => setNewCafeAccId(e.target.value)} style={{ padding: "0.5rem" }}>
                    <option value="">계정 선택</option>
                    {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                  </select>
                  <input type="text" placeholder="카페 주소 URL" value={newCafeUrl} onChange={e => setNewCafeUrl(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} />
                  <button onClick={handleAddCafe} style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none" }}>등록</button>
                </div>
                <ul style={{ paddingLeft: "1.5rem", margin: 0, fontSize: "0.9rem" }}>
                  {accounts.map(acc => (
                    acc.cafes && acc.cafes.map(cafe => (
                      <li key={cafe.id} style={{ marginBottom: "0.3rem" }}>
                        <strong>{acc.naver_id}</strong> ➔ {cafe.cafe_url}
                      </li>
                    ))
                  ))}
                </ul>
              </div>

              {/* 3. Scheduling */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>3. 일일 자동 방문(육성) 스케줄</h2>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <select value={newSchAccId} onChange={e => {
                    setNewSchAccId(e.target.value); setNewSchCafeId("");
                  }} style={{ padding: "0.5rem" }}>
                    <option value="">계정 선택</option>
                    {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                  </select>
                  
                  <select value={newSchCafeId} onChange={e => setNewSchCafeId(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} disabled={!newSchAccId}>
                    <option value="">매핑된 카페 선택</option>
                    {accounts.find(a => a.id === newSchAccId)?.cafes.map(cafe => (
                      <option key={cafe.id} value={cafe.id}>{cafe.cafe_url}</option>
                    ))}
                  </select>

                  <input type="time" value={newSchTime} onChange={e => setNewSchTime(e.target.value)} style={{ padding: "0.5rem" }} />
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem", alignItems: "center" }}>
                  <input type="text" placeholder="대상 게시글 URL (비우면 카페 방문만 = 방문횟수 증가)" value={newSchPostUrl} onChange={e => setNewSchPostUrl(e.target.value)} style={{ padding: "0.5rem", flex: 1 }} />
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.2rem'}}>
                    <span style={{fontSize: '0.9rem'}}>일일 방문수</span>
                    <input type="number" min="1" value={newSchCount} onChange={e => setNewSchCount(e.target.value)} style={{ padding: "0.5rem", width: "60px" }} />
                  </div>
                  <div style={{display: 'flex', alignItems: 'center', gap: '0.2rem'}}>
                    <span style={{fontSize: '0.9rem'}}>방문 간격</span>
                    <input type="number" min="0" value={newSchInterval} onChange={e => setNewSchInterval(e.target.value)} style={{ padding: "0.5rem", width: "60px" }} />
                    <span style={{fontSize: '0.9rem'}}>분</span>
                  </div>
                  <button onClick={handleAddSchedule} style={{ padding: "0.5rem 1rem", background: "#0f172a", color: "white", border: "none" }}>예약</button>
                </div>
                <div style={{ display: "flex", gap: "1.2rem", marginBottom: "1rem", alignItems: "center", fontSize: "0.9rem", color: "#475569" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", fontWeight: "bold" }}>
                    <input type="checkbox" checked={newSchDoView} onChange={e => setNewSchDoView(e.target.checked)} /> 👁️ 조회수 올리기(방문)
                  </label>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>* URL이 있으면 그 글을 방문(조회수). 없으면 카페만 방문(육성). 좋아요는 댓글 작업에서 처리됩니다.</span>
                </div>
                
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "2px solid #cbd5e1" }}>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>실행 시간</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>대상 계정</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>대상 카페</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>작업 내용</th>
                      <th style={{ padding: "0.5rem", textAlign: "left" }}>상태</th>
                      <th style={{ padding: "0.5rem", textAlign: "center" }}>관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedules.map(sch => (
                      <tr key={sch.id} style={{ borderBottom: "1px solid #e2e8f0" }}>
                        <td style={{ padding: "0.5rem", fontWeight: "bold" }}>매일 {sch.schedule_time}</td>
                        <td style={{ padding: "0.5rem" }}>{sch.naver_id}</td>
                        <td style={{ padding: "0.5rem" }}>{sch.cafe_url}{sch.board_name ? ` (${sch.board_name})` : ""}</td>
                        <td style={{ padding: "0.5rem", fontSize: "0.85rem", color: "#475569" }}>
                          {sch.target_post_url
                            ? <span>🎯 게시글 부스트 (방문 {sch.post_count_per_day}회/{sch.visit_interval_min ?? 30}분 간격{sch.do_view ? ", 조회수" : ""}{sch.do_like ? ", ❤️좋아요" : ""})<br/><span style={{ color: "#2563eb", fontSize: "0.78rem", wordBreak: "break-all" }}>{sch.target_post_url}</span></span>
                            : (sch.content_category
                                ? `${sch.content_category}${sch.content_item_title ? ` - ${sch.content_item_title}` : ''} (${sch.post_count_per_day}회)`
                                : `🚶 일반 육성 (카페 방문 ${sch.post_count_per_day}회/${sch.visit_interval_min ?? 30}분 간격)`)}
                        </td>
                        <td style={{ padding: "0.5rem" }}>
                          <span style={{ background: sch.is_active ? "#dcfce7" : "#f1f5f9", color: sch.is_active ? "#166534" : "#64748b", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
                            {sch.is_active ? "활성화" : "정지"}
                          </span>
                        </td>
                        <td style={{ padding: "0.5rem", textAlign: "center" }}>
                          <button onClick={() => handleDeleteSchedule(sch.id)} title="예약 삭제" style={{ padding: "0.3rem 0.6rem", background: "white", color: "#ef4444", border: "1px solid #ef4444", borderRadius: "4px", cursor: "pointer", whiteSpace: "nowrap" }}>삭제</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

        </div>
      </div>

      <div style={{ width: "100%", height: "320px", background: "#1e293b", border: "1px solid #0f172a", display: "flex", flexDirection: "column", color: "#f8fafc", borderRadius: "8px", overflow: "hidden" }}>
        <div style={{ padding: "1rem", borderBottom: "1px solid #334155", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0, color: "#f8fafc" }}>실시간 모니터링 로그</h2>
          {taskStatus === "running" && <span style={{ color: "#34d399", fontSize: "0.8rem" }}>● Running</span>}
          {taskStatus === "completed" && <span style={{ color: "#60a5fa", fontSize: "0.8rem" }}>✓ Completed</span>}
          {taskStatus === "failed" && <span style={{ color: "#f87171", fontSize: "0.8rem" }}>✕ Failed</span>}
        </div>
        <div style={{ flex: 1, padding: "1rem", overflowY: "auto", fontFamily: "monospace", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {statusLogs.length === 0 ? (
            <div style={{ color: "#94a3b8" }}>대기 중... 작업을 시작하면 로그가 표시됩니다.</div>
          ) : (
            statusLogs.map((log, i) => (
              <div key={i} style={{ color: log.includes("✅") ? "#34d399" : log.includes("⚠️") ? "#fbbf24" : "#cbd5e1" }}>
                {log}
              </div>
            ))
          )}
        </div>
      </div>

      <ManuscriptLoaderModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSelect={handleLoadManuscript}
      />
      <WorkHistory menuKey="cafe-auto" />
    </div>
  );
}
