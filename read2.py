import json
data = json.load(open('test_output.json', 'r', encoding='utf-8'))
for b in data.get('blocks', []):
    for l in b['links']:
        if '충주시닷컴' in l['title'] or '맘스홀릭' in l['title'] or '더좋은한우' in l['title']:
            print(f"FOUND: {l['title']} -> {l['url']}")
