import requests
import re
import json

url = 'https://m.place.naver.com/restaurant/1468999371/review/visitor'
headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)'}
html = requests.get(url, headers=headers).text

match = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*?});', html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    reviews = []
    image_urls = []
    
    for key, value in data.items():
        if key.startswith('VisitorReview:') and 'body' in value:
            if value.get('body'):
                reviews.append(value.get('body'))
            
            if value.get('media') and isinstance(value['media'], list):
                for m in value['media']:
                    # m is usually a reference like {"__ref": "VisitorReviewMedia:..."}
                    if isinstance(m, dict) and '__ref' in m:
                        ref_key = m['__ref']
                        if ref_key in data:
                            media_item = data[ref_key]
                            if 'thumbnail' in media_item:
                                image_urls.append(media_item['thumbnail'])
                            elif 'url' in media_item:
                                image_urls.append(media_item['url'])
                    
    print(f"Found {len(reviews)} reviews!")
    print(f"Found {len(image_urls)} images!")
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("Images:", image_urls[:3])
    
    sample_review = None
    for key, value in data.items():
        if key.startswith('VisitorReview:') and 'body' in value:
            sample_review = value
            break
            
    if sample_review:
        print("Sample Review Structure:")
        print(json.dumps(sample_review, ensure_ascii=False, indent=2)[:1000])
else:
    print("No Apollo State found.")
