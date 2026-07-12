'use strict';

// [수정 완료] 일반 puppeteer 대신 우회 기능이 강화된 puppeteer-extra 사용
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');

// 스텔스 플러그인 활성화 (쿠팡 방화벽을 속이는 위장 크림)
puppeteer.use(StealthPlugin());

const { execSync } = require('child_process');

// 헬퍼 함수: 지정한 밀리초(ms)만큼 대기
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// 헬퍼 함수: 범위 내 무작위 정수 반환 (인간형 타이핑용)
const getRandomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

/**
 * ⚡ 스마트폰 adb 명령어를 통해 모바일 데이터를 껐다 켜서 IP를 변경하는 함수
 */
async function resetMobileIp() {
  console.log('\n=========================================');
  console.log('[⚡ 1단계] 스마트폰 테더링 IP 리셋 시작');
  console.log('=========================================');
  try {
    execSync('adb shell svc data disable');
    await sleep(2000);
    execSync('adb shell svc data enable');
    console.log('⏳ 통신사 새 IP 할당 대기 중 (7초)...');
    await sleep(7000);
    console.log('✅ 새 IP 변경 및 네트워크 안정화 완료!');
  } catch (e) {
    console.log(`⚠️ ADB 리셋 실패 (케이블 상태를 확인해 주세요): ${e.message}`);
    console.log('🔄 현재 PC 인터넷 상태로 크롤링을 계속 진행합니다.');
  }
}

/**
 * 🛒 쿠팡/네이버 안전 크롤링 함수 (스텔스 모드 적용)
 */
async function runCrawler() {
  console.log('\n=========================================');
  console.log('[🛒 2단계] 네이버/쿠팡 안전 크롤링 시작');
  console.log('=========================================');

  // 브라우저 실행 (포털이 자동화 프로그램인 것을 눈치채지 못하게 인자값 추가)
  const browser = await puppeteer.launch({
    headless: false,
    args: [
      '--no-sandbox', 
      '--disable-setuid-sandbox', 
      '--window-size=1200,900',
      '--disable-blink-features=AutomationControlled' // 로봇 전광판 숨기기
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 800 });

  // 웹 브라우저 언어 및 핑거프린트 사람처럼 위장
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });

  try {
    // 1. 쿠팡 검색 검증
    console.log('▶️ 쿠팡 접속 중...');
    // 쿠팡의 엄격한 보안을 고려해 실제 사람이 검색창을 누르는 동선을 연출합니다.
    await page.goto('https://www.coupang.com', { waitUntil: 'networkidle2' });
    await sleep(3000);

    const coupangInput = '#headerSearchKeyword';
    await page.waitForSelector(coupangInput, { timeout: 5000 });
    await page.click(coupangInput);
    await sleep(500);

    console.log('⌨️ 쿠팡 검색창 키워드 타이핑 중 (인간형 딜레이 작동)...');
    for (const char of '커클랜드') {
      await page.type(coupangInput, char);
      await sleep(getRandomDelay(120, 250)); // 타이핑 속도를 조금 더 인간답게 조정
    }
    await sleep(500);
    
    await page.keyboard.press('Enter');
    // 네비게이션이 완료될 때까지 최대 15초 대기
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
    await sleep(3000);
    console.log('   - 쿠팡 결과 페이지 이동 완료:', page.url().substring(0, 60) + '...');

    // 2. 네이버 지도 검색 검증
    console.log('\n▶️ 네이버 지도 접속 중...');
    await page.goto('https://map.naver.com/p', { waitUntil: 'networkidle2' });
    await sleep(3000);

    const naverInput = '.input_search';
    await page.waitForSelector(naverInput, { timeout: 5000 });
    await page.click(naverInput);
    await sleep(500);

    console.log('⌨️ 네이버 검색창 키워드 타이핑 중 (인간형 딜레이 작동)...');
    for (const char of '스타벅스') {
      await page.type(naverInput, char);
      await sleep(getRandomDelay(120, 250));
    }
    await sleep(500);

    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
    await sleep(3000);
    console.log('   - 네이버 결과 페이지 이동 완료:', page.url().substring(0, 60) + '...');

  } catch (error) {
    console.log(`❌ 크롤링 중 에러 발생: ${error.message}`);
  } finally {
    await browser.close();
    console.log('🚪 브라우저 안전하게 닫힘');
  }
}

/**
 * 메인 가동 블록
 */
(async () => {
  let loopCount = 1;
  try {
    while (true) {
      console.log(`\n🚀 [마스터 루프 ${loopCount}회차 구동 시작]`);
      await resetMobileIp();
      await runCrawler();
      console.log(`\n⏳ ${loopCount}회차 성공 완료. 20초 대기 후 다음 새 IP로 전환합니다...`);
      await sleep(20000);
      loopCount++;
    }
  } catch (e) {
    console.log('\n🛑 시스템 예기치 못한 종료:', e.message);
  }
})();