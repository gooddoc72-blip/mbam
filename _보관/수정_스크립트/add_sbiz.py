import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\services\gov_data.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add to CATEGORIES
old_categories = '"기업마당 (Bizinfo)": "중소기업/소상공인 지원사업 정보",'
new_categories = '"소상공인24 (sbiz24)": "소상공인 맞춤형 정부지원사업 및 정책자금",\n        "기업마당 (Bizinfo)": "중소기업/소상공인 지원사업 정보",'

content = content.replace(old_categories, new_categories)

# Add AI parsing rules for the new category
old_rules = 'if category == "기업마당 (Bizinfo)":'
new_rules = '''if category == "소상공인24 (sbiz24)":
            source_focus = "소상공인24 (sbiz24.kr)"
            custom_fields = '"application_period": "신청기간", "support_target": "지원대상(예: 매출액 3억 이하)",'
        elif category == "기업마당 (Bizinfo)":'''

content = content.replace(old_rules, new_rules)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("gov_data.py updated with 소상공인24 category")
