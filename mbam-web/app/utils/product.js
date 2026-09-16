// 제품 프로파일 — 하나의 코드베이스로 여러 설치본을 만든다.
//
//   mbam (기본) : 마케팅 연구소 풀버전
//   cafe        : 네이버 카페 전용판 (별도 설치형 · 기기 승인)
//   blog        : 블로그 자동화 전용판 (별도 설치형 · 기기 승인)
//
// 빌드 시점에 NEXT_PUBLIC_PRODUCT 로 결정된다(Next.js 가 값을 인라인하므로
// 런타임에 바뀌지 않는다). 각 설치 페이로드 빌드 스크립트가
// NEXT_PUBLIC_PRODUCT 를 지정해 빌드하고, 그 제품과 무관한 page 폴더는 아예 제외한다.
export const PRODUCT = (process.env.NEXT_PUBLIC_PRODUCT || "mbam").toLowerCase();

export const IS_CAFE_EDITION = PRODUCT === "cafe";
export const IS_BLOG_EDITION = PRODUCT === "blog";

// 설치형(단독 실행 · 로그인 화면 없음 · 기기 승인으로 관리)인지.
// 로그인/회원가입 화면이 없다는 뜻이라, 인증·리다이렉트 분기는 전부 이 값을 봐야 한다.
// (예전엔 IS_CAFE_EDITION 이 이 역할을 겸했다 — 설치형이 카페 하나뿐이었기 때문)
export const IS_STANDALONE = IS_CAFE_EDITION || IS_BLOG_EDITION;

// 로그인 직후·루트 접근 시 보낼 첫 화면. 설치형에는 대시보드가 없다.
export const HOME_PATH = IS_CAFE_EDITION
  ? "/cafe-auto"
  : IS_BLOG_EDITION
    ? "/blog-posting"
    : "/dashboard";

export const PRODUCT_NAME = IS_CAFE_EDITION
  ? "카페 마케팅"
  : IS_BLOG_EDITION
    ? "블로그 마케팅"
    : "마케팅연구소";

// 사이드바 제목·버튼 등에 쓰는 제품 강조색 (설치 아이콘 색과 맞춘다)
export const BRAND_COLOR = IS_CAFE_EDITION
  ? "#16a34a"   // 카페 = 녹색
  : IS_BLOG_EDITION
    ? "#2563eb" // 블로그 = 파랑
    : "#3b82f6";

export const PRODUCT_TAGLINE = IS_CAFE_EDITION
  ? "Cafe Marketing Edition"
  : IS_BLOG_EDITION
    ? "Blog Marketing Edition"
    : "Marketing lab's";
