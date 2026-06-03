import os
import re

app_dir = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam-web\app"
utils_dir = os.path.join(app_dir, "utils")
if not os.path.exists(utils_dir):
    os.makedirs(utils_dir)

# 1. Create api.js
with open(os.path.join(utils_dir, "api.js"), "w", encoding="utf-8") as f:
    f.write('''export const fetchWithAuth = async (url, options = {}) => {
  let token = null;
  if (typeof window !== "undefined") {
    token = localStorage.getItem("access_token");
  }
  const headers = { ...options.headers };
  if (token) {
    headers["Authorization"] = Bearer ;
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }
  return response;
};
''')

# 2. Modify all page.js to use fetchWithAuth
for root, dirs, files in os.walk(app_dir):
    for file in files:
        if file.endswith(".js") and file != "api.js" and file != "layout.js":
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            if "fetch(" in content or "fetch " in content:
                # Calculate relative path to utils/api
                rel_path = os.path.relpath(utils_dir, root).replace("\\", "/")
                import_stmt = f'import {{ fetchWithAuth }} from "{rel_path}/api";\n'
                
                # Replace fetch with fetchWithAuth
                # This regex looks for fetch( and replaces it, handling simple cases
                new_content = re.sub(r'\bfetch\(', 'fetchWithAuth(', content)
                
                if new_content != content:
                    if not content.startswith('import { fetchWithAuth }'):
                        new_content = import_stmt + new_content
                        
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Updated {filepath}")
