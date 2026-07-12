"use client";
import WorkHistory from "../components/WorkHistory";
import ManuscriptLoaderModal from "../components/ManuscriptLoaderModal";
import LibraryPickerModal from "../components/LibraryPickerModal";
import { useCafeAuto } from "./useCafeAuto";
import NurtureTab from "./NurtureTab";
import PostTab from "./PostTab";

export default function CafeAutoPage() {
  const s = useCafeAuto();
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
          <div style={{ display: "flex", gap: "1rem", borderBottom: "2px solid #e2e8f0", overflowX: "auto" }}>
            {[
              { id: "post", label: "정보성 포스팅" },
              { id: "matjip", label: "맛집 포스팅" },
              { id: "nurture", label: "카페 소통·육성" }
            ].map(tab => (
              <button key={tab.id} onClick={() => setMainTab(tab.id)}
                style={{
                  padding: "0.8rem 1.5rem", border: "none", background: "none",
                  fontWeight: "bold", fontSize: "1.05rem", cursor: "pointer",
                  whiteSpace: "nowrap", flexShrink: 0,
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
          
          {/* TAB 1: 정보성 포스팅 / 맛집 포스팅(맛집 모드) — 같은 PostTab 재사용 */}
          {(mainTab === "post" || mainTab === "matjip") && <PostTab s={s} />}

          {/* TAB 2: TARGET MULTI */}
          {mainTab === "nurture" && <NurtureTab s={s} />}

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
