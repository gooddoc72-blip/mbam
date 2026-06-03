import os

dirs = {
    'content-collect': '글감 수집',
    'place-seo': '플레이스 진단',
    'blog-check': '블로그 진단',
    'blog-auto': '블로그 자동화',
    'cafe-auto': '카페 자동화',
    'communication': '소통 & 이웃',
    'multi-task': '멀티 실행',
    'logs': '로그'
}

base = r'c:\Users\blocklabs02\Desktop\review_platform\review-platform-phase1-3\review-platform\frontend\app'

template = """export default function Page() {
    return (
        <div style={{ padding: "2rem" }}>
            <h1 style={{ fontSize: "2rem", fontWeight: "bold", marginBottom: "1.5rem" }}>{title}</h1>
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
}"""

for d, title in dirs.items():
    path = os.path.join(base, d, 'page.js')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(template.replace('{title}', title))

print("Placeholders created successfully!")
