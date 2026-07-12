import json
import os

log_path = r'C:\Users\blocklabs02\.gemini\antigravity\brain\c313dcf0-e203-4d99-b604-8f5fc1c1adbb\.system_generated\logs\transcript_full.jsonl'
output_path = r'conversation_log.md'

with open(log_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(output_path, 'w', encoding='utf-8') as out:
    out.write('# 개발 및 대화 기록\n\n')
    for line in lines:
        try:
            data = json.loads(line)
            if data.get('type') == 'USER_INPUT':
                content = data.get('content', '')
                out.write(f'## 🧑 사용자\n\n{content}\n\n---\n\n')
            elif data.get('type') == 'PLANNER_RESPONSE':
                content = data.get('content', '')
                if content:
                    out.write(f'## 🤖 AI 어시스턴트\n\n{content}\n\n---\n\n')
        except:
            pass

print('Saved conversation log.')
