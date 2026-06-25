import json
import os

HISTORY_FILE = "history.json"

class HistoryManager:
    def __init__(self):
        self.history = set()
        self.load_history()

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = set(data)
            except Exception as e:
                print(f"이력 로드 실패: {e}")
                self.history = set()

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.history), f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"이력 저장 실패: {e}")

    def is_collected(self, item_id):
        return item_id in self.history

    def add_collected(self, item_id):
        self.history.add(item_id)
        self.save_history()

    def clear_history(self):
        self.history = set()
        self.save_history()
