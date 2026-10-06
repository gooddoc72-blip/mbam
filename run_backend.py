import asyncio
import os
import sys
import uvicorn

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def run_migrations():
    """기존 SQLite DB 호환용 컬럼 추가.
    문장별 독립 트랜잭션 — Postgres 는 한 문장 실패 시 트랜잭션 전체가 중단되므로
    각 ALTER 를 engine.begin() 으로 분리해 하나가 실패해도 나머지는 진행되게 한다.
    (신규 DB 는 create_all 이 컬럼을 모두 만들므로 이 ALTER 들은 대부분 무시됨)
    """
    from sqlalchemy import text
    from mbam_nextgen.backend.database import engine
    statements = [
        'ALTER TABLE shopping_tracked_items ADD COLUMN latest_places TEXT;',
        'ALTER TABLE shopping_tracked_items ADD COLUMN latest_report TEXT;',
        'ALTER TABLE naver_accounts ADD COLUMN blog_addr TEXT;',
        'ALTER TABLE cafe_schedules ADD COLUMN target_post_url TEXT;',
        'ALTER TABLE cafe_schedules ADD COLUMN do_view INTEGER DEFAULT 1;',
        'ALTER TABLE cafe_schedules ADD COLUMN do_like INTEGER DEFAULT 1;',
        'ALTER TABLE cafe_schedules ADD COLUMN visit_interval_min INTEGER DEFAULT 30;',
        'ALTER TABLE blog_schedules ADD COLUMN generate_card_news INTEGER DEFAULT 1;',
        'ALTER TABLE advertisers ADD COLUMN custom_limits TEXT;',
        'ALTER TABLE agent_jobs ADD COLUMN priority INTEGER DEFAULT 5;',
    ]
    for stmt in statements:
        try:
            with engine.begin() as conn:   # 문장마다 독립 트랜잭션 (실패 시 자동 롤백)
                conn.execute(text(stmt))
        except Exception:
            pass


def ensure_native_runtime():
    """동봉 Python 에 C++ 런타임(msvcp140.dll)이 빠져 있으면 채워 넣는다.

    보통은 런처가 먼저 처리하지만, 백엔드만 따로 띄우는 경우를 위한 안전망이다.
    이게 없으면 main.py 의 import 사슬이 greenlet 에서 끊겨 서버가 아예 뜨지 않는다.
    설치본이 아닌 환경(클라우드/개발)에서는 licensing 이 없거나 할 일이 없어 조용히 지나간다.
    """
    try:
        from pathlib import Path

        from licensing.native_fix import ensure_msvc_runtime
        msg = ensure_msvc_runtime(Path(__file__).resolve().parent)
        if msg:
            print(msg)
    except Exception:
        pass


if __name__ == "__main__":
    ensure_native_runtime()
    run_migrations()
    port = int(os.environ.get("PORT", "8000"))   # Railway 등 클라우드는 PORT 주입
    uvicorn.run("mbam_nextgen.backend.main:app", host="0.0.0.0", port=port)
