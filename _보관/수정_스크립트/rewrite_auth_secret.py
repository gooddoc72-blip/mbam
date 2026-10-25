import os
import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\backend\auth.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Make SECRET_KEY look for JWT_SECRET (Review platform standard) first, then fallback
replacement = """
SECRET_KEY = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY", "mbam_super_secret_dev_key")
"""

content = re.sub(
    r'SECRET_KEY = os\.environ\.get\("JWT_SECRET_KEY", "mbam_super_secret_dev_key"\)',
    replacement.strip(),
    content
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("auth.py updated to use Review Platform JWT_SECRET")
