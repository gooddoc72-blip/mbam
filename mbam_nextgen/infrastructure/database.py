import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

class DatabaseManager:
    """
    [Infrastructure] SQLite 기반의 SaaS 운영 내역 저장소
    블로그, 카페, 소통, 트렌드, 플레이스 순위 변동 등의 히스토리를 영구 저장합니다.
    """
    
    def __init__(self, db_path="mbam_nextgen/saas_data.db"):
        self.db_path = db_path
        self._init_db()
        
    @contextmanager
    def _get_connection(self):
        # sqlite3의 'with conn'은 commit/rollback만 하고 close는 안 함 → 커넥션/파일핸들 누수.
        # 여기서 commit·rollback·close를 모두 보장한다. (호출부의 'with ... as conn'은 그대로 동작)
        conn = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        
    def _init_db(self):
        """테이블이 없으면 생성합니다."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 블로그 포스팅 내역
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS history_blog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                account_id TEXT,
                post_title TEXT,
                target_keyword TEXT,
                status TEXT,
                result_url TEXT,
                credit_used INTEGER
            )''')

            # 2. 카페 포스팅 내역
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS history_cafe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                account_id TEXT,
                cafe_name TEXT,
                post_title TEXT,
                action_type TEXT,
                status TEXT,
                result_url TEXT
            )''')
            
            # 3. 소통 & 이웃 내역
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS history_engagement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                target_url TEXT,
                action_type TEXT,
                comment_text TEXT,
                status TEXT
            )''')
            
            # 4. 글감 수집 (트렌드) 내역
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                keyword TEXT,
                trend_score INTEGER
            )''')
            
            # 5. 플레이스 순위 변동 내역
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS place_rank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                place_name TEXT,
                search_keyword TEXT,
                current_rank INTEGER,
                rank_change TEXT,
                review_count INTEGER
            )''')
            
            # 6. 정밀 분석 (Top 3 SEO) 내역
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS history_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                keyword TEXT,
                total_words INTEGER,
                total_chars INTEGER,
                total_images INTEGER,
                report_json TEXT
            )''')

            # --- 기존 DB 자동 보강 (대시보드 작업내역: 사용계정/포스팅 제목) ---
            migrations = [
                "ALTER TABLE history_blog ADD COLUMN post_title TEXT",
                "ALTER TABLE history_cafe ADD COLUMN account_id TEXT",
                "ALTER TABLE history_cafe ADD COLUMN post_title TEXT",
            ]
            for mig in migrations:
                try:
                    cursor.execute(mig)
                except Exception:
                    pass  # 이미 컬럼이 있으면 무시

            conn.commit()

    # --- Insert Methods ---

    def log_blog(self, account_id, target_keyword, status, result_url, credit_used=10, post_title=""):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO history_blog (created_at, account_id, post_title, target_keyword, status, result_url, credit_used) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), account_id, post_title, target_keyword, status, result_url, credit_used)
            )

    def log_cafe(self, account_id, cafe_id, keyword, status, result_url="", post_title=""):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO history_cafe (created_at, account_id, cafe_name, post_title, action_type, status, result_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), account_id, cafe_id, post_title, keyword, status, result_url)
            )

    def log_engagement(self, target_url, action_type, comment_text, status):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO history_engagement (created_at, target_url, action_type, comment_text, status) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), target_url, action_type, comment_text, status)
            )
            
    def log_trend(self, keyword, trend_score=0):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO scraped_trends (created_at, keyword, trend_score) VALUES (?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), keyword, trend_score)
            )
            
    def log_place_rank(self, place_name, search_keyword, current_rank, rank_change, review_count):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO place_rank_history (created_at, place_name, search_keyword, current_rank, rank_change, review_count) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), place_name, search_keyword, current_rank, rank_change, review_count)
            )

    def log_analysis(self, keyword, total_words, total_chars, total_images, report_json):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO history_analysis (created_at, keyword, total_words, total_chars, total_images, report_json) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), keyword, total_words, total_chars, total_images, report_json)
            )

    # --- Select Methods (for API) ---
    
    def get_history(self, table_name, limit=50):
        allowed_tables = ["history_blog", "history_cafe", "history_engagement", "scraped_trends", "place_rank_history", "history_analysis"]
        if table_name not in allowed_tables:
            return []
            
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
