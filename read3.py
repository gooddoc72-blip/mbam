import json
data = json.load(open('test_output_sashimi.json', 'r', encoding='utf-8'))
for b in data.get('blocks', []):
    if '인기글' in b['block_title']:
        print(f"BLOCK: {b['block_title']}")
        for l in b['links']:
            print(f"  [{l['type']}] {l['title']} -> {l['url']}")
