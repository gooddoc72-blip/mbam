import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam-web\app\dashboard\page.js"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the alert logic in fetchHistory
replacement = """
      if (res.status === 401) return; // fetchWithAuth will handle the redirect
      
      const json = await res.json();
      if (json.success) {
        setData(json.data);
      } else {
        alert("데이터를 불러오는데 실패했습니다: " + (json.error || json.detail || "서버 오류"));
        setData([]);
      }
"""

content = re.sub(
    r'const json = await res\.json\(\);\s*if \(json\.success\) \{\s*setData\(json\.data\);\s*\} else \{\s*alert\("데이터를 불러오는데 실패했습니다: " \+ json\.error\);\s*setData\(\[\]\);\s*\}',
    replacement.strip(),
    content,
    flags=re.DOTALL
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard/page.js patched for better error handling.")
