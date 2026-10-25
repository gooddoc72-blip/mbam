import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam-web\components\SeoResults.jsx"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix maxCount calculation
content = content.replace(
    "const maxCount = top_keywords[0].count;",
    "const maxCount = Math.max(...top_keywords.map(k => k.count), 1);"
)

# Fix author block rendering condition if it's missing blog info
# Current condition: {m.cafe_author_info && m.cafe_author_info.nickname && (
# Replace with: {(m.cafe_author_info?.nickname || m.blog_info?.blog_id) && (
content = content.replace(
    "{m.cafe_author_info && m.cafe_author_info.nickname && (",
    "{(m.cafe_author_info?.nickname || m.blog_info?.blog_id) && ("
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Frontend bug fixes applied successfully.")
