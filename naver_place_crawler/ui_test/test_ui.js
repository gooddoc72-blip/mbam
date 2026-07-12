const { chromium, devices } = require('playwright');

(async () => {
    console.log('UI 테스트 브라우저를 모바일 환경(360x800)으로 실행합니다...');
    
    // Playwright 브라우저 실행
    const browser = await chromium.launch({
        headless: false, // UI 동작을 확인하기 위해 창을 띄움
    });

    const context = await browser.newContext({
        viewport: { width: 360, height: 800 },
        isMobile: true,
        hasTouch: true,
        userAgent: devices['iPhone 12'].userAgent
    });

    const page = await context.newPage();

    try {
        const targetUrl = 'https://example.com'; // 테스트할 자사 서비스 타겟 URL로 변경하세요.
        console.log(`타겟 페이지(${targetUrl})로 이동 중...`);
        
        await page.goto(targetUrl, { waitUntil: 'networkidle' });
        console.log('페이지 로드 완료. 검색창 요소를 대기합니다.');

        // 테스트할 검색창의 실제 CSS 선택자로 변경하세요. (예: '#searchInput', '.search-box input')
        const searchInputSelector = 'input[type="text"]'; 
        
        // 검색창이 화면에 나타날 때까지 대기
        await page.waitForSelector(searchInputSelector, { state: 'visible', timeout: 5000 }).catch(() => {
            console.log('지정된 검색창을 찾지 못했습니다. 선택자를 확인해 주세요.');
        });
        
        const isVisible = await page.isVisible(searchInputSelector);

        if (isVisible) {
            console.log('검색창 요소를 찾았습니다. 텍스트를 입력합니다...');
            const textToType = '테스트 검색어';
            
            await page.click(searchInputSelector);

            // 한 글자당 100~350ms의 랜덤 딜레이를 주며 사람처럼 입력
            for (const char of textToType) {
                const randomDelay = Math.floor(Math.random() * 251) + 100; // 100 ~ 350
                await page.keyboard.type(char, { delay: randomDelay });
            }

            console.log('입력 완료. 엔터 키를 입력합니다...');
            
            // 엔터를 치고 다음 결과 페이지가 로드될 때까지 대기
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'networkidle', timeout: 10000 }).catch(() => console.log('결과 페이지 로드 대기 시간 초과 또는 페이지 이동이 발생하지 않았습니다.')),
                page.keyboard.press('Enter')
            ]);

            console.log('결과 페이지 렌더링 확인을 위해 화면을 아래로 스크롤합니다...');
            
            // 페이지 아래로 스크롤하여 콘텐츠 렌더링 확인 (지연 로딩 대응)
            for (let i = 0; i < 4; i++) {
                await page.evaluate(() => {
                    window.scrollBy(0, window.innerHeight * 0.7);
                });
                await page.waitForTimeout(1500); // 스크롤 후 1.5초 대기
            }
            
            console.log('스크롤 테스트 완료. 모든 렌더링이 정상적으로 호출되었습니다.');
            // (선택 사항) 최종 스크린샷 저장
            // await page.screenshot({ path: 'test_result.png' });

        }

    } catch (error) {
        console.error('테스트 중 오류가 발생했습니다:', error);
    } finally {
        console.log('테스트 세션을 안전하게 종료하고 브라우저를 닫습니다.');
        await browser.close();
    }
})();
