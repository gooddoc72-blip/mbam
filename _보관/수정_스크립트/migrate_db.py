from mbam_nextgen.backend.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE shopping_tracked_items ADD COLUMN latest_places TEXT;'))
        except Exception as e:
            print("latest_places already exists:", e)
            
        try:
            conn.execute(text('ALTER TABLE shopping_tracked_items ADD COLUMN latest_report TEXT;'))
        except Exception as e:
            print("latest_report already exists:", e)
            
        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
