import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ranking.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("DELETE FROM place_rank_history WHERE date = '2026-06-02'")
conn.commit()
conn.close()
print("Cache cleared for 2026-06-02")
