from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        page.goto("https://search.shopping.naver.com/search/all?query=이롬생식", wait_until="networkidle", timeout=15000)
        page.screenshot(path="naver_shopping_block.png")
        print("Screenshot saved to naver_shopping_block.png")
        print("Title:", page.title())
        browser.close()

if __name__ == "__main__":
    main()
