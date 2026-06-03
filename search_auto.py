lines = open('mbam-web/components/SeoResults.jsx', encoding='utf-8').readlines()
for i, l in enumerate(lines):
    if '자동 글쓰기' in l:
        print(f'{i+1}: {l.strip().encode("ascii", "ignore").decode("ascii")}')
