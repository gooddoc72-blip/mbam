"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Users, Search, Settings, Key, AlertCircle, Save } from "lucide-react";

export default function AdminDashboard() {
  const router = useRouter();
  const [users, setUsers] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [editingUser, setEditingUser] = useState(null);

  // API Key States
  const [keys, setKeys] = useState({ customer_id: "", access_license: "", secret_key: "" });
  const [devKeys, setDevKeys] = useState({ client_id: "", client_secret: "" });
  const [aiKeys, setAiKeys] = useState({ claude_key: "", gemini_key: "", openai_key: "" });
  const [blogPrompts, setBlogPrompts] = useState({ 
    product: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    hospital: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    app: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    place: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    service: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    content_collect: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    blog_daily: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    blogspot: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    cafe: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    cafe_matjip: { claude_prompt: "", gemini_prompt: "", reference_files: [] },
    tistory: { claude_prompt: "", gemini_prompt: "", reference_files: [] }
  });
  const [activePromptCategory, setActivePromptCategory] = useState("product");

  const promptCategories = [
    { id: "product", name: "상품후기" },
    { id: "hospital", name: "병원블로그 운영" },
    { id: "app", name: "앱 및 서비스 홍보" },
    { id: "place", name: "맛집 후기 및 리뷰블로그" },
    { id: "service", name: "서비스업종 리뷰 및 후기 블로그" },
    { id: "content_collect", name: "📰 글감수집 원고" },
    { id: "blog_daily", name: "🗓️ 블로그 자동배포" },
    { id: "blogspot", name: "🅑 블로그스팟 자동배포(HTML)" },
    { id: "cafe", name: "☕ 카페 포스팅" },
    { id: "cafe_matjip", name: "🍜 카페 맛집 포스팅" },
    { id: "tistory", name: "🅣 티스토리 자동배포" }
  ];
  const [apiSaving, setApiSaving] = useState(false);
  const [apiMessage, setApiMessage] = useState(null);

  useEffect(() => {
    fetchUsersAndPlans();
  }, []);

  const fetchUsersAndPlans = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("mbam_token");
      if (!token) {
        router.push("/login");
        return;
      }
      
      const resUsers = await fetch("/api/admin/users", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      
      if (resUsers.status === 403) {
        setError("관리자 권한이 없습니다.");
        setLoading(false);
        return;
      }
      
      if (!resUsers.ok) throw new Error("데이터를 불러오지 못했습니다.");
      const dataUsers = await resUsers.json();
      setUsers(dataUsers);

      const resPlans = await fetch("/api/admin/plans");
      if (resPlans.ok) {
        const dataPlans = await resPlans.json();
        setPlans(dataPlans);
      }
      
      // Fetch API Keys
      const [resNaver, resDev, resAi, resPrompts] = await Promise.all([
        fetch("/api/settings/naver-api", { headers: { "Authorization": `Bearer ${token}` } }),
        fetch("/api/settings/naver-dev-api", { headers: { "Authorization": `Bearer ${token}` } }),
        fetch("/api/settings/ai-api", { headers: { "Authorization": `Bearer ${token}` } }),
        fetch("/api/settings/blog-prompts", { headers: { "Authorization": `Bearer ${token}` } })
      ]);
      
      if (resNaver.ok) {
          const d = await resNaver.json();
          setKeys({ customer_id: d.customer_id || "", access_license: d.access_license || "", secret_key: d.secret_key || "" });
      }
      if (resDev.ok) {
          const d = await resDev.json();
          setDevKeys({ client_id: d.client_id || "", client_secret: d.client_secret || "" });
      }
      if (resAi.ok) {
          const d = await resAi.json();
          setAiKeys({ claude_key: d.claude_key || "", gemini_key: d.gemini_key || "", openai_key: d.openai_key || "" });
      }
      if (resPrompts.ok) {
          const d = await resPrompts.json();
          setBlogPrompts(d);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveApiKeys = async () => {
    setApiSaving(true);
    setApiMessage(null);
    try {
        const token = localStorage.getItem("mbam_token");
        const headers = { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" };
        
        const [res1, resDev, res2, resPrompts] = await Promise.all([
            fetch("/api/settings/naver-api", { method: "POST", headers, body: JSON.stringify(keys) }),
            fetch("/api/settings/naver-dev-api", { method: "POST", headers, body: JSON.stringify(devKeys) }),
            fetch("/api/settings/ai-api", { method: "POST", headers, body: JSON.stringify(aiKeys) }),
            fetch("/api/settings/blog-prompts", { method: "POST", headers, body: JSON.stringify(blogPrompts) })
        ]);
        
        if (res1.ok && resDev.ok && res2.ok && resPrompts.ok) {
            setApiMessage({ type: "success", text: "마스터 API 및 프롬프트 설정이 성공적으로 저장되었습니다." });
        } else {
            setApiMessage({ type: "error", text: `저장에 실패했습니다. Naver: ${res1.status}, AI: ${res2.status}, Prompts: ${resPrompts.status}` });
        }
    } catch (error) {
        setApiMessage({ type: "error", text: `서버와 연결할 수 없습니다: ${error.message}` });
    }
    setApiSaving(false);
  };

  const handleUpdateQuota = async (e) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem("mbam_token");
      const res = await fetch(`/api/admin/users/${editingUser.id}/quota`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          plan_type: editingUser.plan_type,
          max_usage: parseInt(editingUser.max_usage)
        })
      });

      if (res.ok) {
        alert("회원 쿼터가 성공적으로 변경되었습니다.");
        setEditingUser(null);
        fetchUsersAndPlans();
      } else {
        const errorData = await res.json();
        alert(errorData.detail || "업데이트 실패");
      }
    } catch (err) {
      alert("서버와 통신할 수 없습니다.");
    }
  };

    const handleUpdatePlans = async () => {
    try {
      const token = localStorage.getItem("mbam_token");
      const res = await fetch(`/api/admin/plans`, {
        method: "PUT",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(plans)
      });
      if (res.ok) {
        alert("요금제 설정이 성공적으로 저장되었습니다.");
      } else {
        alert("요금제 설정 저장에 실패했습니다.");
      }
    } catch (err) {
      alert("서버 오류");
    }
  };

  const handleResetPassword = async (userId, email) => {
    const newPw = prompt(`[${email}] 회원의 새 비밀번호를 입력하세요. (8자 이상)`);
    if (newPw === null) return;
    if (!newPw || newPw.length < 8) {
      alert("비밀번호는 8자 이상이어야 합니다.");
      return;
    }
    try {
      const token = localStorage.getItem("mbam_token");
      const res = await fetch(`/api/admin/users/${userId}/password`, {
        method: "PUT",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: newPw })
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || "비밀번호가 재설정되었습니다.");
      } else {
        alert(data.detail || "비밀번호 재설정에 실패했습니다.");
      }
    } catch (err) {
      alert("서버와 통신할 수 없습니다.");
    }
  };

  const handleResetDevices = async (userId) => {
    if (!confirm("해당 회원의 모든 기기(PC) 등록 정보를 초기화하시겠습니까?\\n(초기화 후 새로운 기기 2대에서 접속이 가능해집니다.)")) return;
    try {
      const token = localStorage.getItem("mbam_token");
      const res = await fetch(`/api/admin/users/${userId}/reset-devices`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        alert("기기 정보가 성공적으로 초기화되었습니다.");
        fetchUsersAndPlans(); // Refresh device count
      } else {
        const errorData = await res.json();
        alert(errorData.detail || "초기화에 실패했습니다.");
      }
    } catch (err) {
      alert("서버 통신 오류");
    }
  };

  const filteredUsers = users.filter(u => 
    u.email.toLowerCase().includes(searchTerm.toLowerCase()) || 
    (u.business_name && u.business_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  if (loading) return <div style={{ padding: "2rem" }}>Loading...</div>;
  if (error) return <div style={{ padding: "2rem", color: "red" }}>{error}</div>;

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.8rem", fontWeight: "700", color: "#1e293b", margin: 0 }}>전체관리자 대시보드</h1>
        <p style={{ color: "#64748b", marginTop: "0.5rem" }}>마케팅연구소 회원 및 요금제 설정 관리</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "1.5rem", marginBottom: "2rem" }}>
        <div style={{ background: "white", padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ background: "#eff6ff", padding: "1rem", borderRadius: "12px", color: "#3b82f6" }}>
            <Users size={24} />
          </div>
          <div>
            <div style={{ fontSize: "0.9rem", color: "#64748b", fontWeight: "600" }}>총 회원수</div>
            <div style={{ fontSize: "1.8rem", fontWeight: "700", color: "#1e293b" }}>{users.length}명</div>
          </div>
        </div>
      </div>

      {/* 요금제 설정 패널 */}
      <div style={{ background: "white", borderRadius: "12px", border: "1px solid #e2e8f0", overflow: "hidden", marginBottom: "2rem" }}>
        <div style={{ padding: "1.5rem", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Settings size={20} color="#3b82f6" />
            <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#1e293b", margin: 0 }}>플랜(요금제) 기준 설정</h2>
          </div>
          <button 
            onClick={handleUpdatePlans}
            style={{ padding: "0.6rem 1.2rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "600" }}
          >
            변경사항 저장하기
          </button>
        </div>
        <div style={{ padding: "1.5rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem" }}>
          {plans.map((plan, idx) => (
            <div key={idx} style={{ padding: "1.5rem", border: "1px solid #e2e8f0", borderRadius: "8px", background: "#fcfcfc" }}>
              <h3 style={{ margin: "0 0 1rem 0", color: "#1e293b", fontSize: "1.2rem" }}>{plan.name} 플랜</h3>
              <div style={{ marginBottom: "1rem" }}>
                <label style={{ display: "block", fontSize: "0.9rem", color: "#64748b", marginBottom: "0.3rem" }}>월 가격 (₩)</label>
                <input 
                  type="number" 
                  value={plan.price} 
                  onChange={e => {
                    const newPlans = [...plans];
                    newPlans[idx].price = parseInt(e.target.value) || 0;
                    setPlans(newPlans);
                  }}
                  style={{ width: "100%", padding: "0.8rem", borderRadius: "6px", border: "1px solid #cbd5e1", boxSizing: "border-box" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.9rem", color: "#64748b", marginBottom: "0.3rem" }}>기본 제공 쿼터 (횟수)</label>
                <input
                  type="number"
                  value={plan.max_usage}
                  onChange={e => {
                    const newPlans = [...plans];
                    newPlans[idx].max_usage = parseInt(e.target.value) || 0;
                    setPlans(newPlans);
                  }}
                  style={{ width: "100%", padding: "0.8rem", borderRadius: "6px", border: "1px solid #cbd5e1", boxSizing: "border-box" }}
                />
              </div>
              <div style={{ marginTop: "1rem" }}>
                <label style={{ display: "block", fontSize: "0.9rem", color: "#64748b", marginBottom: "0.3rem" }}>네이버 계정 수 (최대)</label>
                <input
                  type="number"
                  value={plan.max_naver_accounts ?? 0}
                  onChange={e => {
                    const newPlans = [...plans];
                    newPlans[idx].max_naver_accounts = parseInt(e.target.value) || 0;
                    setPlans(newPlans);
                  }}
                  style={{ width: "100%", padding: "0.8rem", borderRadius: "6px", border: "1px solid #cbd5e1", boxSizing: "border-box" }}
                />
              </div>
              <div style={{ marginTop: "1rem" }}>
                <label style={{ display: "block", fontSize: "0.9rem", color: "#64748b", marginBottom: "0.5rem" }}>일일 자동화 한도 (계정당)</label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                  {[["blog_post","블로그 발행"],["cafe_post","카페 글"],["cafe_comment","카페 댓글"],["boost","부스트(방문)"],["place_news","플레이스 소식"]].map(([key, label]) => (
                    <div key={key}>
                      <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "0.2rem" }}>{label}</label>
                      <input
                        type="number"
                        value={(plan.daily_limits && plan.daily_limits[key]) ?? 0}
                        onChange={e => {
                          const newPlans = [...plans];
                          newPlans[idx].daily_limits = { ...(newPlans[idx].daily_limits || {}) };
                          newPlans[idx].daily_limits[key] = parseInt(e.target.value) || 0;
                          setPlans(newPlans);
                        }}
                        style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid #cbd5e1", boxSizing: "border-box" }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 마스터 API 설정 패널 */}
      <div style={{ background: "white", borderRadius: "12px", border: "1px solid #e2e8f0", overflow: "hidden", marginBottom: "2rem" }}>
        <div style={{ padding: "1.5rem", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#f8fafc" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Key size={20} color="#8b5cf6" />
            <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#1e293b", margin: 0 }}>글로벌 마스터 API 연동 설정</h2>
          </div>
          <button 
            onClick={handleSaveApiKeys}
            disabled={apiSaving}
            style={{ padding: "0.6rem 1.2rem", background: apiSaving ? "#94a3b8" : "#8b5cf6", color: "white", border: "none", borderRadius: "6px", cursor: apiSaving ? "not-allowed" : "pointer", fontWeight: "600", display: "flex", alignItems: "center", gap: "0.5rem" }}
          >
            <Save size={16} />
            {apiSaving ? "저장 중..." : "API 키 저장하기"}
          </button>
        </div>
        
        <div style={{ padding: "1.5rem" }}>
          <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1.5rem" }}>
            여기에 등록된 API 키는 <b>전체 사용자(회원)에게 공통으로 적용</b>됩니다. 
            (메인 서버 방식). 회원들은 별도의 API 가입이나 등록 없이 이 키를 통해 기능을 사용하게 됩니다.
          </p>
          
          {apiMessage && (
              <div style={{ 
                  padding: "1rem", marginBottom: "1.5rem", borderRadius: "8px", 
                  background: apiMessage.type === "success" ? "#f0fdf4" : "#fef2f2",
                  color: apiMessage.type === "success" ? "#166534" : "#991b1b",
                  border: `1px solid ${apiMessage.type === "success" ? "#bbf7d0" : "#fecaca"}`,
                  display: "flex", alignItems: "center", gap: "0.5rem"
              }}>
                  <AlertCircle size={18} />
                  {apiMessage.text}
              </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1.5rem" }}>
            {/* 네이버 검색광고 */}
            <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1.5rem", background: "#fafafa" }}>
              <h3 style={{ margin: "0 0 1rem 0", color: "#334155", fontSize: "1.05rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{width:"8px", height:"8px", borderRadius:"50%", background:"#3b82f6"}}></span> 네이버 검색광고 (검색량)
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Customer ID</label>
                      <input type="text" value={keys.customer_id} onChange={e => setKeys({...keys, customer_id: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Access License</label>
                      <input type="text" value={keys.access_license} onChange={e => setKeys({...keys, access_license: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Secret Key</label>
                      <input type="password" value={keys.secret_key} onChange={e => setKeys({...keys, secret_key: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
              </div>
            </div>
            
            {/* 네이버 개발자센터 */}
            <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1.5rem", background: "#fafafa" }}>
              <h3 style={{ margin: "0 0 1rem 0", color: "#334155", fontSize: "1.05rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{width:"8px", height:"8px", borderRadius:"50%", background:"#10b981"}}></span> 네이버 오픈 API (쇼핑)
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Client ID</label>
                      <input type="text" value={devKeys.client_id} onChange={e => setDevKeys({...devKeys, client_id: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Client Secret</label>
                      <input type="password" value={devKeys.client_secret} onChange={e => setDevKeys({...devKeys, client_secret: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
              </div>
            </div>

            {/* AI 엔진 */}
            <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1.5rem", background: "#fafafa" }}>
              <h3 style={{ margin: "0 0 1rem 0", color: "#334155", fontSize: "1.05rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{width:"8px", height:"8px", borderRadius:"50%", background:"#f59e0b"}}></span> AI 원고 작성 엔진
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Claude API Key</label>
                      <input type="password" value={aiKeys.claude_key} onChange={e => setAiKeys({...aiKeys, claude_key: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>OpenAI API Key</label>
                      <input type="password" value={aiKeys.openai_key} onChange={e => setAiKeys({...aiKeys, openai_key: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem" }}>Gemini API Key</label>
                      <input type="password" value={aiKeys.gemini_key} onChange={e => setAiKeys({...aiKeys, gemini_key: e.target.value})} style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", border: "1px solid #cbd5e1" }} />
                  </div>
              </div>
            </div>
            
            {/* 블로그 시스템 프롬프트 */}
            <div style={{ border: "1px solid #e2e8f0", borderRadius: "8px", padding: "1.5rem", background: "#fafafa", gridColumn: "1 / -1" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h3 style={{ margin: 0, color: "#334155", fontSize: "1.05rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{width:"8px", height:"8px", borderRadius:"50%", background:"#8b5cf6"}}></span> 블로그 포스팅 AI 프롬프트 (시스템 지시어)
                </h3>
                <button 
                  onClick={handleSaveApiKeys}
                  disabled={apiSaving}
                  style={{ padding: "0.5rem 1rem", background: apiSaving ? "#94a3b8" : "#8b5cf6", color: "white", border: "none", borderRadius: "6px", cursor: apiSaving ? "not-allowed" : "pointer", fontWeight: "bold", display: "flex", alignItems: "center", gap: "0.5rem" }}
                >
                  <Save size={16} />
                  {apiSaving ? "저장 중..." : "프롬프트 저장"}
                </button>
              </div>
              <p style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "1rem" }}>{`여기에서 설정한 프롬프트는 블로그 포스팅 자동화 시 AI(클로드/제미나이)에 기본 지시어로 주입됩니다. {keyword}, {combined_text} 등의 변수를 적절히 활용할 수 있습니다.`}</p>
              
              {/* 카테고리 탭 — 좁은 화면에서는 가로 스크롤 대신 여러 줄로 접힘 */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1.5rem", borderBottom: "1px solid #cbd5e1", paddingBottom: "0.5rem" }}>
                {promptCategories.map(cat => (
                  <button
                    key={cat.id}
                    onClick={() => setActivePromptCategory(cat.id)}
                    style={{
                      padding: "0.5rem 1rem",
                      background: activePromptCategory === cat.id ? "#8b5cf6" : "transparent",
                      color: activePromptCategory === cat.id ? "white" : "#64748b",
                      border: "none",
                      borderRadius: "6px",
                      cursor: "pointer",
                      fontWeight: activePromptCategory === cat.id ? "bold" : "normal",
                      whiteSpace: "nowrap"
                    }}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem", fontWeight: "bold" }}>Claude 시스템 프롬프트</label>
                      <textarea 
                          value={blogPrompts[activePromptCategory]?.claude_prompt || ""} 
                          onChange={e => setBlogPrompts({...blogPrompts, [activePromptCategory]: { ...blogPrompts[activePromptCategory], claude_prompt: e.target.value }})} 
                          placeholder="Claude 엔진에 전달할 블로그 원고 작성용 프롬프트를 입력하세요."
                          style={{ width: "100%", height: "200px", padding: "0.8rem", borderRadius: "6px", border: "1px solid #cbd5e1", resize: "vertical", fontFamily: "inherit" }} 
                      />
                  </div>
                  <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.3rem", fontWeight: "bold" }}>Gemini 시스템 프롬프트</label>
                      <textarea 
                          value={blogPrompts[activePromptCategory]?.gemini_prompt || ""} 
                          onChange={e => setBlogPrompts({...blogPrompts, [activePromptCategory]: { ...blogPrompts[activePromptCategory], gemini_prompt: e.target.value }})} 
                          placeholder="Gemini 엔진에 전달할 블로그 원고 작성용 프롬프트를 입력하세요."
                          style={{ width: "100%", height: "200px", padding: "0.8rem", borderRadius: "6px", border: "1px solid #cbd5e1", resize: "vertical", fontFamily: "inherit" }} 
                      />
                  </div>
              </div>

              <div style={{ marginTop: "1.5rem", padding: "1rem", border: "1px dashed #cbd5e1", borderRadius: "6px", background: "white" }}>
                <label style={{ display: "block", fontSize: "0.85rem", color: "#64748b", marginBottom: "0.5rem", fontWeight: "bold" }}>참고용 첨부파일 (필수 가이드라인 등)</label>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <input 
                    type="file" 
                    accept=".txt"
                    multiple
                    onChange={(e) => {
                      const files = Array.from(e.target.files);
                      if (files.length > 0) {
                        const newFiles = [];
                        let loadedCount = 0;
                        files.forEach(file => {
                          const reader = new FileReader();
                          reader.onload = (event) => {
                            newFiles.push({ name: file.name, content: event.target.result });
                            loadedCount++;
                            if (loadedCount === files.length) {
                              const existingFiles = blogPrompts[activePromptCategory]?.reference_files || [];
                              setBlogPrompts({...blogPrompts, [activePromptCategory]: { ...blogPrompts[activePromptCategory], reference_files: [...existingFiles, ...newFiles] }});
                              // Clear input
                              const input = document.querySelector('input[type="file"]');
                              if(input) input.value = '';
                            }
                          };
                          reader.readAsText(file, 'utf-8');
                        });
                      }
                    }}
                    style={{ fontSize: "0.85rem" }}
                  />
                  
                  {(blogPrompts[activePromptCategory]?.reference_files || []).length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                      {blogPrompts[activePromptCategory].reference_files.map((file, idx) => (
                        <div key={idx} style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", color: "#16a34a", background: "#f0fdf4", padding: "0.3rem 0.8rem", borderRadius: "4px", border: "1px solid #bbf7d0" }}>
                          <span>📄 {file.name}</span>
                          <button 
                            onClick={() => {
                                const newFiles = blogPrompts[activePromptCategory].reference_files.filter((_, i) => i !== idx);
                                setBlogPrompts({...blogPrompts, [activePromptCategory]: { ...blogPrompts[activePromptCategory], reference_files: newFiles }});
                            }}
                            style={{ border: "none", background: "transparent", cursor: "pointer", color: "#ef4444", fontWeight: "bold", marginLeft: "0.5rem" }}
                            title="파일 삭제"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.5rem", marginBottom: 0 }}>* .txt 형식의 텍스트 파일만 업로드 권장. 업로드된 파일 내용은 원고 생성 시 AI 프롬프트 하단에 자동으로 주입됩니다.</p>
              </div>

            </div>
            
          </div>
        </div>
      </div>

      {/* 회원 목록 */}
      <div style={{ background: "white", borderRadius: "12px", border: "1px solid #e2e8f0", overflow: "hidden" }}>
        <div style={{ padding: "1.5rem", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "1.2rem", fontWeight: "600", color: "#1e293b", margin: 0 }}>회원 목록</h2>
          <div style={{ position: "relative" }}>
            <Search size={18} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "#94a3b8" }} />
            <input 
              type="text" 
              placeholder="이메일 검색..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ padding: "0.6rem 1rem 0.6rem 2.5rem", borderRadius: "8px", border: "1px solid #cbd5e1", outline: "none", width: "250px" }}
            />
          </div>
        </div>
        
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ background: "#f8fafc", color: "#475569", fontSize: "0.9rem" }}>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600" }}>이메일 / 이름</th>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600" }}>플랜</th>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600" }}>라이선스(AI)</th>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600" }}>사용량 / 쿼터</th>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600" }}>기기 등록</th>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600" }}>만료일</th>
                <th style={{ padding: "1rem 1.5rem", fontWeight: "600", textAlign: "right" }}>관리</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map(user => (
                <tr key={user.id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                  <td style={{ padding: "1rem 1.5rem" }}>
                    <div style={{ fontWeight: "500", color: "#1e293b" }}>{user.email}</div>
                    <div style={{ fontSize: "0.85rem", color: "#64748b" }}>{user.business_name}</div>
                  </td>
                  <td style={{ padding: "1rem 1.5rem" }}>
                    <span style={{ 
                      padding: "0.2rem 0.8rem", borderRadius: "99px", fontSize: "0.85rem", fontWeight: "600",
                      background: user.plan_type === "trial" ? "#fef3c7" : "#dcfce3",
                      color: user.plan_type === "trial" ? "#d97706" : "#16a34a"
                    }}>
                      {user.plan_type === "trial" ? "무료체험" : user.plan_type}
                    </span>
                  </td>
                  <td style={{ padding: "1rem 1.5rem" }}>
                    <span style={{
                      padding: "0.2rem 0.7rem", borderRadius: "99px", fontSize: "0.8rem", fontWeight: "600",
                      background: user.has_byok ? "#ede9fe" : "#e0f2fe",
                      color: user.has_byok ? "#6d28d9" : "#0369a1"
                    }}>
                      {user.has_byok ? "설치형 · 본인키" : "웹 · 서버키(쿼터)"}
                    </span>
                  </td>
                  <td style={{ padding: "1rem 1.5rem", color: "#475569" }}>
                    {user.has_byok
                      ? <span style={{ color: "#94a3b8" }}>무제한(BYOK)</span>
                      : <><span style={{ fontWeight: "600", color: "#3b82f6" }}>{user.usage_count}</span> / {user.max_usage}회</>}
                  </td>
                  <td style={{ padding: "1rem 1.5rem", color: "#475569", fontSize: "0.9rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span style={{ color: (user.device_count || 0) >= 2 ? "#ef4444" : "#475569", fontWeight: "600" }}>
                            {user.device_count || 0} / 2 대
                        </span>
                        {(user.device_count || 0) > 0 && (
                            <button onClick={() => handleResetDevices(user.id)} style={{ padding: "0.2rem 0.5rem", fontSize: "0.75rem", background: "#fee2e2", color: "#b91c1c", border: "none", borderRadius: "4px", cursor: "pointer" }}>
                                초기화
                            </button>
                        )}
                    </div>
                  </td>
                  <td style={{ padding: "1rem 1.5rem", color: "#475569", fontSize: "0.95rem" }}>
                    {user.trial_ends_at ? new Date(user.trial_ends_at).toLocaleDateString() : "-"}
                  </td>
                  <td style={{ padding: "1rem 1.5rem", textAlign: "right" }}>
                    <div style={{ display: "flex", gap: "0.4rem", justifyContent: "flex-end" }}>
                      <button
                        onClick={() => handleResetPassword(user.id, user.email)}
                        style={{ padding: "0.5rem 0.8rem", background: "#fef3c7", color: "#b45309", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "500" }}
                        title="회원 비밀번호를 새로 지정합니다"
                      >
                        비번 재설정
                      </button>
                      <button
                        onClick={() => setEditingUser(user)}
                        style={{ padding: "0.5rem 1rem", background: "#f1f5f9", color: "#475569", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: "500" }}
                      >
                        회원 쿼터설정
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 모달 */}
      {editingUser && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "white", padding: "2rem", borderRadius: "12px", width: "400px", boxShadow: "0 20px 25px -5px rgba(0,0,0,0.1)" }}>
            <h3 style={{ margin: "0 0 1.5rem 0", fontSize: "1.3rem" }}>개별 회원 쿼터 강제 설정</h3>
            <div style={{ marginBottom: "1rem", color: "#64748b" }}>{editingUser.email}</div>
            
            <form onSubmit={handleUpdateQuota}>
              <div style={{ marginBottom: "1rem" }}>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>플랜 종류 적용</label>
                <select 
                  value={editingUser.plan_type}
                  onChange={e => setEditingUser({...editingUser, plan_type: e.target.value})}
                  style={{ width: "100%", padding: "0.8rem", borderRadius: "8px", border: "1px solid #cbd5e1" }}
                >
                  <option value="trial">무료체험 (Trial)</option>
                  <option value="web_basic">웹 Basic (서버키+쿼터)</option>
                  <option value="web_pro">웹 Pro (서버키+쿼터)</option>
                  <option value="installed">설치형 (BYOK·본인키)</option>
                  <option value="Basic">Basic</option>
                  <option value="Pro">Pro</option>
                  <option value="Enterprise">Enterprise</option>
                </select>
              </div>
              <div style={{ marginBottom: "1.5rem" }}>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>최대 사용 가능 횟수 (쿼터)</label>
                <input 
                  type="number" 
                  value={editingUser.max_usage}
                  onChange={e => setEditingUser({...editingUser, max_usage: e.target.value})}
                  style={{ width: "100%", padding: "0.8rem", borderRadius: "8px", border: "1px solid #cbd5e1", boxSizing: "border-box" }}
                />
              </div>
              
              <div style={{ display: "flex", gap: "1rem" }}>
                <button type="button" onClick={() => setEditingUser(null)} style={{ flex: 1, padding: "0.8rem", background: "#f1f5f9", color: "#475569", border: "none", borderRadius: "8px", fontWeight: "600", cursor: "pointer" }}>취소</button>
                <button type="submit" style={{ flex: 1, padding: "0.8rem", background: "#3b82f6", color: "white", border: "none", borderRadius: "8px", fontWeight: "600", cursor: "pointer" }}>저장하기</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
