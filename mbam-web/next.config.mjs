import path from 'node:path';
import { fileURLToPath } from 'node:url';

// 이 파일이 있는 폴더(= mbam-web 또는 설치형 빌드용 사본)
const webRoot = path.dirname(fileURLToPath(import.meta.url));
const standalone = process.env.NEXT_OUTPUT_STANDALONE === '1';

/** @type {import('next').NextConfig} */
const nextConfig = {
  // 설치형 빌드(installer\build_*_payload.ps1)만 NEXT_OUTPUT_STANDALONE=1 로 켠다.
  // 실행에 실제로 필요한 node_modules 만 추려 .next\standalone 에 담아 주므로
  // 설치 파일 수가 1만 8천 개 → 수백 개로 줄어 설치가 빨라진다.
  // 웹 배포·개발 서버(next dev / next start)는 그대로다.
  // 추적 기준 폴더를 이 폴더로 고정한다. 안 그러면 저장소 루트의 package-lock.json 을 보고
  // 저장소 전체를 기준으로 잡아, 산출물이 standalone\installer\.cache\...\server.js 처럼
  // 경로 구조째로 나온다(설치 폴더에 그대로 놓을 수 없음).
  ...(standalone ? { output: 'standalone', outputFileTracingRoot: webRoot, turbopack: { root: webRoot } } : {}),
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
