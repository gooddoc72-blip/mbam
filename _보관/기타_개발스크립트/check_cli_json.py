import json
with open('cli_test.json', 'r', encoding='utf-16') as f:
    data = json.load(f)
    print(f'Total items: {len(data)}')
    for i, item in enumerate(data):
        if '집구석' in item.get('name', ''):
            print(f"Found '집구석' at index {i} (Rank {i+1})")
            print(f"MID: {item.get('mid')}")
