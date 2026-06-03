import asyncio
import sys
import os

sys.path.append(r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램")
from mbam_nextgen.services.gov_data import GovDataCollector

async def main():
    collector = GovDataCollector()
    print("Fetching data for 소상공인24 (sbiz24)...")
    data = await collector.fetch_data("소상공인24 (sbiz24)")
    if data:
        collector.save_cache("소상공인24 (sbiz24)", data)
        print(f"Success! {len(data)} items collected.")
    else:
        print("Failed to collect data.")

asyncio.run(main())
