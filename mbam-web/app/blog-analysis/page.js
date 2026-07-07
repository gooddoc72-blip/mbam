"use client";
// 블로그글 분석 라우트 — 카페 분석과 같은 뼈대를 쓰되 channel="blog" 로 분리:
// 블로그 URL만 허용, URL 권위 분석은 블로그 지수 진단, 작업내역/입력 상태도 별도 보관.
import CafeAnalysisPage from "../cafe-analysis/page";

export default function BlogAnalysisPage() {
    return <CafeAnalysisPage channel="blog" />;
}
