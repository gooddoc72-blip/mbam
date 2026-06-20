"use client";
import { useState, useRef, useEffect } from "react";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import { fetchWithAuth } from "../utils/api";
import { Plus, Check, Download, Info } from "lucide-react";

export default function ImageWashPage() {
  const [files, setFiles] = useState([]);
  const [selectedFileIndex, setSelectedFileIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]); // List of { original_filename, base64_data }
  const fileInputRef = useRef(null);

  // Settings state
  const [count, setCount] = useState(10);
  const [exifSetting, setExifSetting] = useState("촬영일시 ±10일 랜덤 / 카메라 모델 랜덤");
  const [useBorder, setUseBorder] = useState(false);
  const [useNoise, setUseNoise] = useState(true);
  const [useWatermark, setUseWatermark] = useState(false);
  const [useRotation, setUseRotation] = useState(false);

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

    try {
      const res = await fetchWithAuth("/api/settings/wash-upload", {
        method: "POST",
        body: formData, // fetchWithAuth shouldn't stringify FormData
      });

      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          setResults(data.results);
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

      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
        
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
              전체 저장 ({results.length}장)
            </button>
            {results.length > 0 && <div style={{ textAlign: "center", fontSize: "0.85rem", color: "#16a34a", fontWeight: "bold" }}>{results.length}장 생성 완료</div>}
          </div>
        </div>

        {/* Center Panel: Settings */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "1rem" }}>
          
          <div style={{ backgroundColor: "#f8faff", border: "1px solid #dbeafe", borderRadius: "8px", padding: "1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#1e3a8a", margin: 0 }}>자동 대량 생성</h2>
              <span style={{ backgroundColor: "#dbeafe", color: "#2563eb", padding: "0.2rem 0.5rem", borderRadius: "4px", fontSize: "0.8rem" }}>블로그 캠페인용</span>
            </div>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "1.5rem", lineHeight: 1.5 }}>
              원본 이미지를 순환하며 N장을 생성합니다. 각 이미지마다 노이즈·회전·밝기를 미세 변형하고 EXIF 날짜를 오늘 기준 ±10일 내 랜덤 설정합니다.
            </p>

            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
              <span style={{ fontWeight: "bold", color: "#334155" }}>생성 수량</span>
              <input 
                type="number" 
                value={count} 
                onChange={e => setCount(parseInt(e.target.value))} 
                style={{ width: "80px", padding: "0.5rem", border: "1px solid #cbd5e1", borderRadius: "4px", textAlign: "center" }}
              />
              <span style={{ color: "#64748b" }}>장 (최대 200)</span>
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

          {/* Toggle Options */}
          {[
            { label: "테두리", state: useBorder, setter: setUseBorder },
            { label: "노이즈", state: useNoise, setter: setUseNoise, desc: "(자동 생성 시 항상 적용됨)" },
            { label: "워터마크", state: useWatermark, setter: setUseWatermark },
            { label: "회전", state: useRotation, setter: setUseRotation, desc: "(자동 생성 시 기준값 ±2° 랜덤 추가)" },
          ].map((opt, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", padding: "1.2rem", backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px" }}>
              <input 
                type="checkbox" 
                checked={opt.state} 
                onChange={e => opt.setter(e.target.checked)} 
                style={{ width: "18px", height: "18px", marginRight: "1rem", cursor: "pointer" }}
              />
              <span style={{ fontSize: "1rem", fontWeight: "bold", color: "#334155" }}>{opt.label}</span>
              {opt.desc && <span style={{ marginLeft: "0.5rem", fontSize: "0.9rem", color: "#94a3b8" }}>{opt.desc}</span>}
            </div>
          ))}

        </div>

        {/* Right Panel: Preview & Info */}
        <div style={{ width: "320px", display: "flex", flexDirection: "column", gap: "1rem" }}>
          
          <div style={{ backgroundColor: "white", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1.5rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: "bold", margin: 0, color: "#1e293b" }}>미리보기</h3>
              <button style={{ padding: "0.4rem 0.8rem", backgroundColor: "#3b82f6", color: "white", border: "none", borderRadius: "4px", fontSize: "0.85rem", cursor: "pointer" }}>미리보기 생성</button>
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
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.9rem", color: "#64748b" }}>
              <div>테두리: {useBorder ? <span style={{color:"#4f46e5", fontWeight:"bold"}}>활성</span> : "비활성"}</div>
              <div>노이즈: {useNoise ? <span style={{color:"#4f46e5", fontWeight:"bold"}}>활성</span> : "비활성"}</div>
              <div>워터마크: {useWatermark ? <span style={{color:"#4f46e5", fontWeight:"bold"}}>활성</span> : "비활성"}</div>
              <div>회전: {useRotation ? <span style={{color:"#4f46e5", fontWeight:"bold"}}>활성</span> : "비활성"}</div>
              <div style={{ marginTop: "0.5rem", color: "#3b82f6" }}>자동생성: EXIF 날짜 ±10일 랜덤 삽입</div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
