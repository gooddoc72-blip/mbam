import "./globals.css";

import Sidebar from "./components/Sidebar";

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
        <div style={{ display: "flex", minHeight: "100vh" }}>
          <Sidebar />
          <main style={{ flex: 1, padding: "2rem", overflowY: "auto", height: "100vh" }}>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
