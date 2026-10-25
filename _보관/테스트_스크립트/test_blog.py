import requests
from bs4 import BeautifulSoup
import re

url = "https://blog.naver.com/PostView.naver?blogId=loooong_&logNo=223405791787"
res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
soup = BeautifulSoup(res.text, 'html.parser')
content_div = soup.select_one('.se-main-container, #postViewArea')
if content_div:
    text = content_div.get_text(separator='\n', strip=True)
    print("SUCCESS, length:", len(text))
    print(text[:100])
else:
    print("FAIL")
