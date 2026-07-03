'use strict';

/**
 * qa_test.js
 * ----------------------------------------------------------------------------
 * 구글 모바일 환경 타이밍 이슈를 보완한 E2E 테스터
 * ----------------------------------------------------------------------------
 */

const puppeteer = require('puppeteer');

// ─── 검증 설정 ──────────────────────────────────────────────────────────────
const CONFIG = {
  baseUrl: process.env.BASE_URL || 'https://www.google.com',
  searchKeyword: process.env.SEARCH_KEYWORD || '돈버는 하마',
  expectedResultText: process.env.EXPECTED_RESULT_TEXT || '하마',
  selectors: {
    searchInput: 'input[name="q"]',
    resultContainer: '#search', // 구글 검색 결과 메인 영역
  },
  mobile: {
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) ' +
      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    viewport: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
  },
  assertTimeoutMs: 15_000, // 결과창을 기다려주는 시간을 15초로 넉넉하게 늘림
};

const results = [];
function record(name, passed, detail = '') {
  results.push({ name, passed, detail });
  const tag = passed ? '✅ PASS' : '❌ FAIL';
  console.log(`  ${tag}  ${name}${detail ? `  →  ${detail}` : ''}`);
}

(async () => {
  console.log('────────────────────────────────────────────────────────');
  console.log(' 모바일 UI / 검색 정합성 E2E 검증 시작');
  console.log(` 대상       : ${CONFIG.baseUrl}`);
  console.log(` 검색어     : "${CONFIG.searchKeyword}"`);
  console.log(` 기대 문자열: "${CONFIG.expectedResultText}"`);
  console.log('────────────────────────────────────────────────────────');

  const browser = await puppeteer.launch({
    headless: false, // 브라우저 창 열림 유지
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const context = await browser.createBrowserContext();

  try {
    const page = await context.newPage();
    await page.emulate(CONFIG.mobile);

    // 1) 페이지 로드
    let resp = await page.goto(CONFIG.baseUrl, { waitUntil: 'networkidle2' });
    record('페이지 로드(HTTP 200대 응답)', !!resp && resp.ok(), `status=${resp ? resp.status() : 'N/A'}`);

    // 모바일 레이아웃 검증
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return { scrollW: doc.scrollWidth, clientW: doc.clientWidth };
    });
    record('모바일 레이아웃 안정성(가로 오버플로 없음)', overflow.scrollW <= overflow.clientW + 1);

    // 2) 검색 입력창 노출 검증
    const searchInput = await page.waitForSelector(CONFIG.selectors.searchInput, { timeout: 5000 }).catch(() => null);
    record('검색 입력창 노출', !!searchInput, CONFIG.selectors.searchInput);
    if (!searchInput) throw new Error('검색창을 찾을 수 없습니다.');

    // 3) 검색어 입력 및 엔터 (타이핑 후 대기 보완)
    await searchInput.click({ clickCount: 3 });
    await page.keyboard.press('Backspace'); 
    await page.type(CONFIG.selectors.searchInput, CONFIG.searchKeyword, { delay: 150 });
    
    // 엔터 키를 누르고 구글이 화면을 그릴 시간을 의도적으로 줍니다.
    await page.keyboard.press('Enter');
    console.log('    ⏳ 구글 검색 결과 화면으로 이동 중... (잠시 기다림)');
    
    // 4) 검색 결과 영역 렌더링 대기 (★ 여기가 핵심 보완점!)
    // 화면이 검색 결과 페이지로 바뀔 때까지 최대 15초 동안 끈질기게 기다립니다.
    const resultEl = await page
      .waitForSelector(CONFIG.selectors.resultContainer, { timeout: CONFIG.assertTimeoutMs })
      .catch(() => null);
    record('검색 결과 영역 렌더링', !!resultEl, CONFIG.selectors.resultContainer);

    // 5) 결과 정합성 검증
    const resultText = resultEl
      ? await page.evaluate((el) => el.innerText || el.textContent || '', resultEl)
      : await page.evaluate(() => document.body.innerText);

    const matched = resultText.includes(CONFIG.expectedResultText);
    record(`검색 결과 정합성("${CONFIG.expectedResultText}" 노출)`, matched, matched ? '기대 문자열 확인됨' : '기대 문자열 미검출');

    if (!matched) {
      const preview = resultText.replace(/\s+/g, ' ').trim().slice(0, 200);
      console.log(`     [진단] 실제 결과 미리보기: "${preview}..."`);
    }
  } catch (e) {
    console.error(`\n[오류] ${e.message}`);
  } finally {
    // 5초간 결과를 눈으로 본 뒤 브라우저가 닫힙니다.
    await new Promise(r => setTimeout(r, 5000));
    await context.close();
    await browser.close();
  }

  // 최종 판정 출력
  const failed = results.filter((r) => !r.passed);
  console.log('────────────────────────────────────────────────────────');
  console.log(` 총 ${results.length}건  |  통과 ${results.length - failed.length}  |  실패 ${failed.length}`);
  if (failed.length === 0) {
    console.log(' 최종 판정: 🟢 합격 (PASS)');
  } else {
    console.log(' 최종 판정: 🔴 불합격 (FAIL)');
  }
  console.log('────────────────────────────────────────────────────────');
})();