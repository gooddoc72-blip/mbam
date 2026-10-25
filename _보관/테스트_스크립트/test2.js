const fs = require('fs');
const jsdom = require('jsdom');
const { JSDOM } = jsdom;
const html = fs.readFileSync('search_test.html', 'utf8');
const dom = new JSDOM(html);
const document = dom.window.document;

(() => {
    const results = [];
    const rel_kws = [];
    
    const containers = document.querySelectorAll('section, div.api_subject_bx, .fds-ugc-block, .place_section, .api_custom_bx, .sc_new');
    const seenBlockHashes = new Set();
    
    containers.forEach(container => {
        let titleEl = container.querySelector('h2, h3, .api_title, .title, .tit, [role="heading"], .subject_title, .api_tit, .place_section_header .name');
        let blockTitle = titleEl ? titleEl.innerText || titleEl.textContent : "결과 없음";
        blockTitle = blockTitle.trim();
        
        if (blockTitle.includes("함께 많이 찾는")) {
            return;
        }

        if (!blockTitle || blockTitle === "결과 없음" || blockTitle.includes("검색어")) return;

        if (blockTitle !== "광고" && blockTitle !== "이미지 클립" && !blockTitle.includes("플레이스") && !blockTitle.includes("클립") && !blockTitle.includes("카페") && !blockTitle.includes("블로그") && !blockTitle.includes("인기") && !blockTitle.includes("최신") && !blockTitle.includes("브랜드 콘텐츠") && !blockTitle.includes("파워링크") && !blockTitle.includes("함") && blockTitle.length <= 25) {
            rel_kws.push(blockTitle);
        }

        let links = [];
        let aTags = container.querySelectorAll('a[href]');
        const seenUrls = new Set();
        
        aTags.forEach(a => {
            let href = a.href;
            if (!href || href.startsWith('javascript:')) return;
            if (href.includes('#lb_api')) return;
            
            let isAd = a.closest('.sp_power, .powerlink, [class*="ad_"], .sponsored, .ad');
            if (isAd) return;
            
            let titleEl = a.querySelector('.YwYwt, .place_bluelink, .name, .tit, .title, .Fc1rA');
            let title = "";
            if (titleEl) {
                title = (titleEl.innerText || titleEl.textContent || "").trim().replace(/[\r\n]+/g, ' ');
            } else {
                title = (a.innerText || a.textContent || "").trim().replace(/[\r\n]+/g, ' ');
            }
            if (!title) return;

            if (href.includes("m.search.naver.com/search.naver") && href.includes("url=")) {
                try {
                    let urlObj = new URL(href);
                    let realUrl = urlObj.searchParams.get("url");
                    if (realUrl) href = decodeURIComponent(realUrl);
                } catch (e) {}
            }
            

            if (a.dataset && a.dataset.url) {
                href = a.dataset.url;
            }
            
            try {
                let urlObj = new URL(href);
                if (href.includes('blog.naver.com')) {
                    if (!urlObj.searchParams.has('logNo') && !urlObj.pathname.match(/\/[^/]+\/\d+/)) { return; }
                }
                if (href.includes('cafe.naver.com')) {
                    if (!href.includes('art=') && !href.includes('articleid=') && !urlObj.pathname.match(/\/[a-zA-Z0-9_-]+\/\d+/)) { return; }
                }
            } catch(e) {}
            
            if (title.length > 2 && !seenUrls.has(href)) {
                seenUrls.add(href);
                
                let type = "기타";
                if (href.includes("blog.naver.com")) type = "블로그";
                else if (href.includes("cafe.naver.com")) type = "카페";
                else if (href.includes("in.naver.com") || href.includes("influencer")) type = "플레";
                else if (href.includes("youtube.com") || href.includes("tv.naver.com") || href.includes("clip.naver.com") || href.includes("m.wev.naver.com")) type = "숏/영";
                else if (href.includes("post.naver.com")) type = "포스트";
                else if (href.includes("place.naver.com") || href.includes("map.naver.com") || href.includes("store.naver.com")) type = "플레이스";

                let cleanTitle = title.substring(0, 80);
                links.push({ title: cleanTitle, url: href, type: type });
            }
        });

        if (links.length > 0) {
            if (links[0].type === "인플루언서" && !blockTitle.includes("인플루언서")) {
                blockTitle = "인플루언서 | " + blockTitle;
            } else if (links[0].type === "카페" && !blockTitle.includes("카페")) {
                blockTitle = "카페 | " + blockTitle;
            } else if (links[0].type === "플레이스" && !blockTitle.includes("플레이스")) {
                blockTitle = "플레이스 | " + blockTitle;
            }
            
            const blockHash = links.map(l => l.url).join('|');
            if (!seenBlockHashes.has(blockHash)) {
                seenBlockHashes.add(blockHash);
                results.push({
                    block_title: blockTitle,
                    links: links.slice(0, 15)
                });
            }
        }
    });
    console.log('RESULTS:', JSON.stringify(results.filter(b => b.block_title.includes('클립') || b.block_title.includes('광안리 한식 맛집')), null, 2));
})();
