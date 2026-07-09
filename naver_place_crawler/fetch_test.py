import urllib.request
import gzip

req = urllib.request.Request(
    'https://www.coupang.com/np/search?q=%EB%94%94%ED%93%A8%EC%A0%80',
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1'
    }
)
try:
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read()
        if response.info().get('Content-Encoding') == 'gzip':
            html = gzip.decompress(html)
        html = html.decode('utf-8', 'ignore')
        import re
        paginations = re.findall(r'<div[^>]*pagination[^>]*>.*?</div>', html, re.DOTALL | re.IGNORECASE)
        print('Pagination Divs:', len(paginations))
        if paginations:
            print(paginations[0])
        else:
            print('No pagination found. Blocked?')
            print(html[:500])
except Exception as e:
    print('Error:', e)
