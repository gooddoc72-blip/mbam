import re
filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam-web\app\login\page.js"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the social login buttons
content = re.sub(
    r'<div className="mt-8 pt-6 border-t border-gray-700">.*?</div>\s*</div>\s*</div>',
    '</div></div></div>',
    content,
    flags=re.DOTALL
)

# Remove the signup link
content = re.sub(
    r'<p className="mt-6 text-center text-sm text-gray-400">.*?회원가입</a>\s*</p>',
    '<p className="mt-6 text-center text-sm text-gray-400">리뷰 플랫폼(광고주/대행사/총판) 계정으로 로그인하세요.</p>',
    content,
    flags=re.DOTALL
)

# Change the title
content = content.replace('MBAM Platform 로그인', 'MBAM 통합 로그인 (SSO)')
content = content.replace('이메일 (Email)', '아이디 또는 이메일')
content = content.replace('placeholder="이메일을 입력하세요"', 'placeholder="광고주 이메일 또는 대행사/총판 아이디"')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("login page updated for SSO")
