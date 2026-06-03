import requests
import json

def get_related(keyword):
    url = f"https://ac.search.naver.com/nx/ac?q={keyword}&con=1&rev=4&q_enc=UTF-8&st=100"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if "items" in data and len(data["items"]) > 0:
                # data["items"][0] contains lists of [keyword, ...]
                related = [item[0] for item in data["items"][0][:5]]
                return related
    except Exception as e:
        print("Error:", e)
    return []

if __name__ == "__main__":
    print("Related:", get_related("동래맛집"))
