"use client";
// 카페 소통·육성 탭 — 댓글 작업 / 아이디 풀·가입 카페 매핑 / 예약 육성.
// 상태·핸들러는 page 에서 useCafeAuto() 로 만든 객체(s)를 받아 공유한다.
export default function NurtureTab({ s }) {
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
  } = s;

  return (
    <>
            {/* 블로그·카페 포스팅과 동일한 2단 레이아웃: 좌측 = 작업 실행(댓글·예약 등록), 우측 = 관리 목록 */}
            <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start", flexWrap: "wrap" }}>
            <div style={{ flex: "1.5 1 480px", minWidth: 0, display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <div style={{ padding: "1rem", background: "#eff6ff", color: "#1e3a8a", border: "1px solid #bfdbfe", borderRadius: "8px" }}>
                💬 <b>댓글 작업(여론 형성·품앗이)</b>: 입력된 게시글 URL들을 선택한 여러 네이버 아이디로 차례대로 방문하여, 지정된 키워드의 뉘앙스로 자연스러운 호응 댓글을 작성합니다.
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
                  {loading ? "작업 중..." : "🚀 다중 타겟 댓글 작업 시작"}
                </button>
                {loading && (
                  <button onClick={handleCancelTask} style={{ padding: "1rem 2rem", background: "#ef4444", color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", cursor: "pointer" }}>
                    ■ 작업 강제 중지
                  </button>
                )}
              </div>

              <div style={{ padding: "1rem", background: "#fdf2f8", color: "#831843", border: "1px solid #fbcfe8", borderRadius: "8px" }}>
⚙️ <b>육성 예약</b>: 예약을 등록하면 백그라운드 서버가 매일 자동으로 게시글 방문(조회수) 등 육성 작업을 수행합니다. (아이디 풀·카페 매핑은 우측에서 관리)
              </div>

              {/* 육성 예약 등록 (폼) */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>4. 일일 자동 방문(육성) 예약 등록</h2>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
                  <select value={newSchAccId} onChange={e => {
                    setNewSchAccId(e.target.value); setNewSchCafeId("");
                  }} style={{ padding: "0.5rem" }}>
                    <option value="">계정 선택</option>
                    {accounts.map(acc => <option key={acc.id} value={acc.id}>{acc.naver_id}</option>)}
                  </select>

                  <select value={newSchCafeId} onChange={e => setNewSchCafeId(e.target.value)} style={{ padding: "0.5rem", flex: 1, minWidth: "180px" }} disabled={!newSchAccId}>
                    <option value="">매핑된 카페 선택</option>
                    {accounts.find(a => a.id === newSchAccId)?.cafes.map(cafe => (
                      <option key={cafe.id} value={cafe.id}>{cafe.cafe_url}</option>
                    ))}
                  </select>

                  <input type="time" value={newSchTime} onChange={e => setNewSchTime(e.target.value)} style={{ padding: "0.5rem" }} />
                </div>
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
                  <input type="text" placeholder="대상 게시글 URL (비우면 카페 방문만 = 방문횟수 증가)" value={newSchPostUrl} onChange={e => setNewSchPostUrl(e.target.value)} style={{ padding: "0.5rem", flex: 1, minWidth: "200px" }} />
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
                <div style={{ display: "flex", gap: "1.2rem", alignItems: "center", fontSize: "0.9rem", color: "#475569" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", fontWeight: "bold" }}>
                    <input type="checkbox" checked={newSchDoView} onChange={e => setNewSchDoView(e.target.checked)} /> 👁️ 조회수 올리기(방문)
                  </label>
                  <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>* URL이 있으면 그 글을 방문(조회수). 없으면 카페만 방문(육성). 좋아요는 댓글 작업에서 처리됩니다.</span>
                </div>
              </div>
            </div>

            {/* ── 우측: 관리 목록 (아이디 풀 / 카페 매핑 / 등록된 예약) ── */}
            <div style={{ flex: "1 1 380px", minWidth: 0, display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {/* 1. Account Management */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0 }}>네이버 아이디 풀 관리</h2>
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
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>아이디별 가입 카페 매핑</h2>
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

              {/* 등록된 예약 목록 */}
              <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", marginBottom: "1rem" }}>등록된 육성 예약 ({schedules.length})</h2>
                {schedules.length === 0 && (
                  <div style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8", border: "2px dashed #cbd5e1", borderRadius: "8px", fontSize: "0.9rem", marginBottom: "0.5rem" }}>
                    아직 예약이 없습니다. 좌측 '일일 자동 방문(육성) 예약 등록'에서 추가하세요.
                  </div>
                )}
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
            </div>
            </div>
    </>
  );
}
