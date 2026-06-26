import asyncio
import sys
import uvicorn

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

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
        try: conn.execute(text('ALTER TABLE naver_accounts ADD COLUMN blog_addr TEXT;'))
        except Exception: pass
        # 게시글 부스트(조회수/좋아요) 스케줄 컬럼
        try: conn.execute(text('ALTER TABLE cafe_schedules ADD COLUMN target_post_url TEXT;'))
        except Exception: pass
        try: conn.execute(text('ALTER TABLE cafe_schedules ADD COLUMN do_view INTEGER DEFAULT 1;'))
        except Exception: pass
        try: conn.execute(text('ALTER TABLE cafe_schedules ADD COLUMN do_like INTEGER DEFAULT 1;'))
        except Exception: pass
        try: conn.execute(text('ALTER TABLE cafe_schedules ADD COLUMN visit_interval_min INTEGER DEFAULT 30;'))
        except Exception: pass
        # 블로그 매일발행: 카드뉴스 자동생성 토글
        try: conn.execute(text('ALTER TABLE blog_schedules ADD COLUMN generate_card_news INTEGER DEFAULT 1;'))
        except Exception: pass
        conn.commit()

    uvicorn.run("mbam_nextgen.backend.main:app", host="0.0.0.0", port=8000)
