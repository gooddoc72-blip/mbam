const { chromium, devices } = require('playwright');
const ExcelJS = require('exceljs');
const fs = require('fs');
const path = require('path');

// config.json 파일 불러오기
const configPath = path.join(__dirname, 'config.json');
if (!fs.existsSync(configPath)) {
    console.error('config.json 파일을 찾을 수 없습니다.');
    process.exit(1);
}
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

// 유틸리티: 랜덤 딜레이 생성
const getRandomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// 엑셀 저장 함수
async function saveResultToExcel(testResult) {
    const workbook = new ExcelJS.Workbook();
    const filePath = path.join(__dirname, config.output.excelFileName);
    let worksheet;

    if (fs.existsSync(filePath)) {
        await workbook.xlsx.readFile(filePath);
        worksheet = workbook.getWorksheet('QA Results') || workbook.addWorksheet('QA Results');
    } else {
        worksheet = workbook.addWorksheet('QA Results');
        worksheet.columns = [
            { header: '테스트 일시', key: 'timestamp', width: 25 },
            { header: '타겟 URL', key: 'url', width: 30 },
            { header: '검색 키워드', key: 'keyword', width: 20 },
            { header: '기대 텍스트', key: 'expectedText', width: 30 },
            { header: '결과 (Pass/Fail)', key: 'result', width: 15 },
            { header: '상세 내용/에러', key: 'details', width: 50 },
        ];
    }

    worksheet.addRow({
        timestamp: new Date().toLocaleString('ko-KR'),
        url: testResult.url,
        keyword: testResult.keyword,
        expectedText: testResult.expectedText,
        result: testResult.passed ? 'PASS' : 'FAIL',
        details: testResult.details
    });

    await workbook.xlsx.writeFile(filePath);
    console.log(`[Excel] 테스트 결과가 ${config.output.excelFileName} 파일에 누적 저장되었습니다.`);
}

(async () => {
    console.log('====================================');
    console.log(' QA 테스트 자동화 스크립트 (Playwright)');
    console.log('====================================');

    const browserOpts = config.browserSettings;
    console.log(`\n브라우저 실행 중... (Headless: ${browserOpts.headless})`);
    
    const browser = await chromium.launch({
        headless: browserOpts.headless,
        slowMo: browserOpts.slowMo
    });

    const device = devices[browserOpts.emulateDevice] || devices['iPhone 12'];
    const context = await browser.newContext({
        ...device
    });

    const page = await context.newPage();

    for (const testCase of config.testCases) {
        let testResult = {
            url: testCase.url,
            keyword: testCase.keyword,
            expectedText: testCase.expectedText,
            passed: false,
            details: ''
        };

        try {
            console.log(`\n▶️ [Step 1] ${testCase.url} 페이지 접속 중...`);
            await page.goto(testCase.url, { waitUntil: 'networkidle' });

            console.log(`▶️ [Step 2] 검색창(${testCase.searchInputSelector}) 로드 대기 중...`);
            await page.waitForSelector(testCase.searchInputSelector, { state: 'visible', timeout: 10000 });
            await page.click(testCase.searchInputSelector);

            console.log(`▶️ [Step 3] 키워드 "${testCase.keyword}" 타이핑 시작 (랜덤 딜레이 적용)...`);
            for (const char of testCase.keyword) {
                const delay = getRandomDelay(testCase.typingDelay.min, testCase.typingDelay.max);
                await page.keyboard.type(char, { delay });
            }

            console.log('▶️ [Step 4] Enter 키 입력 및 결과 페이지 대기 중...');
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'networkidle', timeout: 15000 }).catch(() => console.log('   (페이지 이동 없음 또는 타임아웃)')),
                page.keyboard.press('Enter')
            ]);

            console.log('▶️ [Step 5] 결과 검증(Assertion) 중...');
            // 결과 페이지 전체 텍스트를 가져와 기대 텍스트가 포함되어 있는지 확인
            const bodyText = await page.innerText('body');
            
            if (bodyText.includes(testCase.expectedText)) {
                console.log(`✅ [검증 성공] 화면에 "${testCase.expectedText}" 텍스트가 존재합니다.`);
                testResult.passed = true;
                testResult.details = '기대 텍스트 매칭 성공';
            } else {
                console.log(`❌ [검증 실패] 화면에 "${testCase.expectedText}" 텍스트를 찾을 수 없습니다.`);
                testResult.passed = false;
                testResult.details = '화면 내 기대 텍스트 누락';
            }

        } catch (error) {
            console.error(`❌ [에러 발생] 테스트 실행 중 오류 발생: ${error.message}`);
            testResult.passed = false;
            testResult.details = error.message;
        }

        // 결과 엑셀 저장
        await saveResultToExcel(testResult);
        // 안정성을 위해 다음 케이스 전 잠시 대기
        await page.waitForTimeout(2000);
    }

    console.log('\n모든 테스트 시나리오 종료. 브라우저를 닫습니다.');
    await browser.close();
})();
