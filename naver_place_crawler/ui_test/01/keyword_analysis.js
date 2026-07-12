'use strict';

// 🎭 포털 방화벽 우회를 위한 스텔스 패키지 로드
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const { execSync } = require('child_process');

// 헬퍼 함수
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const getRandomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

const CONFIG = {
  baseUrl: 'https://www.google.com',            // 분석 대상 포털
  searchKeyword: '돈버는 하마',                  // 검색할 키워드
  expectedResultText: '하마',                    // 화면에 노출되어야 하는 기대 단어
  selectors: {
    searchInput: 'input[name="q"]',
    resultContainer: '#search',
  },
  // 모바일 에뮬레이션 (iPhone 12 기준)
  mobile: {
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    viewport: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
  }
};

/**
 * [1단계] 스마트폰 adb 명령어를 통해 모바일 데이터를 껐다 켜서 IP를 변경
 */
async function resetMobileIp() {
  console.log('\n────────────────────────────────────────────────────────');
  console.log('[1단계] 네트워크 리셋 실행 (모바일 데이터 ON/OFF)');
  console.log('────────────────────────────────────────────────────────');
  try {
    execSync('adb shell svc data disable');
    await sleep(2000);
    execSync('adb shell svc data enable');
    console.log('⏳ 통신사 새 IP 할당 및 네트워크 안정화 대기 중 (7초)...');
    await sleep(7000);
    console.log('✅ [네트워크 재설정] 성공! 새로운 깨끗한 IP로 전환되었습니다.');
  } catch (e) {
    console.log('⚠️ [네트워크 재설정] 옥에 티: 연결된 기기를 찾지 못했습니다. (adb devices 결과 없음)');
    console.log('    USB 연결과 USB 디버깅 허용 여부를 확인해 주세요.');
    console.log('    (현재는 IP 변경 없이 기존 PC 인터넷으로 검증을 계속 진행합니다.)');
  }
}

/**
 * [2단계] 모바일 UI 및 검색 노출 정합성 검증
 */
async function verifyKeywordExposure() {
  console.log('\n────────────────────────────────────────────────────────');
  console.log(' [2단계] 모바일 UI 및 검색 정합성 검증 시작');
  console.log(` 대상       : ${CONFIG.baseUrl}`);
  console.log(` 검색어     : "${CONFIG.searchKeyword}"`);
  console.log(` 기대 문자열: "${CONFIG.expectedResultText}"`);
  console.log('────────────────────────────────────────────────────────');

  const browser = await puppeteer.launch({
    headless: false, // 눈으로 검증 과정을 볼 수 있게 브라우저 창을 켬
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
  });

  const page = await browser.newPage();
  await page.emulate(CONFIG.mobile);

  // 로봇 전광판 숨기기 가속화
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });

  try {
    // 1. 페이지 로드 검증
    const resp = await page.goto(CONFIG.baseUrl, { waitUntil: 'networkidle2' });
    if (resp && resp.ok()) {
      console.log(`  ✅ PASS  페이지 로드 성공  →  status=${resp.status()}`);
    } else {
      console.log('  ❌ FAIL  페이지 로드 실패');
      return;
    }

    // 2. 모바일 레이아웃 안정성 검증
    const overflow = await page.evaluate(() => {
      return { scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth };
    });
    if (overflow.scrollW <= overflow.clientW + 1) {
      console.log(`  ✅ PASS  모바일 레이아웃 안정성 (가로 오버플로 없음)`);
    }

    // 3. 검색창 확인 및 인간형 타이핑 연출 (자전거 창 차단 우회)
    await page.waitForSelector(CONFIG.selectors.searchInput, { timeout: 5000 });
    await page.click(CONFIG.selectors.searchInput);
    
    console.log('  ⌨️  로봇 의심 방지를 위해 사람 속도로 키워드 입력 중...');
    for (const char of CONFIG.searchKeyword) {
      await page.type(CONFIG.selectors.searchInput, char);
      await sleep(getRandomDelay(120, 255)); // 0.12초 ~ 0.25초 사이의 무작위 타이핑 속도!
    }
    await sleep(500);
    await page.keyboard.press('Enter');
    
    // 검색 결과 화면 대기
    await page.waitForSelector(CONFIG.selectors.resultContainer, { timeout: 15000 }).catch(() => null);
    await sleep(2000); // 안정적인 렌더링을 위한 추가 휴식

    // 4. 최종 검색 결과 노출 정합성 검증
    const pageText = await page.evaluate(() => document.body.innerText);
    if (pageText.includes(CONFIG.expectedResultText)) {
      console.log(`  ✅ PASS  검색 결과 정합성 완료 ("${CONFIG.expectedResultText}" 노출 확인)`);
      console.log('\n 🏆 최종 판정: 🟢 합격 (PASS)');
    } else {
      console.log(`  ❌ FAIL  검색 결과 정합성 실패 ("${CONFIG.expectedResultText}" 미검출)`);
      console.log('\n 🏆 최종 판정: 🔴 불합격 (FAIL)');
    }

  } catch (error) {
    console.log(`\n❌ 검증 중 에러 발생: ${error.message}`);
  } finally {
    await sleep(3000); // 결과 확인 대기 후 종료
    await browser.close();
    console.log('────────────────────────────────────────────────────────');
  }
}

// 공장 가동
(async () => {
  // [1단계] 핸드폰 데이터로 IP 신선하게 바꾸고
  await resetMobileIp();
  // [2단계] 안티그래비티 급 위장술로 포털 검색창 노출 검증 진행
  await verifyKeywordExposure();
})();