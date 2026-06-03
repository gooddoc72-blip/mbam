import asyncio
import os
import sys

# 패키지 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.gov_data import GovDataCollector

async def test_collect():
    collector = GovDataCollector()
    print("--- Testing AI Research for '기업마당 (Bizinfo)' ---")
    data = await collector.fetch_data("기업마당 (Bizinfo)")
    if data:
        print(f"✅ Successfully collected {len(data)} items.")
        for item in data[:2]:
            print(f"- {item.get('title')} ({item.get('source')})")
    else:
        print("❌ Collection failed or returned no data.")

if __name__ == "__main__":
    asyncio.run(test_collect())
