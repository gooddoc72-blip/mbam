"use client";
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
    LayoutDashboard, 
    FileText, 
    TrendingUp, 
    MapPin, 
    ShieldCheck, 
    PenTool, 
    Coffee, 
    HeartHandshake, 
    Layers, 
    Settings, 
    ScrollText,
    ChevronDown,
    ChevronRight,
    Search,
    MessageSquare,
    CreditCard,
    CalendarClock,
    BarChart3,
    KeyRound,
    Image,
    Folder
} from 'lucide-react';
import { fetchWithAuth } from "../utils/api";

const MENU_ITEMS = [
    { name: "홈", path: "/dashboard", icon: LayoutDashboard },
    {
        name: "블로그",
        icon: PenTool,
        submenus: [
            { name: "블로그 진단", path: "/blog-check", icon: ShieldCheck },
            { name: "형태소 분석", path: "/blog-analysis", icon: Search },
            { name: "블로그 발행", path: "/blog-posting", icon: PenTool },
            { name: "소통 & 이웃", path: "/communication", icon: HeartHandshake },
            { name: "이미지 세탁소", path: "/image-wash", icon: Image },
            { name: "구글 블로그스팟", path: "/blogspot", icon: FileText },
            { name: "티스토리", path: "/blog-schedule?platform=tistory", icon: FileText }
        ]
    },
    {
        name: "네이버 카페",
        icon: Coffee,
        submenus: [
            { name: "형태소 분석", path: "/cafe-analysis", icon: Search },
            { name: "카페 포스팅", path: "/cafe-auto", icon: PenTool },
            { name: "블로그·카페 글 순위", path: "/cafe-rank", icon: TrendingUp },
            { name: "이미지 세탁소", path: "/cafe-image-wash", icon: Image }
        ]
    },
    {
        name: "플레이스 마케팅",
        icon: MapPin,
        submenus: [
            { name: "플레이스 진단", path: "/place-seo", icon: MapPin },
            { name: "플레이스 자동화", path: "/place-news", icon: PenTool }
        ]
    },
    {
        name: "순위 추적",
        icon: TrendingUp,
        submenus: [
            { name: "네이버 쇼핑", path: "/shopping/rank", icon: TrendingUp },
            { name: "쿠팡 순위", path: "/coupang/rank", icon: TrendingUp }
        ]
    },
    {
        name: "키워드 분석",
        icon: KeyRound,
        submenus: [
            { name: "SEO 통검분석", path: "/seo-analysis", icon: BarChart3 },
            { name: "쇼핑 키워드 분석", path: "/shopping/keyword", icon: Search },
            { name: "상품명 키워드 조합", path: "/shopping/combine", icon: FileText }
        ]
    },
    {
        name: "마케팅 컨텐츠",
        icon: Folder,
        submenus: [
            { name: "글감수집", path: "/content-collect", icon: FileText },
            { name: "원고관리", path: "/manuscript", icon: ScrollText },
            { name: "이미지 세탁소", path: "/content-image-wash", icon: Image }
        ]
    },
    { name: "계정관리", path: "/multi-task", icon: Layers },
    { name: "설정", path: "/settings", icon: Settings },
    { name: "결제 및 플랜", path: "/billing", icon: CreditCard },
    { name: "로그", path: "/logs", icon: ScrollText },
    { name: "관리자 (마스터)", path: "/admin", icon: ShieldCheck, adminOnly: true },
];

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [openMenus, setOpenMenus] = useState({"블로그": true, "네이버 카페": true, "플레이스 마케팅": true, "순위 추적": true, "키워드 분석": true, "마케팅 컨텐츠": true});
    const [mounted, setMounted] = useState(false);
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [userRole, setUserRole] = useState(null);
    const [userEmail, setUserEmail] = useState("");
    const [planType, setPlanType] = useState(null);
    const [trialDaysLeft, setTrialDaysLeft] = useState(null);
    const [activeTasks, setActiveTasks] = useState([]);
    const [drawerOpen, setDrawerOpen] = useState(false); // 모바일 사이드바 드로어

    // 메뉴 이동 시 드로어 자동 닫기
    useEffect(() => { setDrawerOpen(false); }, [pathname]);

    const fetchActiveTasks = async () => {
        try {
            const res = await fetchWithAuth("/api/auto_post/active_tasks");
            if (res.ok) {
                const data = await res.json();
                if (data.tasks) {
                    setActiveTasks(data.tasks);
                }
            }
        } catch (e) {
            // silent fail
        }
    };

    useEffect(() => {
        setMounted(true);
        const token = localStorage.getItem('mbam_token');
        if (token) {
            setIsLoggedIn(true);
            try {
                const payload = JSON.parse(atob(token.split('.')[1]));
                setUserRole(payload.role);
                setUserEmail(payload.sub);
            } catch (e) {
                console.error("Token parsing error");
            }
            // 무료 체험 남은 일수 조회
            fetchWithAuth("/api/auth/me").then(async (res) => {
                if (res && res.ok) {
                    const me = await res.json();
                    setPlanType(me.plan_type || null);
                    if (me.trial_ends_at) {
                        const end = new Date(me.trial_ends_at.endsWith("Z") ? me.trial_ends_at : me.trial_ends_at + "Z");
                        const days = Math.max(0, Math.ceil((end.getTime() - Date.now()) / 86400000));
                        setTrialDaysLeft(days);
                    }
                }
            }).catch(() => {});
            fetchActiveTasks();
            const interval = setInterval(fetchActiveTasks, 5000);
            return () => clearInterval(interval);
        } else {
            setIsLoggedIn(false);
            setUserRole(null);
            setUserEmail("");
        }
    }, [pathname]);

    const toggleMenu = (name) => {
        setOpenMenus(prev => ({ ...prev, [name]: !prev[name] }));
    };

    return (
        <>
        <button className="sidebar-hamburger" onClick={() => setDrawerOpen(true)} aria-label="메뉴 열기">☰</button>
        <div className={"sidebar-overlay" + (drawerOpen ? " open" : "")} onClick={() => setDrawerOpen(false)} />
        <aside className={"app-sidebar" + (drawerOpen ? " open" : "")} style={{
            width: "260px",
            height: "100vh",
            background: "rgba(255, 255, 255, 0.95)",
            backdropFilter: "blur(12px)",
            borderRight: "1px solid rgba(226, 232, 240, 0.8)",
            display: "flex",
            flexDirection: "column",
            position: "sticky",
            top: 0
        }}>
            <div style={{ padding: "2rem 1.5rem 1.5rem 1.5rem", borderBottom: "1px solid rgba(226, 232, 240, 0.6)", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                <div>
                    <h1 style={{ fontSize: "2.1rem", fontWeight: "800", color: "#1e293b", margin: 0, letterSpacing: "-0.5px" }}>
                        <span style={{ color: "#3b82f6" }}>마케팅연구소</span>
                    </h1>
                    <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "0.3rem" }}>Marketing lab's</p>
                </div>
                
                {!mounted ? (
                    <div style={{ height: "45px" }}></div>
                ) : isLoggedIn ? (
                    <div style={{ padding: "0.75rem", borderRadius: "8px", background: "#f8fafc", border: "1px solid #e2e8f0" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                            <div style={{ width: "32px", height: "32px", borderRadius: "50%", background: "#3b82f6", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "0.9rem" }}>
                                {userEmail ? userEmail.charAt(0).toUpperCase() : "U"}
                            </div>
                            <div style={{ flex: 1, overflow: "hidden" }}>
                                <div style={{ fontSize: "0.85rem", fontWeight: "600", color: "#1e293b", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                                    {userEmail || "사용자"}
                                </div>
                                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                                    {userRole === "admin" ? "마스터 관리자" : "회원"}
                                </div>
                                {userRole !== "admin" && planType === "trial" && trialDaysLeft !== null && (
                                    <div style={{ fontSize: "0.72rem", fontWeight: 700, marginTop: "2px", color: trialDaysLeft <= 1 ? "#ef4444" : "#f59e0b" }}>
                                        {trialDaysLeft > 0 ? `무료 체험 ${trialDaysLeft}일 남음` : "무료 체험 종료"}
                                    </div>
                                )}
                                {userRole !== "admin" && planType === "paid" && (
                                    <div style={{ fontSize: "0.72rem", fontWeight: 700, marginTop: "2px", color: "#10b981" }}>
                                        정식 이용 중
                                    </div>
                                )}
                            </div>
                        </div>
                        <button 
                            onClick={() => {
                                localStorage.removeItem('mbam_token');
                                window.location.href = '/login';
                            }}
                            style={{
                                width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid #e2e8f0", 
                                background: "white", color: "#64748b", fontWeight: "600", cursor: "pointer",
                                transition: "all 0.2s ease", fontSize: "0.8rem"
                            }}
                            onMouseOver={(e) => { e.currentTarget.style.background = "#fee2e2"; e.currentTarget.style.color = "#ef4444"; e.currentTarget.style.borderColor = "#fecaca"; }}
                            onMouseOut={(e) => { e.currentTarget.style.background = "white"; e.currentTarget.style.color = "#64748b"; e.currentTarget.style.borderColor = "#e2e8f0"; }}
                        >
                            로그아웃
                        </button>
                    </div>
                ) : (
                    <Link href="/login" style={{ textDecoration: "none" }}>
                        <button 
                            style={{
                                width: "100%", padding: "0.75rem", borderRadius: "8px", border: "none", 
                                background: "#3b82f6", color: "white", fontWeight: "600", cursor: "pointer",
                                transition: "all 0.2s ease"
                            }}
                            onMouseOver={(e) => { e.currentTarget.style.background = "#2563eb"; }}
                            onMouseOut={(e) => { e.currentTarget.style.background = "#3b82f6"; }}
                        >
                            로그인
                        </button>
                    </Link>
                )}
            </div>
            
            <nav style={{ flex: 1, padding: "1.5rem 1rem", display: "flex", flexDirection: "column", gap: "0.5rem", overflowY: "auto" }}>
                {MENU_ITEMS.map((item, idx) => {
                    if (item.adminOnly && userRole !== 'admin') return null;
                    
                    const Icon = item.icon;
                    
                    if (item.submenus) {
                        const isOpen = openMenus[item.name];
                        const isAnySubActive = item.submenus.some(sub => pathname === sub.path);
                        return (
                            <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                <div 
                                    onClick={() => toggleMenu(item.name)}
                                    style={{
                                        display: "flex", alignItems: "center", justifyContent: "space-between",
                                        padding: "0.75rem 1rem", borderRadius: "8px", cursor: "pointer",
                                        background: isAnySubActive ? "#f1f5f9" : "transparent",
                                        color: isAnySubActive ? "#334155" : "#475569",
                                        fontWeight: isAnySubActive ? "600" : "500",
                                        transition: "all 0.2s ease"
                                    }}
                                >
                                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", minWidth: 0 }}>
                                        <Icon size={20} strokeWidth={isAnySubActive ? 2.5 : 2} style={{ flexShrink: 0 }} />
                                        <span style={{ fontSize: "0.95rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.name}</span>
                                    </div>
                                    <span style={{ flexShrink: 0, display: "inline-flex" }}>{isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
                                </div>
                                {isOpen && (
                                    <div style={{ paddingLeft: "2.5rem", display: "flex", flexDirection: "column", gap: "2px" }}>
                                        {item.submenus.map((sub, sIdx) => {
                                            const isSubActive = pathname === sub.path;
                                            const SubIcon = sub.icon;
                                            return (
                                                <Link key={sIdx} href={sub.path} style={{ textDecoration: "none" }}>
                                                    <div style={{
                                                        display: "flex", alignItems: "center", gap: "0.5rem",
                                                        padding: "0.6rem 1rem", borderRadius: "8px",
                                                        background: isSubActive ? "#eff6ff" : "transparent",
                                                        color: isSubActive ? "#3b82f6" : "#64748b",
                                                        fontWeight: isSubActive ? "600" : "400",
                                                        fontSize: "0.9rem",
                                                        transition: "all 0.2s ease",
                                                        minWidth: 0
                                                    }}>
                                                        <SubIcon size={16} style={{ flexShrink: 0 }} />
                                                        <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{sub.name}</span>
                                                    </div>
                                                </Link>
                                            )
                                        })}
                                    </div>
                                )}
                            </div>
                        );
                    }

                    const isActive = pathname === item.path;
                    return (
                        <Link key={item.path} href={item.path} style={{ textDecoration: "none" }}>
                            <div style={{
                                display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem",
                                borderRadius: "8px", background: isActive ? "#eff6ff" : "transparent",
                                color: isActive ? "#3b82f6" : "#475569", fontWeight: isActive ? "600" : "500",
                                transition: "all 0.2s ease"
                            }}>
                                <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
                                <span style={{ fontSize: "0.95rem" }}>{item.name}</span>
                            </div>
                        </Link>
                    );
                })}
            </nav>

            {mounted && isLoggedIn && activeTasks.length > 0 && (
                <div style={{ padding: "1rem", borderTop: "1px solid rgba(226, 232, 240, 0.6)" }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: "bold", color: "#64748b", marginBottom: "0.5rem" }}>
                        ⚡ 진행 중인 자동화 작업 ({activeTasks.length})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {activeTasks.map(task => (
                            <div 
                                key={task.task_id}
                                onClick={() => {
                                    // 진행 중인 자동화 브라우저 창을 앞으로 가져오기
                                    fetchWithAuth("/api/auto_post/focus-running", { method: "POST" }).catch(() => {});
                                    const title = task.title || "";
                                    if (title.includes('카페') || title.includes('다중')) {
                                        localStorage.setItem("mbam_cafe_task_id", task.task_id);
                                        router.push("/cafe-auto");
                                    } else {
                                        localStorage.setItem("mbam_auto_post_task_id", task.task_id);
                                        router.push("/blog-posting");
                                    }
                                }}
                                style={{
                                    padding: "0.6rem", background: "#eff6ff", borderRadius: "6px",
                                    border: "1px solid #bfdbfe", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.5rem"
                                }}
                            >
                                <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#3b82f6", animation: "pulse 1.5s infinite" }} />
                                <span style={{ fontSize: "0.8rem", color: "#1e3a8a", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                    {task.title}
                                </span>
                            </div>
                        ))}
                    </div>
                    <style>{`
                        @keyframes pulse {
                            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
                            70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(59, 130, 246, 0); }
                            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
                        }
                    `}</style>
                </div>
            )}
            
            <div style={{ padding: "1.5rem", borderTop: "1px solid rgba(226, 232, 240, 0.6)", display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ fontSize: "0.8rem", color: "#94a3b8", textAlign: "center", marginTop: "0.5rem" }}>
                    &copy; 2026 마케팅연구소 Marketing lab's
                </div>
            </div>
        </aside>
        </>
    );
}
