import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv("mbam_nextgen/.env")

from mbam_nextgen.services.soul import SoulRewriter

async def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    print("[SOUL-TEST] Creating SoulRewriter...")
    soul = SoulRewriter()
    
    print("[SOUL-TEST] calling _call_gemini...")
    try:
        res = await soul._call_gemini("Hello, are you there?")
        print("[SOUL-TEST] Response:")
        print(res)
    except Exception as e:
        print("[SOUL-TEST] Error:", e)

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
