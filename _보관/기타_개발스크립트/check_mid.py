import sys, json
sys.path.append('.')
from mbam_nextgen.services.naver_crawler import search_keyword_ranking
res = search_keyword_ranking('전포동 맛집', limit=300)
found = False
for i, r in enumerate(res):
    if '집구석' in r['name']:
        print(f'FOUND 집구석 AT RANK {i+1}')
        print(f'MID: {r.get("mid")}')
        found = True
if not found:
    print('집구석 STILL NOT FOUND IN TOP 300!')
print(f'Total scraped items: {len(res)}')
