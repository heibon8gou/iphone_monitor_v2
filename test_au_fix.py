import asyncio
from playwright.async_api import async_playwright
import re

async def test_au_pricing():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        url = "https://www.au.com/iphone/product/iphone-16e/"
        print(f"Checking {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # 1. Gross Price
        content = await page.content()
        price_gross = 0
        gross_match = re.search(r'現金販売価格／支払総額：([\d,]+)円', content)
        if gross_match:
            price_gross = int(gross_match.group(1).replace(',', ''))
        
        # 2. Effective Rent
        price_effective_rent = 0
        program_sections = await page.locator("div.program-inner").all()
        for section in program_sections:
            text = await section.text_content()
            if "スマホトクするプログラム" in text and "実質負担額" in text:
                price_el = section.locator(".text-amount-price strong").first
                if await price_el.count() > 0:
                    p_text = await price_el.text_content()
                    price_effective_rent = int(p_text.replace(',', ''))
                    break
        
        # 3. Monthly Payment (The Logic We Fixed)
        monthly_payment = price_effective_rent // 23 if price_effective_rent > 0 else 0
        
        print(f"Gross: {price_gross}")
        print(f"Effective Rent: {price_effective_rent}")
        print(f"Monthly Payment (Calculated / 23): {monthly_payment}")
        
        if monthly_payment == 1675: # Expected for 38547 / 23
            print("SUCCESS: Monthly payment calculation is correct (1675 yen).")
        else:
            print(f"FAILURE: Monthly payment is {monthly_payment}, expected ~1675.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_au_pricing())
