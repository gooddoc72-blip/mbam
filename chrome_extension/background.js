chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "PING") {
        sendResponse({ status: "OK", version: "1.0" });
        return true;
    }

    if (message.action === "SCRAPE_NAVER_SHOPPING") {
        const { keyword, page } = message.payload;
        
        // 1. Initial URL: Naver Main Search
        const initialUrl = `https://search.naver.com/search.naver?query=${encodeURIComponent(keyword)}`;
        // 2. Target URL: Naver Shopping
        const shoppingUrl = `https://search.shopping.naver.com/search/all?query=${encodeURIComponent(keyword)}&pagingIndex=${page}&pagingSize=40`;

        let isResponded = false;
        
        const respond = (data) => {
            if (!isResponded) {
                isResponded = true;
                sendResponse(data);
            }
        };

        let currentState = 'LOADING_SEARCH';

        chrome.tabs.create({ url: initialUrl, active: true }, (tab) => {
            const tabId = tab.id;

            chrome.tabs.onUpdated.addListener(function listener(tId, changeInfo) {
                if (tId === tabId && changeInfo.status === 'complete') {
                    
                    if (currentState === 'LOADING_SEARCH') {
                        currentState = 'WAITING';
                        // Simulate human reading time (1.5s) before clicking Shopping tab
                        setTimeout(() => {
                            if (isResponded) return;
                            currentState = 'LOADING_SHOPPING';
                            chrome.tabs.update(tabId, { url: shoppingUrl });
                        }, 1500);
                        
                    } else if (currentState === 'LOADING_SHOPPING') {
                        currentState = 'SCRAPING';
                        chrome.tabs.onUpdated.removeListener(listener);
                        
                        // Inject scraping script
                        chrome.scripting.executeScript({
                            target: { tabId: tabId },
                            func: function() {
                                return new Promise((resolve) => {
                                    // Human-like scrolling
                                    let currentScroll = 0;
                                    const scrollStep = 400; // Scroll 400px at a time
                                    const maxScroll = document.body.scrollHeight;
                                    
                                    const scrollInterval = setInterval(() => {
                                        window.scrollBy(0, scrollStep);
                                        currentScroll += scrollStep;
                                        
                                        if (currentScroll >= document.body.scrollHeight) {
                                            clearInterval(scrollInterval);
                                            
                                            // Wait 1 second after reaching the bottom for images/data to settle
                                            setTimeout(() => {
                                                // 네이버 DOM 변경에 견고하게: 여러 클래스 패턴 + 폴백(가격/리뷰 포함 카드)
                                                let items = document.querySelectorAll(
                                                    "[class^='product_item__'], [class^='basicList_item__'], " +
                                                    "[class*='product_item'], [class*='basicList_item'], " +
                                                    "[class*='adProduct_item'], [class*='basicProductCard'], " +
                                                    "[class*='superSavingProduct'], div[class*='product_list_item'], li[data-shp-page-key]"
                                                );
                                                if (!items || items.length === 0) {
                                                    items = Array.from(document.querySelectorAll('li, div')).filter((el) => {
                                                        const t = el.innerText || '';
                                                        return /원/.test(t) && /(리뷰|구매|찜|판매)/.test(t) && t.length > 10 && t.length < 800 && el.querySelector('a');
                                                    });
                                                }
                                                let results = [];
                                                items.forEach((item) => {
                                                    let text = item.innerText.replace(/\n/g, ' ');
                                                    let reviewMatch = text.match(/리뷰(?![별점])[^\d]*?([0-9,\.]+만?)/);
                                                    let purchaseMatch = text.match(/(?:구매|판매)[^\d]*?([0-9,\.]+만?)/);
                                                    let keepMatch = text.match(/찜[^\d]*?([0-9,\.]+만?)/);
                                                    let priceMatch = text.match(/([0-9,]+)원/);
                                                    let price = priceMatch ? parseInt(priceMatch[1].replace(/,/g, '')) : 0;
                                                    
                                                    // Robust title extraction: Longest text in any <a> tag
                                                    let aTags = item.querySelectorAll("a");
                                                    let title = "";
                                                    aTags.forEach(a => {
                                                        let t = a.innerText.trim();
                                                        if (t.length > title.length) title = t;
                                                    });
                                                    
                                                    if (!title || title.length < 5) {
                                                        let titleMatch = text.match(/^(.*?)(?:\s*(?:찜|리뷰|구매|무료배송))/);
                                                        title = titleMatch ? titleMatch[1].trim().substring(0, 40) : text.substring(0, 40);
                                                    } else {
                                                        title = title.substring(0, 50); // Truncate just in case
                                                    }
                                                    
                                                    const parseNum = (m) => {
                                                        if (!m) return 0;
                                                        let val = m[1].replace(/,/g, '');
                                                        if (val.includes('만')) {
                                                            return parseInt(parseFloat(val.replace('만', '')) * 10000);
                                                        }
                                                        return parseInt(parseFloat(val)) || 0;
                                                    };
                                                    
                                                    // 상품 링크(MID 포함) — 서버의 타겟 매칭용
                                                    let href = "";
                                                    const linkEl = item.querySelector("a[href*='smartstore'], a[href*='shopping.naver'], a[href*='catalog'], a[href]");
                                                    if (linkEl) href = linkEl.getAttribute("href") || "";

                                                    results.push({
                                                        title: title,
                                                        price: price,
                                                        reviews: parseNum(reviewMatch),
                                                        purchases: parseNum(purchaseMatch),
                                                        keeps: parseNum(keepMatch),
                                                        href: href,
                                                        html_content: text
                                                    });
                                                });
                                                // 진단: 추출 실패(0개 또는 전부 0) 시 실제 DOM 구조를 함께 반환
                                                const allZero = results.length > 0 && results.every(r => !r.reviews && !r.purchases && !r.keeps);
                                                const diag = {
                                                    count: items.length,
                                                    firstClass: (items[0] && items[0].className) ? items[0].className.toString().slice(0, 100) : "",
                                                    firstText: (items[0] && items[0].innerText) ? items[0].innerText.replace(/\n/g, ' ').slice(0, 250) : (document.body.innerText || "").slice(0, 250),
                                                    allZeroFields: allZero
                                                };
                                                resolve({ items: results, diag: diag });
                                            }, 1000);
                                        }
                                    }, 150); // Scroll every 150ms
                                });
                            }
                        }).then((injectionResults) => {
                            const r = injectionResults[0].result;
                            const data = Array.isArray(r) ? r : (r && r.items ? r.items : []);
                            const diag = (r && r.diag) ? r.diag : null;
                            if (diag) console.log("[MBAM-EXT] 수집 진단:", JSON.stringify(diag));
                            chrome.tabs.remove(tabId, () => chrome.runtime.lastError);
                            respond({ success: true, data: data, diag: diag });
                        }).catch(err => {
                            chrome.tabs.remove(tabId, () => chrome.runtime.lastError);
                            respond({ success: false, error: err.toString() });
                        });
                    }
                }
            });
            
            // Safety timeout: Extended to 60 seconds because of the extra navigation steps and slow networks
            setTimeout(() => {
                chrome.tabs.get(tabId, (t) => {
                    if (chrome.runtime.lastError) return; // Prevent uncaught error
                    if (t) {
                        chrome.tabs.remove(tabId, () => chrome.runtime.lastError);
                        respond({ success: false, error: "Timeout waiting for tab to load (Human Navigation)" });
                    }
                });
            }, 60000);
        });

        // Return true to indicate we will sendResponse asynchronously
        return true;
    }
});
