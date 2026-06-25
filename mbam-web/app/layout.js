import "./globals.css";

import Sidebar from "./components/Sidebar";
import AuthGuard from "./components/AuthGuard";

export const metadata = {
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
