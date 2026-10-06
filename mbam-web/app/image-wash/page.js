"use client";
import { useState, useRef, useEffect } from "react";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import { fetchWithAuth } from "../utils/api";
import { usePersistentState } from "../utils/persistentState";
import { addHistory } from "../utils/workHistory";
import WorkHistory from "../components/WorkHistory";
import { Plus, Check, Download, Info } from "lucide-react";

export default function ImageWashPage() {
  const [files, setFiles] = useState([]);
  const [selectedFileIndex, setSelectedFileIndex] = useState(0);
  // 세탁 진행/결과는 전역 보관 — 메뉴 이동해도 처리 계속·복귀 시 결과 유지
  const [loading, setLoading] = usePersistentState("image-wash:loading", false);
  const [results, setResults] = usePersistentState("image-wash:results", []); // List of { original_filename, base64_data }
  const fileInputRef = useRef(null);

  // Settings state
  const [count, setCount] = useState(10);
  const [exifSetting, setExifSetting] = useState("촬영일시 ±10일 랜덤 / 카메라 모델 랜덤");
  const [useBorder, setUseBorder] = useState(false);
  const [useNoise, setUseNoise] = useState(true);
  const [useWatermark, setUseWatermark] = useState(false);
  const [useRotation, setUseRotation] = useState(false);
  // 원본 해상도 그대로 세탁하면 매우 느리다(휴대폰 사진 10장 = 약 23초).
  // 기본은 긴 변 1600px 로 줄여 처리(10장 2초 내외). 원본이 꼭 필요할 때만 켠다.
  const [keepOriginalSize, setKeepOriginalSize] = useState(false);

  // 세탁 방식 — 어떤 처리를 걸지 직접 고른다.
  // 기본값은 예전 동작과 같다(크롭·노이즈·밝기·EXIF 켜짐). 건드리지 않으면 결과가 그대로다.
  const [useCrop, setUseCrop] = useState(true);
  const [useBrightContrast, setUseBrightContrast] = useState(true);
  const [useExif, setUseExif] = useState(true);
  const [useFlip, setUseFlip] = useState(false);
  const [useHue, setUseHue] = useState(false);
  const [useResample, setUseResample] = useState(false);

  // 이미지 보관함 (세탁 후 저장 → 발행 재사용)
  const [library, setLibrary] = useState([]);
  const [libMeta, setLibMeta] = useState({ max_files: 30, ttl_days: 14 });
  const [savingLib, setSavingLib] = useState(false);

  const loadLibrary = async () => {
    try {
      const res = await fetchWithAuth("/api/image-wash/library");
      if (res.ok) { const d = await res.json(); setLibrary(d.items || []); setLibMeta({ max_files: d.max_files || 30, ttl_days: d.ttl_days || 14 }); }
    } catch (e) {}
  };
  useEffect(() => { loadLibrary(); }, []);

  const saveToLibrary = async () => {
    if (!results.length) { alert("먼저 이미지를 세탁해주세요."); return; }
    setSavingLib(true);
    try {
      const res = await fetchWithAuth("/api/image-wash/library/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images: results.map(r => r.base64_data) })
      });
      const d = await res.json();
      if (res.ok && d.success) { alert(`✅ ${d.saved}장을 보관함에 저장했습니다.`); loadLibrary(); }
      else alert("저장에 실패했습니다.");
    } catch (e) { alert("저장 중 오류: " + e.message); }
    finally { setSavingLib(false); }
  };

  const deleteFromLibrary = async (filename) => {
    if (!confirm("이 이미지를 보관함에서 삭제할까요?")) return;
    try {
      const res = await fetchWithAuth(`/api/image-wash/library/${encodeURIComponent(filename)}`, { method: "DELETE" });
      if (res.ok) loadLibrary();
    } catch (e) {}
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
  };

  const addFiles = (fileList) => {
    const newFiles = Array.from(fileList).filter(f => f.type.startsWith('image/'));
    const mappedFiles = newFiles.map(file => ({
      file,
      preview: URL.createObjectURL(file),
      name: file.name,
      size: (file.size / 1024).toFixed(1) + " KB",
      type: file.type
    }));
    setFiles(prev => [...prev, ...mappedFiles]);
  };

  const handleGenerate = async () => {
    if (files.length === 0) {
      alert("원본 이미지를 추가해주세요.");
      return;
    }

    setLoading(true);
    setResults([]);

    const formData = new FormData();
    files.forEach(f => {
      formData.append("files", f.file);
    });
    formData.append("count", count);
    formData.append("use_border", useBorder);
    formData.append("use_noise", useNoise);
    formData.append("use_watermark", useWatermark);
    formData.append("use_rotation", useRotation);
    formData.append("keep_original_size", keepOriginalSize);
    formData.append("use_crop", useCrop);
    formData.append("use_bright_contrast", useBrightContrast);
    formData.append("use_exif", useExif);
    formData.append("use_flip", useFlip);
    formData.append("use_hue", useHue);
    formData.append("use_resample", useResample);

    try {
      const res = await fetchWithAuth("/api/image-wash/upload", {
        method: "POST",
        body: formData, // fetchWithAuth shouldn't stringify FormData
      });

      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          setResults(data.results);
          try { addHistory("image-wash", { summary: `이미지 세탁 ${(data.results || []).length}장` }); } catch (e) {}
        } else {
          alert("변환 실패: " + data.message);
        }
      } else {
        alert(`서버 에러: ${res.status}`);
      }
    } catch (e) {
      alert("오류 발생: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadAll = () => {
    if (results.length === 0) return;
    const zip = new JSZip();
    results.forEach((res, i) => {
      const base64Data = res.base64_data.split(',')[1];
      zip.file(res.washed_filename, base64Data, {base64: true});
    });
    zip.generateAsync({type:"blob"}).then(function(content) {
      saveAs(content, "washed_images.zip");
    });
  };

  const handleDownloadSelected = () => {
    if (results.length === 0) return;
    const selectedRes = results[selectedFileIndex % results.length];
    if(selectedRes) {
      saveAs(selectedRes.base64_data, selectedRes.washed_filename);
    }
  };

  const selectedOriginal = files[selectedFileIndex];
  const relatedResult = results.find(r => r.original_filename === selectedOriginal?.name) || results[0];

  return (
    <div style={{ padding: "2rem", backgroundColor: "#f8fafc", minHeight: "100vh" }}>
      <h1 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#1e293b", marginBottom: "0.5rem" }}>이미지 일괄 편집기</h1>
      <p style={{ color: "#64748b", marginBottom: "2rem" }}>수동: 최대 10개 이미지 (각 5MB 이하) / 자동: 블로그 캠페인 수량만큼 일괄 생성</p>

      <div className="iw-row" style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start", flexWrap: "wrap" }}>
        
        {/* Left Panel: Files */}
        <div style={{ width: "220px", display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div 
            onClick={() => fileInputRef.current?.click()}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            style={{ 
              border: "2px dashed #cbd5e1", borderRadius: "8px", padding: "2rem 1rem", 
              textAlign: "center", cursor: "pointer", backgroundColor: "white",
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"
            }}
          >
            <Plus size={24} color="#94a3b8" style={{ marginBottom: "0.5rem" }}/>
            <span style={{ fontSize: "0.9rem", color: "#475569" }}>원본 이미지 추가<br/>(드래그 또는 클릭)</span>
            {files.length > 0 && <span style={{ fontSize: "0.8rem", color: "#3b82f6", marginTop: "0.5rem", fontWeight: "bold" }}>{files.length}장</span>}
          </div>
          <input type="file" multiple accept="image/*" ref={fileInputRef} onChange={handleFileInput} style={{ display: "none" }} />

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "400px", overflowY: "auto" }}>
            {files.map((f, i) => (
              <div 
                key={i} 
                onClick={() => setSelectedFileIndex(i)}
                style={{ 
                  height: "60px", borderRadius: "8px", overflow: "hidden", position: "relative", cursor: "pointer",
                  border: selectedFileIndex === i ? "2px solid #4f46e5" : "2px solid transparent",
                  backgroundImage: `url(${f.preview})`, backgroundSize: "cover", backgroundPosition: "center"
                }}
              >
                <div style={{ position: "absolute", top: "4px", right: "4px", width: "16px", height: "16px", borderRadius: "50%", backgroundColor: "#22c55e", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Check size={12} color="white" />
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "1rem" }}>
            <button onClick={handleDownloadSelected} style={{ padding: "0.8rem", backgroundColor: "#3b82f6", color: "white", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}>
              선택 저장
            </button>
            <button onClick={handleDownloadAll} style={{ padding: "0.8rem", backgroundColor: "#16a34a", color: "white", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: "pointer" }}>
              ⬇️ 내 PC로 다운로드 ({results.length}장)
            </button>
            <button onClick={saveToLibrary} disabled={savingLib || results.length === 0} style={{ padding: "0.8rem", backgroundColor: savingLib ? "#a78bfa" : "#7c3aed", color: "white", border: "none", borderRadius: "4px", fontWeight: "bold", cursor: savingLib ? "wait" : "pointer" }}>
              {savingLib ? "저장 중..." : `💾 보관함에 저장 (${results.length}장)`}
            </button>
            {results.length > 0 && <div style={{ textAlign: "center", fontSize: "0.85rem", color: "#16a34a", fontWeight: "bold" }}>{results.length}장 생성 완료</div>}
          </div>
        </div>

        {/* Center Panel: Settings */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "1rem" }}>

          <div style={{ backgroundColor: "#f8faff", border: "1px solid #dbeafe", borderRadius: "8px", padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#1e3a8a", margin: 0, whiteSpace: "nowrap" }}>자동 대량 생성</h2>
              <span style={{ backgroundColor: "#dbeafe", color: "#2563eb", padding: "0.2rem 0.5rem", borderRadius: "4px", fontSize: "0.8rem", whiteSpace: "nowrap" }}>블로그 캠페인용</span>
            </div>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "1.5rem", lineHeight: 1.5 }}>
              원본 이미지를 순환하며 N장을 생성합니다. 아래 <b>세탁 방식 선택</b>에서 고른 처리가 장마다 조금씩 다른 강도로 적용되어, 결과물끼리도 서로 달라집니다.
            </p>

            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
              <span style={{ fontWeight: "bold", color: "#334155", whiteSpace: "nowrap" }}>생성 수량</span>
              <input 
                type="number" 
                value={count} 
                onChange={e => setCount(parseInt(e.target.value))} 
                style={{ width: "80px", padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "4px", textAlign: "center" }}
              />
              <span style={{ color: "#64748b", whiteSpace: "nowrap" }}>장 (최대 200)</span>
            </div>

            <div style={{ padding: "0.8rem 1rem", border: "1px solid #cbd5e1", borderRadius: "4px", backgroundColor: "white", marginBottom: "1.5rem", fontSize: "0.9rem", color: "#334155" }}>
              <strong style={{ color: "#16a34a" }}>EXIF 자동 삽입</strong> — {exifSetting}
            </div>

            <button 
              onClick={handleGenerate}
              disabled={loading || files.length === 0}
              style={{ 
                width: "100%", padding: "1.2rem", backgroundColor: loading ? "#94a3b8" : "#4f46e5", 
                color: "white", fontWeight: "bold", fontSize: "1.1rem", border: "none", borderRadius: "6px", 
                cursor: loading || files.length === 0 ? "not-allowed" : "pointer",
                boxShadow: "0 4px 6px -1px rgba(79, 70, 229, 0.2)"
              }}
            >
              {loading ? "생성 중..." : `${count}장 자동 생성`}
            </button>
          </div>

          {/* 세탁 방식 선택 — 적용할 처리를 하나씩 고른다.
              '강함/보통/약함' 은 이미지 판별값(pHash)을 얼마나 흔드는지다.
              크롭이 유일하게 확실히 흔드는 처리라, 끄면 경고를 띄운다. */}
          <div style={{ backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.2rem" }}>
            <div style={{ marginBottom: "0.4rem", fontSize: "1.05rem", fontWeight: "bold", color: "#1e293b" }}>세탁 방식 선택</div>
            <div style={{ marginBottom: "1rem", fontSize: "0.85rem", color: "#64748b", lineHeight: 1.5 }}>
              적용할 처리를 직접 고릅니다. 괄호 안은 <b>같은 사진인지 가려내는 판별값(pHash)</b>이 실제로 얼마나 바뀌는지 측정한 값입니다(64 중).
              <br />구도를 바꾸는 <b>크롭·좌우반전·미세회전</b>만 판별값을 움직입니다. 나머지는 파일 내용과 색 분포만 바꿔 <b>같은 파일 검사</b>를 피하는 용도입니다.
            </div>

            {/* 크롭과 좌우반전 둘 다 꺼져 있을 때만 경고한다 — 반전만 켜도 판별값은 충분히 바뀐다. */}
            {!useCrop && !useFlip && (
              <div style={{ marginBottom: "1rem", padding: "0.8rem 1rem", backgroundColor: "#fef2f2", border: "1px solid #fecaca", borderRadius: "6px", fontSize: "0.85rem", color: "#b91c1c", lineHeight: 1.5 }}>
                ⚠️ 크롭이 꺼져 있습니다. 노이즈·밝기·색조·리샘플링은 판별값을 <b>전혀 바꾸지 못합니다(측정값 0).</b> 크롭이나 좌우반전 중 하나는 켜야 원본과 다른 사진으로 인식됩니다.
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {[
              { label: "가장자리 크롭 5~8%", state: useCrop, setter: setUseCrop, impact: "강함 16~20",
                desc: "네 변을 조금씩 잘라 구도를 바꿉니다. 사진이 어색해지지 않으면서 판별값을 확실히 바꾸는 처리라 켜두시길 권합니다." },
              { label: "좌우반전", state: useFlip, setter: setUseFlip, impact: "가장 강함 32",
                desc: "좌우를 뒤집습니다. 판별값이 가장 크게 바뀌지만, 간판·글자·사람이 찍힌 사진은 뒤집힌 티가 바로 납니다." },
              { label: "미세회전", state: useRotation, setter: setUseRotation, impact: "보통 2~6",
                desc: "±0.5~2° 돌립니다. 크롭과 함께 쓰면 회전으로 생긴 여백이 함께 잘려나갑니다." },
              { label: "노이즈", state: useNoise, setter: setUseNoise, impact: "파일만 0",
                desc: "미세한 블러를 섞습니다. 판별값은 바뀌지 않지만 파일 내용이 달라져 같은 파일(해시) 검사를 피합니다." },
              { label: "밝기·대비 미세변형", state: useBrightContrast, setter: setUseBrightContrast, impact: "파일만 0",
                desc: "±2% 안에서 조정합니다. 눈으로도 판별값으로도 차이가 없고, 파일 내용만 달라집니다." },
              { label: "색조 미세이동", state: useHue, setter: setUseHue, impact: "파일만 0~2",
                desc: "색상을 아주 조금 돌립니다. 같은 색으로 보이지만 색 분포가 달라져, 색으로 비교하는 검사에 대응합니다." },
              { label: "리사이즈 재샘플링", state: useResample, setter: setUseResample, impact: "파일만 0",
                desc: "살짝 줄였다 되돌려 픽셀 격자를 새로 계산합니다. 크기는 그대로고, 원본의 압축 흔적이 지워집니다." },
              { label: "촬영정보(EXIF) 교체", state: useExif, setter: setUseExif, impact: "정보",
                desc: "촬영일시를 오늘 기준 ±10일, 카메라 모델을 랜덤으로 바꿉니다. 픽셀은 건드리지 않습니다." },
            ].map((opt, i) => (
              <label key={i} style={{ display: "flex", alignItems: "flex-start", padding: "0.8rem", backgroundColor: opt.state ? "#f5f3ff" : "#f8fafc", border: `1px solid ${opt.state ? "#c4b5fd" : "#e2e8f0"}`, borderRadius: "6px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={opt.state}
                  onChange={e => opt.setter(e.target.checked)}
                  style={{ width: "18px", height: "18px", marginRight: "0.8rem", marginTop: "0.1rem", cursor: "pointer", flexShrink: 0 }}
                />
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.95rem", fontWeight: "bold", color: "#334155" }}>{opt.label}</span>
                    {/* 색은 판별값을 실제로 바꾸는 정도에 맞춘다 — 강함(분홍) / 보통(주황) / 그 외(회색) */}
                    <span style={{ fontSize: "0.7rem", fontWeight: "bold", padding: "0.1rem 0.45rem", borderRadius: "999px",
                                   color: /^(강함|가장)/.test(opt.impact) ? "#9d174d" : /^보통/.test(opt.impact) ? "#9a3412" : "#475569",
                                   backgroundColor: /^(강함|가장)/.test(opt.impact) ? "#fce7f3" : /^보통/.test(opt.impact) ? "#ffedd5" : "#e2e8f0" }}>
                      {opt.impact}
                    </span>
                  </div>
                  <div style={{ marginTop: "0.25rem", fontSize: "0.82rem", color: "#64748b", lineHeight: 1.5 }}>{opt.desc}</div>
                </div>
              </label>
            ))}
            </div>
          </div>

          {/* 그 밖의 옵션 — 세탁 강도와는 무관한 장식·성능 설정 */}
          {[
            { label: "테두리", state: useBorder, setter: setUseBorder, desc: "(바깥에 5px 밝은색 테두리를 두릅니다)" },
            { label: "워터마크", state: useWatermark, setter: setUseWatermark, desc: "(준비 중 — 켜도 아직 적용되지 않습니다)" },
            { label: "원본 크기 유지", state: keepOriginalSize, setter: setKeepOriginalSize,
              desc: "(끄면 긴 변 1600px 로 줄여 처리 — 10장 기준 23초 → 2초. 카페 업로드에는 1600px 로 충분합니다)" },
          ].map((opt, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", padding: "1.2rem", backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px", flexWrap: "wrap" }}>
              <input
                type="checkbox"
                checked={opt.state}
                onChange={e => opt.setter(e.target.checked)}
                style={{ width: "18px", height: "18px", marginRight: "1rem", cursor: "pointer" }}
              />
              <span style={{ fontSize: "1rem", fontWeight: "bold", color: "#334155", whiteSpace: "nowrap" }}>{opt.label}</span>
              {opt.desc && <span style={{ marginLeft: "0.5rem", fontSize: "0.9rem", color: "#94a3b8" }}>{opt.desc}</span>}
            </div>
          ))}

        </div>

        {/* Right Panel: Preview & Info */}
        <div style={{ width: "320px", display: "flex", flexDirection: "column", gap: "1rem" }}>
          
          <div style={{ backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0, color: "#1e293b", whiteSpace: "nowrap" }}>미리보기</h3>
              <button style={{ padding: "0.4rem 0.8rem", backgroundColor: "#3b82f6", color: "white", border: "none", borderRadius: "4px", fontSize: "0.85rem", cursor: "pointer", whiteSpace: "nowrap" }}>미리보기 생성</button>
            </div>

            {selectedOriginal ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div>
                  <div style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "0.5rem" }}>원본</div>
                  <div style={{ width: "100%", height: "200px", border: "1px solid #e2e8f0", borderRadius: "4px", backgroundImage: `url(${selectedOriginal.preview})`, backgroundSize: "contain", backgroundRepeat: "no-repeat", backgroundPosition: "center" }} />
                </div>
                <div>
                  <div style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "0.5rem" }}>처리 결과</div>
                  <div style={{ width: "100%", height: "200px", border: "1px solid #e2e8f0", borderRadius: "4px", backgroundImage: relatedResult ? `url(${relatedResult.base64_data})` : 'none', backgroundColor: "#f8fafc", backgroundSize: "contain", backgroundRepeat: "no-repeat", backgroundPosition: "center", display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: "0.9rem" }}>
                    {!relatedResult && "아직 변환되지 않았습니다"}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ height: "400px", display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8", fontSize: "0.9rem", border: "1px dashed #cbd5e1", borderRadius: "4px" }}>
                이미지를 선택해주세요
              </div>
            )}
            
            {results.length > 0 && (
              <div style={{ marginTop: "1rem", padding: "0.8rem", backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", color: "#16a34a", borderRadius: "4px", textAlign: "center", fontSize: "0.9rem", fontWeight: "bold" }}>
                생성 완료
              </div>
            )}
          </div>

          <div style={{ backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.5rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: "bold", marginBottom: "1rem", color: "#1e293b" }}>선택된 파일 정보</h3>
            {selectedOriginal ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.9rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span style={{ color: "#64748b" }}>파일명</span> <span style={{ color: "#334155", maxWidth: "150px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{selectedOriginal.name}</span></div>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span style={{ color: "#64748b" }}>크기</span> <span style={{ color: "#334155" }}>{selectedOriginal.size}</span></div>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span style={{ color: "#64748b" }}>형식</span> <span style={{ color: "#334155" }}>{selectedOriginal.type}</span></div>
              </div>
            ) : (
              <div style={{ fontSize: "0.9rem", color: "#94a3b8" }}>파일 정보 없음</div>
            )}
          </div>

          <div style={{ backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.5rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: "bold", marginBottom: "1rem", color: "#1e293b" }}>적용 설정 요약</h3>
            {/* 켠 것만 보여준다 — 항목이 늘어나 '비활성'까지 나열하면 무엇을 켰는지 한눈에 안 들어온다. */}
            {(() => {
              const on = [
                useCrop && "가장자리 크롭",
                useNoise && "노이즈",
                useBrightContrast && "밝기·대비",
                useExif && "EXIF 교체",
                useRotation && "미세회전",
                useFlip && "좌우반전",
                useHue && "색조 이동",
                useResample && "재샘플링",
                useBorder && "테두리",
              ].filter(Boolean);
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.9rem", color: "#64748b" }}>
                  <div>선택한 방식 <span style={{ color: "#334155", fontWeight: "bold" }}>{on.length}개</span></div>
                  {on.length === 0 ? (
                    <div style={{ color: "#b91c1c" }}>아무것도 선택하지 않아 원본이 그대로 복사됩니다.</div>
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                      {on.map((name, i) => (
                        <span key={i} style={{ fontSize: "0.8rem", padding: "0.2rem 0.5rem", borderRadius: "4px", backgroundColor: "#eef2ff", color: "#4f46e5", fontWeight: "bold" }}>{name}</span>
                      ))}
                    </div>
                  )}
                  {!useCrop && !useFlip && (
                    <div style={{ color: "#b91c1c" }}>크롭·좌우반전이 모두 꺼져 있어 원본과 같은 이미지로 걸립니다.</div>
                  )}
                  <div style={{ marginTop: "0.25rem", color: "#94a3b8" }}>
                    처리 크기: {keepOriginalSize ? "원본 그대로(느림)" : "긴 변 1600px"}
                  </div>
                  {useExif && <div style={{ color: "#3b82f6" }}>EXIF 날짜 ±10일 랜덤 삽입</div>}
                </div>
              );
            })()}
          </div>

        </div>

      </div>

      {/* 내 이미지 보관함 */}
      <div style={{ marginTop: "2rem", padding: "1.5rem", background: "white", border: "1px solid #e2e8f0", borderRadius: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
          <h2 style={{ margin: 0, fontSize: "1.1rem", color: "#0f172a" }}>🗂️ 내 이미지 보관함 <span style={{ color: "#94a3b8", fontWeight: "normal", fontSize: "0.9rem" }}>({library.length}/{libMeta.max_files}장)</span></h2>
          <button onClick={loadLibrary} style={{ fontSize: "0.85rem", padding: "0.4rem 0.9rem", background: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1", borderRadius: "6px", cursor: "pointer", fontWeight: "bold", whiteSpace: "nowrap" }}>새로고침</button>
        </div>
        <p style={{ margin: "0 0 1rem", fontSize: "0.85rem", color: "#64748b" }}>세탁한 이미지를 저장해두면, 블로그·카페 발행 때 가져다 쓸 수 있습니다. 서버 용량 보호를 위해 <b>계정당 최대 {libMeta.max_files}장 · {libMeta.ttl_days}일 후 자동 삭제 · 저장 시 자동 압축</b>됩니다.</p>
        {library.length === 0 ? (
          <div style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8", fontSize: "0.9rem", background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: "8px" }}>
            아직 저장된 이미지가 없습니다. 세탁 후 <b>💾 보관함에 저장</b>을 눌러보세요.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: "0.8rem" }}>
            {library.map((img) => (
              <div key={img.filename} style={{ position: "relative", border: "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden", background: "#f8fafc" }}>
                <img src={img.base64_data} alt={img.filename} style={{ width: "100%", height: "110px", objectFit: "cover", display: "block" }} />
                <button onClick={() => deleteFromLibrary(img.filename)} title="삭제" style={{ position: "absolute", top: "4px", right: "4px", width: "24px", height: "24px", borderRadius: "50%", background: "rgba(239,68,68,0.9)", color: "white", border: "none", cursor: "pointer", fontWeight: "bold", lineHeight: 1 }}>×</button>
              </div>
            ))}
          </div>
        )}
      </div>

      <WorkHistory menuKey="image-wash" />
    </div>
  );
}
