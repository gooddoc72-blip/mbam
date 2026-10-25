import sys

with open('mbam_nextgen/services/seo_analyzer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_process_url = False
try_block_active = False

for i, line in enumerate(lines):
    if 'async def process_url(raw_url):' in line:
        in_process_url = True
    
    if in_process_url:
        if line.strip() == 'url = raw_url':
            try_block_active = True
            
        if try_block_active:
            if 'except Exception as e:' in line:
                try_block_active = False
                in_process_url = False
                continue
            lines[i] = '    ' + line

with open('mbam_nextgen/services/seo_analyzer.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
