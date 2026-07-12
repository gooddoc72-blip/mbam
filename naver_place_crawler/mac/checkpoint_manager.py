import json
import os

CHECKPOINT_FILE = "checkpoint.json"

class CheckpointManager:
    @staticmethod
    def save_checkpoint(target, keywords, current_index, position=0, results=None):
        state = {
            "target": target,
            "keywords": keywords,
            "current_index": current_index,
            "position": position,
            "results": results if results is not None else []
        }
        try:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
            print(f"[체크포인트] 저장 완료: 대상={target}, 검색어={keywords[current_index]}, 위치={position}, 누적데이터={len(state['results'])}건")
        except Exception as e:
            print(f"[체크포인트] 저장 실패: {e}")

    @staticmethod
    def load_checkpoint():
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[체크포인트] 로드 실패: {e}")
        return None

    @staticmethod
    def clear_checkpoint():
        if os.path.exists(CHECKPOINT_FILE):
            try:
                os.remove(CHECKPOINT_FILE)
                print("[체크포인트] 삭제 완료.")
            except Exception as e:
                print(f"[체크포인트] 삭제 실패: {e}")
