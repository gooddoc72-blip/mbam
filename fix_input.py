filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam-web\app\login\page.js"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('type="email"', 'type="text"')
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Login page input type changed to text.")
