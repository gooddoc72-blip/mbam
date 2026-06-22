/** @type {import('next').NextConfig} */
const nextConfig = {
  // dev rewrite 프록시 기본 타임아웃은 30초. 글감수집은 백그라운드 작업+폴링으로 전환해
  // 더는 이 한도에 걸리지 않지만, Playwright 기반 SEO 분석 등 다른 장시간 엔드포인트를
  // 위한 dev 안전망으로 120초 유지.
  experimental: {
    proxyTimeout: 120000,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
