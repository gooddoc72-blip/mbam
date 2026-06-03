import sys

with open('mbam_nextgen/services/seo_analyzer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip() == 'try:' and 'await page.goto(post_url' in lines[i+1]:
        # Found the inner try. Delete it.
        lines[i] = ''
        # Unindent until we hit the except
        for j in range(i+1, len(lines)):
            if lines[j].strip().startswith('except Exception as e:') and lines[j].startswith('                        except'):
                break
            if lines[j].startswith('    '):
                lines[j] = lines[j][4:]
        break

with open('mbam_nextgen/services/seo_analyzer.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
