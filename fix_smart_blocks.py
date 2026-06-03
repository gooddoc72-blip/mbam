import re

def fix_search_smart_blocks():
    file_path = 'mbam_nextgen/services/seo_analyzer.py'
    content = open(file_path, encoding='utf-8').read()
    
    js_addition = """
                            if (a.dataset && a.dataset.url) {
                                href = a.dataset.url;
                            }
                            
                            // 🚀 [추가된 로직] 블로그 홈, 카페 홈 필터링
                            try {
                                let urlObj = new URL(href);
                                if (href.includes("blog.naver.com")) {
                                    // logNo가 없고, 경로에 포스트 번호가 없으면 블로그 홈
                                    if (!urlObj.searchParams.has("logNo") && !urlObj.pathname.match(/\\/[^/]+\\/\\d+/)) {
                                        return;
                                    }
                                }
                                if (href.includes("cafe.naver.com")) {
                                    // 개별 글 파라미터가 없으면 홈
                                    if (!href.includes("art=") && !href.includes("articleid=") && !urlObj.pathname.match(/\\/[a-zA-Z0-9_-]+\\/\\d+/)) {
                                        return;
                                    }
                                }
                            } catch(e) {}
                            
                            if (title.length > 2 && !seenUrls.has(href)) {"""
                            
    # The existing code is:
    #                             if (a.dataset && a.dataset.url) {
    #                                 href = a.dataset.url;
    #                             }
    #                             
    #                             if (title.length > 2 && !seenUrls.has(href)) {
    
    pattern = re.compile(r'                            if \(a\.dataset && a\.dataset\.url\) \{\s*href = a\.dataset\.url;\s*\}\s*if \(title\.length > 2 && !seenUrls\.has\(href\)\) \{')
    if pattern.search(content):
        new_content = pattern.sub(js_addition, content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS")
    else:
        print("FAIL TO MATCH")

fix_search_smart_blocks()
