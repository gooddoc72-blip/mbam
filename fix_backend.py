import sys
import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\services\seo_analyzer.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove module-level fetch_related_keywords and fetch_keyword_volumes
# Find from 'async def fetch_related_keywords(keyword: str) -> list:' to '# We will inject these into SeoAnalyzer'
import re
content = re.sub(r'async def fetch_related_keywords\(keyword: str\).*?# We will inject these into SeoAnalyzer\s+', '', content, flags=re.DOTALL)

# 2. Fix type parsing in analyze_keyword
content = content.replace(
    '"type": "선택된 포스팅",',
    '"type": "인플루언서" if "in.naver.com" in url else "인기카페" if "cafe.naver.com" in url else "인기블로그",'
)
content = content.replace(
    '"type": "?택???스??,', # encoded version just in case
    '"type": "인플루언서" if "in.naver.com" in url else "인기카페" if "cafe.naver.com" in url else "인기블로그",'
)

# 3. Fix smart block parsing (monthlyPcQcCnt -> pc, monthlyMobileQcCnt -> mobile, relKeyword -> keyword)
content = content.replace(
    "vol_data[0].get('monthlyPcQcCnt', 0)",
    "vol_data[0].get('pc', 0)"
)
content = content.replace(
    "vol_data[0].get('monthlyMobileQcCnt', 0)",
    "vol_data[0].get('mobile', 0)"
)
content = content.replace(
    "vkw = v.get('relKeyword', '').replace(' ', '')",
    "vkw = v.get('keyword', '').replace(' ', '')"
)
content = content.replace(
    "'pc': v.get('monthlyPcQcCnt', 0)",
    "'pc': v.get('pc', 0)"
)
content = content.replace(
    "'mo': v.get('monthlyMobileQcCnt', 0)",
    "'mo': v.get('mobile', 0)"
)

# 4. asyncio.sleep -> page.wait_for_timeout
content = content.replace("await asyncio.sleep(2)", "await page.wait_for_timeout(2000)")

# 5. paragraph_count removal
content = re.sub(r'paragraph_count = max\(1, raw_text\.count\("\\n"\) \+ 1\)\s+', '', content)
content = re.sub(r'"paragraph_count": paragraph_count,\s+', '', content)

# 6. import asyncio duplicate removal
content = content.replace("import asyncio\nimport re\nimport asyncio", "import asyncio\nimport re")

# 7. AI timeout 15 to 12
content = content.replace("asyncio.wait_for(task, timeout=15.0)", "asyncio.wait_for(task, timeout=12.0)")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Backend bug fixes applied successfully.")
