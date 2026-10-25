import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\services\gov_data.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix open(env_path, 'r') to open(env_path, 'r', encoding='utf-8')
content = content.replace("open(env_path, 'r')", "open(env_path, 'r', encoding='utf-8')")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("gov_data.py encoding fixed")
