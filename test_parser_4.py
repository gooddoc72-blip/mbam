from bs4 import BeautifulSoup

with open('naver_shopping_dump_ok.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

elements = soup.find_all(string=lambda text: text and '구매' in text)
classes_found = set()
for el in elements:
    parent = el.find_parent('div', class_=True)
    if parent:
        while parent:
            cls = str(parent.get('class'))
            if 'product' in cls or 'item' in cls:
                classes_found.add(cls)
            if parent.parent and parent.parent.name == 'div':
                parent = parent.parent
            else:
                break

for c in classes_found:
    print('Found class:', c)
    
print("--- Let's look at div classes with 'item' or 'product' ---")
items = soup.find_all('div', class_=lambda c: c and ('item' in c or 'product' in c))
for i in items[:5]:
    print('Class:', i.get('class'))
