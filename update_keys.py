import os
import re

env_path = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\.env"

with open(env_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'KAKAO_CLIENT_ID=.*', r'KAKAO_CLIENT_ID=3159cdbb19f8d577fb7a96be6b8c3c71', content)
content = re.sub(r'NAVER_CLIENT_ID=.*', r'NAVER_CLIENT_ID=ARK6V3upIjh8kHm9FDal', content)
content = re.sub(r'NAVER_CLIENT_SECRET=.*', r'NAVER_CLIENT_SECRET=RaIWn1oEE0', content)

with open(env_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(".env updated with Kakao and Naver keys.")
