import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\backend\main.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified successfully.")
except Exception as e:
    print(f"[Warning] Failed to connect to database during startup: {e}")
"""

content = re.sub(r'Base\.metadata\.create_all\(bind=engine\)', replacement.strip(), content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("main.py DB connection wrapped in try-except")
