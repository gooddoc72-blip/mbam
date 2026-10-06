import "./globals.css";

import Sidebar from "./components/Sidebar";
import AuthGuard from "./components/AuthGuard";
import { IS_CAFE_EDITION, IS_BLOG_EDITION } from "./utils/product";

export const metadata = IS_CAFE_EDITION
  ? {
      title: "카페 마케팅",
      description: "네이버 카페 분석 · 포스팅 · 육성 · 순위추적",
    }
  : IS_BLOG_EDITION
  ? {
      title: "블로그 마케팅",
      description: "블로그 진단 · 형태소 분석 · 자동 발행 · 소통 · 순위추적",
    }
  : {
      title: "마케팅연구소 Marketing lab's",
      description: "Advanced Marketing Automation & SEO Analysis",
    };

export default function RootLayout({ children }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <style>{`
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }
          body {
            margin: 0;
            padding: 0;
            background: #f8fafc;
            color: #334155;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          }
        `}</style>
      </head>
      <body suppressHydrationWarning>
        <AuthGuard>
          <div className="app-shell">
            <Sidebar />
            <main className="app-main">
              {children}
            </main>
          </div>
        </AuthGuard>
      </body>
    </html>
  );
}
