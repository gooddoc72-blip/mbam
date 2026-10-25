import os

app_dir = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam-web\app"

for root, dirs, files in os.walk(app_dir):
    for file in files:
        if file.endswith(".js"):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Find the line indices
            fetch_idx = -1
            use_client_idx = -1
            
            for i, line in enumerate(lines):
                if line.strip().startswith('import { fetchWithAuth }'):
                    fetch_idx = i
                if line.strip() == '"use client";' or line.strip() == "'use client';":
                    use_client_idx = i
                    
            if fetch_idx != -1 and use_client_idx != -1 and fetch_idx < use_client_idx:
                # Need to swap so "use client" is at the top
                fetch_line = lines.pop(fetch_idx)
                # Since fetch_idx was < use_client_idx, popping it shifted use_client_idx down by 1
                new_use_client_idx = use_client_idx - 1
                lines.insert(new_use_client_idx + 1, fetch_line)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"Fixed {filepath}")
