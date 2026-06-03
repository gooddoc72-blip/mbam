export default function Page() {
    return (
        <div style={{ padding: "2rem" }}>
            <h1 style={{ fontSize: "2rem", fontWeight: "bold", marginBottom: "1.5rem" }}>로그</h1>
            <div style={{ 
                background: "white", 
                padding: "3rem", 
                borderRadius: "16px", 
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                textAlign: "center",
                color: "#64748b"
            }}>
                현재 열심히 개발 중인 페이지입니다. 🚀<br/>(Phase 2 백엔드 연동 대기 중)
            </div>
        </div>
    );
}