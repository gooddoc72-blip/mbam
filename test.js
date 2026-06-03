const fs = require('fs');
const jsdom = require('jsdom');
const { JSDOM } = jsdom;
const html = fs.readFileSync('search_test.html', 'utf8');
const dom = new JSDOM(html);
const document = dom.window.document;

const containers = document.querySelectorAll('section, div.api_subject_bx, .fds-ugc-block, .place_section, .api_custom_bx, .sc_new');
containers.forEach(container => {
    let titleEl = container.querySelector('h2, h3, .api_title, .title, .tit, [role="heading"], .subject_title, .api_tit, .place_section_header .name');
    let blockTitle = titleEl ? titleEl.textContent.trim() : '결과 없음';
    if (!blockTitle || blockTitle === '결과 없음' || blockTitle.includes('검색어')) return;

    let links = [];
    let aTags = container.querySelectorAll('a[href]');
    const seenUrls = new Set();
    
    aTags.forEach(a => {
        let href = a.href;
        if (!href || href.startsWith('javascript:')) return;
        if (href.includes('#lb_api')) return;
        
        let titleEl = a.querySelector('.YwYwt, .place_bluelink, .name, .tit, .title, .Fc1rA');
        let title = '';
        if (titleEl) {
            title = titleEl.textContent.trim().replace(/[\r\n]+/g, ' ');
        } else {
            title = a.textContent.trim().replace(/[\r\n]+/g, ' ');
        }
        if (!title) return;

        if (a.dataset && a.dataset.url) {
            href = a.dataset.url;
        }
        
        try {
            let urlObj = new URL(href);
            if (href.includes('blog.naver.com')) {
                if (!urlObj.searchParams.has('logNo') && !urlObj.pathname.match(/\/[^/]+\/\d+$/) && !href.includes('/clip/')) { return; }
            }
            if (href.includes('cafe.naver.com')) {
                if (!href.includes('art=') && !href.includes('articleid=') && !urlObj.pathname.match(/\/[a-zA-Z0-9_-]+\/\d+$/)) { return; }
            }
        } catch(e) {}
        
        if (title.length > 2 && !seenUrls.has(href)) {
            seenUrls.add(href);
            links.push({ title: title, url: href });
        }
    });

    if (links.length > 0) {
        if (blockTitle.includes('광안리 한식 맛집') || blockTitle.includes('클립')) {
            console.log('BLOCK:', blockTitle);
            links.forEach(l => console.log('  - ' + l.title));
        }
    }
});
