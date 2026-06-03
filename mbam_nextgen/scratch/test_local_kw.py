import re
from collections import Counter

def extract_keywords_local(texts: list) -> list:
    # 1. Combine texts
    combined = " ".join(texts)
    
    # 2. Curated list of Korean suffixes (조사) to strip from the end of words
    suffixes = [
        '에서는', '구만요', '네용', '네요', '아요', '어요', '지요', '고요', '라고', '하자', '하며', 
        '에서', '부터', '까지', '으로', '로써', '로서', '한테', '에게', '이며', '였다', 
        '은', '는', '이', '가', '을', '를', '에', '의', '도', '로', '과', '와', '고', '며', '랑'
    ]
    # Sort suffixes by length in descending order to match longest first
    suffixes.sort(key=len, reverse=True)
    
    # 3. Curated stop words to ignore
    stop_words = {
        '것', '수', '등', '이', '그', '저', '요', '네', '아', '오', '한', '적', '제', '더', '안', '못', 
        '잘', '참', '꼭', '너무', '진짜', '매우', '엄청', '많이', '조금', '약간', '거의', '전혀', 
        '항상', '자주', '종종', '보통', '대체로', '주로', '가끔', '때때로', '있는', '없어', '있어', 
        '하는', '했다', '합니다', '있습니다', '없습니다', '때문에', '위해', '위해서', '대한', 
        '대해', '대해서', '통해', '통해서', '같이', '함께', '같은', '다른', '모든', '어떤', '무슨', 
        '이런', '저런', '그런', '이렇게', '저렇게', '그렇게', '그리고', '하지만', '그러나', 
        '그래서', '그러면', '그럼', '또한', '따라서', '때', '후', '전', '안쪽', '바깥쪽', '시간', 
        '하루', '이틀', '이번', '다음', '지난', '올해', '내년', '오늘', '내일', '어제', '저희', 
        '저희가', '제가', '내가', '우리가', '우리', '여러분', '여럿', '하나', '둘', '셋', '넷', 
        '다섯', '여섯', '일곱', '여덟', '아홉', '열', '맛집', '위치', '방문', '추천', '메뉴', '후기',
        '생각', '느낌', '이용', '준비', '시작', '확인', '사용', '진행', '가능', '경우', '정도', '때문'
    }
    
    # Clean text: keep only Korean letters, English letters, and numbers
    # Convert to lowercase
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', combined)
    words = cleaned.split()
    
    processed_words = []
    for w in words:
        w = w.lower().strip()
        if len(w) < 2:
            continue
            
        # Strip suffixes
        stripped = w
        for suffix in suffixes:
            if stripped.endswith(suffix):
                # Only strip if the remaining part is at least 2 chars to avoid over-stripping
                rem = stripped[:-len(suffix)]
                if len(rem) >= 2:
                    stripped = rem
                    break
        
        if len(stripped) >= 2 and stripped not in stop_words:
            processed_words.append(stripped)
            
    # Count frequencies
    counter = Counter(processed_words)
    top_20 = [{"keyword": kw, "count": count} for kw, count in counter.most_common(20)]
    return top_20

# Test with a snippet
test_texts = [
    "부산 동래역 맛집인 한우장터에 다녀왔습니다. 동래맛집 중에서 고기 질이 가장 좋았고 한우 육즙이 풍부했습니다.",
    "동래역 근처 맛집을 찾으신다면 한우장터를 추천합니다. 한우 고기가 아주 부드럽고 가성비도 괜찮았습니다."
]

print(extract_keywords_local(test_texts))
