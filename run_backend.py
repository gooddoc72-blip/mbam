import asyncio
import sys
import uvicorn

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    from sqlalchemy import text
    from mbam_nextgen.backend.database import engine
    with engine.connect() as conn:
        try: conn.execute(text('ALTER TABLE shopping_tracked_items ADD COLUMN latest_places TEXT;'))
        except Exception: pass
        try: conn.execute(text('ALTER TABLE shopping_tracked_items ADD COLUMN latest_report TEXT;'))
        except Exception: pass
        conn.commit()

    uvicorn.run("mbam_nextgen.backend.main:app", host="127.0.0.1", port=8000, reload=True)
