from bs4 import BeautifulSoup

with open('naver_shopping_dump.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Let's find any text containing '구매'
elements = soup.find_all(string=lambda text: text and '구매' in text)
for el in elements:
    parent = el.find_parent('div', class_=True)
    if parent:
        print(f"Text: '{el.strip()}' | Parent class: {parent.get('class')}")
        
        # Go up a few levels to see if we can find a container
        grandparent = parent.find_parent('div', class_=True)
        if grandparent:
            print(f"  Grandparent class: {grandparent.get('class')}")
