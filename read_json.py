import json
data = json.load(open('test_output.json', 'r', encoding='utf-8'))
for b in data.get('blocks', []):
    print(f"BLOCK: {b['block_title']}")
    for l in b['links']:
        print(f"  [{l['type']}] {l['title']} -> {l['url']}")
