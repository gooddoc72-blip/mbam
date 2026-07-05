// 병원 블로그 전용 라우트. 블로그 발행과 동일 페이지를 렌더하되 경로가 /hospital-blog 라서
// 페이지가 병원 카테고리(promoType=hospital)로 자동 세팅되고(의료법 프롬프트+나노바나나 이미지),
// 사이드바에서도 '병원 블로그'가 독립적으로 활성표시된다.
export { default } from "../blog-posting/page";
