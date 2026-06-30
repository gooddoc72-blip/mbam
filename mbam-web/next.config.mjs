/** @type {import('next').NextConfig} */
const nextConfig = {
  // dev rewrite 프록시 기본 타임아웃은 30초. 글감수집은 백그라운드 작업+폴링으로 전환해
  // 더는 이 한도에 걸리지 않지만, Playwright 기반 SEO 분석 등 다른 장시간 엔드포인트를
  // 위한 dev 안전망으로 120초 유지.
  experimental: {
    proxyTimeout: 120000,
  },
  async rewrites() {
    // 배포(Vercel): 환경변수 BACKEND_URL 을 Railway 백엔드 주소로 설정 → /api/* 를 그쪽으로 프록시.
    // 프론트와 같은 출처처럼 보이게 해 쿠키/CORS 문제를 없앤다.
    // 로컬 개발: 기본값 http://127.0.0.1:8000
    const backend = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
