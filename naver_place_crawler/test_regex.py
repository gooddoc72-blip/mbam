import re
with open('debug.html', 'r', encoding='utf-8') as f:
    html_source = f.read()
print('Name:', re.search(r'"name"\s*:\s*"([^"]+)"', html_source))
print('Road:', re.search(r'"roadAddress"\s*:\s*"([^"]+)"', html_source))
print('Phone:', re.search(r'"virtualPhone"\s*:\s*"([^"]+)"', html_source))
print('Phone:', re.search(r'"phone"\s*:\s*"([^"]+)"', html_source))
