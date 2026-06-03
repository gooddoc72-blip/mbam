import asyncio
import os
import sys

# 패키지 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mbam_nextgen.services.gov_data import GovDataCollector

async def test_gemini():
    collector = GovDataCollector()
    print("--- Testing Gemini Call Directly ---")
    prompt = "Korea government support programs for startups 2024. Return only a list of 3 items in JSON."
    try:
        response = await collector.soul._call_gemini(prompt)
        print("Response received:")
        print(response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
