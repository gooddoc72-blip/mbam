import requests, re

res = requests.get('https://m.cafe.naver.com/cjyeonsu', headers={'User-Agent': 'Mozilla/5.0'})
match = re.search(r'cafeId[\"\':\s]+(\d+)', res.text)
if match:
    print('FOUND:', match.group(1))
else:
    print('NOT FOUND')
