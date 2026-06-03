import asyncio
import os
import sys
from dotenv import load_dotenv
from google import genai

async def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    # Load environment variables
    load_dotenv("mbam_nextgen/.env")

    api_key = os.getenv("GEMINI_API_KEY")
    print("API Key exists:", bool(api_key))
    
    client = genai.Client(api_key=api_key)
    
    prompt = "Hello! Tell me a short 1-line joke."
    
    print("--- 1. Testing Sync Call ---")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        print("Sync Success:", response.text.strip())
    except Exception as e:
        print("Sync Error:", e)

    print("\n--- 2. Testing Sync Call inside asyncio.to_thread ---")
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        print("Sync in thread Success:", response.text.strip())
    except Exception as e:
        print("Sync in thread Error:", e)

    print("\n--- 3. Testing Async Call (client.aio) ---")
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        print("Async Success:", response.text.strip())
    except Exception as e:
        print("Async Error:", e)

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
