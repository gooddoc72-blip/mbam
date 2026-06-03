from bs4 import BeautifulSoup
import re

with open('naver_shopping_dump.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

items = soup.find_all('div', class_=re.compile(r'product_item__.*|basicList_item__.*'))
print(f"Found {len(items)} items.")

for idx, item in enumerate(items[:3]):
    text = item.get_text(" ", strip=True)
    print(f"--- Item {idx+1} ---")
    print(text)
    
    review_match = re.search(r'리뷰\s*([0-9,]+)', text)
    if not review_match:
        # Check for parentheses format: ★ 4.89 (6,656)
        review_match = re.search(r'\(([\d,]+)\)', text)
        
    purchase_match = re.search(r'구매\s*([0-9,]+)', text)
    keep_match = re.search(r'찜\s*([0-9,]+)', text)
    
    print('Reviews:', review_match.group(1) if review_match else 'None')
    print('Purchases:', purchase_match.group(1) if purchase_match else 'None')
    print('Keeps:', keep_match.group(1) if keep_match else 'None')
