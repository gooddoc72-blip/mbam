import sqlite3
import os
from datetime import datetime

class RankingDB:
    def __init__(self, db_path="mbam_nextgen/data/ranking.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 키워드 관리 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS target_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blog_id TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(blog_id, keyword)
                )
            ''')
            # 순위 히스토리 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ranking_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword_id INTEGER,
                    rank INTEGER,
                    check_date DATE DEFAULT (CURRENT_DATE),
                    FOREIGN KEY (keyword_id) REFERENCES target_keywords(id)
                )
            ''')
            conn.commit()

    def add_keyword(self, blog_id, keyword):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO target_keywords (blog_id, keyword) VALUES (?, ?)', (blog_id, keyword))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_keyword(self, keyword_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ranking_history WHERE keyword_id = ?', (keyword_id,))
            cursor.execute('DELETE FROM target_keywords WHERE id = ?', (keyword_id,))
            conn.commit()

    def get_keywords(self, blog_id=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if blog_id:
                cursor.execute('SELECT id, blog_id, keyword FROM target_keywords WHERE blog_id = ?', (blog_id,))
            else:
                cursor.execute('SELECT id, blog_id, keyword FROM target_keywords')
            return cursor.fetchall()

    def add_history(self, keyword_id, rank):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 날짜 기반 중복 체크를 위해 쿼리 수정
            cursor.execute('SELECT id FROM ranking_history WHERE keyword_id = ? AND check_date = CURRENT_DATE', (keyword_id,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute('UPDATE ranking_history SET rank = ? WHERE id = ?', (rank, exists[0]))
            else:
                cursor.execute('INSERT INTO ranking_history (keyword_id, rank) VALUES (?, ?)', (keyword_id, rank))
            conn.commit()

    def get_history(self, keyword_id, days=30):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT check_date, rank FROM ranking_history 
                WHERE keyword_id = ? 
                ORDER BY check_date DESC LIMIT ?
            ''', (keyword_id, days))
            return cursor.fetchall()
