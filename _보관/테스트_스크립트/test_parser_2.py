from bs4 import BeautifulSoup
import re

with open('naver_shopping_dump.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find any element containing '찜'
zzim_elements = soup.find_all(string=re.compile(r'찜'))
for z in zzim_elements:
    parent = z.find_parent('div', class_=True)
    while parent:
        if 'product' in str(parent.get('class')) or 'item' in str(parent.get('class')):
            print("Found potential container class:", parent.get('class'))
            break
        parent = parent.find_parent('div', class_=True)

# Also let's just find the divs with "adProduct_item__" or something similar
items = soup.find_all('div', class_=re.compile(r'.*item__.*'))
print("Found items with *item__*:", len(items))
if items:
    print("Class of first item:", items[0].get('class'))
