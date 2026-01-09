import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to a product page
        await page.goto("https://onlineshop.docomo.ne.jp/products/iphone/index.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        links = await page.locator("a[href*='/products/mobile/details/']").all()
        if len(links) > 0:
            link = links[0]
            href = await link.get_attribute("href")
            if not href.startswith("http"):
                 href = "https://onlineshop.docomo.ne.jp" + href
            
            print(f"Visiting {href}")
            await page.goto(href, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            
            content = await page.content()
            with open("docomo_detail.html", "w") as f:
                f.write(content)
            print("Dumped to docomo_detail.html")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
