
import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import re

DATA_FILE = "docs/data.json"

async def scrape_rakuten(page):
    print("Scraping Rakuten Mobile...")
    items = []
    
    # --- 1. Scrape Campaign Points (Phase 5) ---
    campaign_map = {} 
    try:
        camp_url = "https://network.mobile.rakuten.co.jp/product/iphone/"
        await page.goto(camp_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        links = await page.locator("a[href*='campaign']").all()
        print(f"Rakuten Campaign: Found {len(links)} links")
        
        visited_urls = set()
        for link in links:
            href = await link.get_attribute("href")
            if href and "point" in href and "iphone" in href:
                if not href.startswith("http"):
                    href = "https://network.mobile.rakuten.co.jp" + href
                
                if href in visited_urls: continue
                visited_urls.add(href)
                
                try:
                    target_model = None
                    if "iphone-16e" in href: target_model = "iPhone 16e"
                    elif "iphone-16" in href: target_model = "iPhone 16"
                    else: continue
                    
                    if campaign_map.get(target_model, 0) > 40000: continue
                    
                    await page.goto(href, wait_until="domcontentloaded")
                    content = await page.content()
                    matches = re.findall(r'([\d,]{4,})\s*ポイント', content)
                    if matches:
                        nums = [int(m.replace(',', '')) for m in matches]
                        max_pts = max(nums)
                        if max_pts > campaign_map.get(target_model, 0):
                            campaign_map[target_model] = max_pts
                            print(f"  Campaign: {target_model} -> {max_pts} pts")
                except Exception as e:
                    print(f"  Camp Error {href}: {e}")
    except Exception as e:
        print(f"Error scraping campaigns: {e}")

    # --- 2. Scrape Stock (Phase 7) ---
    stock_map = {}
    try:
        url_stock = "https://network.mobile.rakuten.co.jp/product/iphone/stock/"
        await page.goto(url_stock, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        product_headers = await page.locator(".product-iphone-stock-Layout_Product-name").all()
        print(f"Rakuten Stock: Found {len(product_headers)} products")
        
        for header in product_headers:
            model_name = await header.text_content()
            model_name = model_name.strip()
            
            area = header.locator("xpath=following-sibling::div[contains(@class, 'product-iphone-stock-Layout_Product-area')]").first
            if await area.count() == 0: continue
                
            if model_name not in stock_map: stock_map[model_name] = {}
            
            color_details = await area.locator(".color-details").all()
            for cd in color_details:
                color_header = cd.locator(".c-Heading_Lv4, h4")
                if await color_header.count() == 0: continue
                
                color_text = await color_header.first.text_content()
                color_name = color_text.strip()
                
                table = cd.locator("table")
                if await table.count() == 0: continue
                
                rows = await table.locator("tbody tr").all()
                for row in rows:
                    cols = await row.locator("td").all()
                    if len(cols) < 2: continue
                    
                    cap_text = await cols[0].text_content()
                    status_text = await cols[1].text_content()
                    
                    storage_match = re.search(r'(\d+)(GB|TB)', cap_text)
                    if not storage_match: continue
                    
                    storage = storage_match.group(0)
                    is_in_stock = "在庫あり" in status_text or "In stock" in status_text
                    
                    if storage not in stock_map[model_name]: 
                        stock_map[model_name][storage] = []
                    
                    stock_map[model_name][storage].append({
                        "color": color_name,
                        "stock_text": status_text.strip()[:20],
                        "stock_available": is_in_stock
                    })
            print(f"  Parsed stock for {model_name}: {len(stock_map[model_name])} capacities")
    except Exception as e:
        print(f"Error scraping Rakuten Stock: {e}")

    # --- 3. Scrape Fees (New Phase 11 Logic) ---
    try:
        url = "https://network.mobile.rakuten.co.jp/product/iphone/fee/"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        sections = await page.locator(".product-iphone-Fee_Media").all()
        if len(sections) == 0:
            sections = await page.locator("section").all()

        print(f"Rakuten Fee: Found {len(sections)} sections")
        
        # Define helper here
        def extract_price(text):
            m = re.search(r'([\d,]+)', text)
            if m: return int(m.group(1).replace(',', ''))
            return 0

        for i, section in enumerate(sections):
            name_el = section.locator("h3, .product-name, h2")
            if await name_el.count() == 0:
                print(f"  Section {i}: No header")
                continue
            
            raw_model = await name_el.first.text_content()
            model_name = raw_model.strip()
            
            if "iPhone" not in model_name:
                # print(f"  Skip non-iPhone: {model_name}")
                continue
            
            print(f"  Processing: {model_name}")
            
            table = section.locator("table")
            if await table.count() == 0:
                print("    No table")
                continue
            
            headers = await table.locator("thead th").all()
            storages = []
            for th in headers:
                txt = await th.text_content()
                txt = txt.strip()
                if "GB" in txt or "TB" in txt:
                    storages.append(txt)
            
            if not storages:
                print(f"    No storages found. Headers: {len(headers)}")
                continue

            rows = await table.locator("tbody tr").all()
            price_map = {s: {"gross": 0, "program": 0, "rent": 0} for s in storages}
            
            for row in rows:
                th = row.locator("th")
                if await th.count() == 0: continue
                header_text = await th.first.text_content()
                header_text = header_text.strip()
                
                tds = await row.locator("td").all()
                if len(tds) < len(storages): continue
                
                # Logic A: Gross
                if any(k in header_text for k in ["楽天モバイル", "一括価格", "現金販売価格"]):
                    for idx, td in enumerate(tds):
                        if idx >= len(storages): break
                        txt = await td.text_content()
                        gross = extract_price(txt)
                        if gross > 0:
                            price_map[storages[idx]]["gross"] = gross
                        if "48回" in txt:
                             m_inst = re.search(r'48回.*?([\d,]+)', txt)
                             if m_inst:
                                 installment = int(m_inst.group(1).replace(',', ''))
                                 price_map[storages[idx]]["program_calc"] = installment * 24

                # Logic B: Program Row
                elif any(k in header_text for k in ["買い替え超トクプログラム", "24回分"]):
                    for idx, td in enumerate(tds):
                        if idx >= len(storages): break
                        val = extract_price(await td.text_content())
                        if val > 0: price_map[storages[idx]]["program"] = val

                # Logic C: Rent Row (Priority)
                elif any(k in header_text for k in ["実質", "キャンペーン"]):
                    for idx, td in enumerate(tds):
                        if idx >= len(storages): break
                        val = extract_price(await td.text_content())
                        if val > 0: price_map[storages[idx]]["rent"] = val
            
            added_count = 0
            for s in storages:
                pm = price_map[s]
                p_gross = pm["gross"]
                if p_gross == 0: continue

                p_program = 0
                if pm["program"] > 0: p_program = pm["program"]
                elif "program_calc" in pm and pm["program_calc"] > 0: p_program = pm["program_calc"]
                else: p_program = int(p_gross / 2)
                
                p_effective_rent = pm["rent"] if pm["rent"] > 0 else p_program
                p_effective_buyout = p_gross
                
                points_awarded = 0
                if model_name in campaign_map:
                    points_awarded = campaign_map[model_name]
                elif "16e" in model_name and "iPhone 16e" in campaign_map:
                        points_awarded = campaign_map["iPhone 16e"]

                if "16e" in model_name and points_awarded < 50000:
                     points_awarded = 52352

                if pm["rent"] == 0:
                     p_effective_rent = p_effective_rent - points_awarded
                
                if p_effective_rent < 0: p_effective_rent = 0
                
                program_exemption = p_gross - p_program
                if program_exemption < 0: program_exemption = 0
                
                item_variants = []
                if model_name in stock_map and s in stock_map[model_name]:
                        item_variants = stock_map[model_name][s]

                items.append({
                    "carrier": "Rakuten",
                    "model": model_name,
                    "storage": s,
                    "price_gross": p_gross,
                    "price_effective_rent": p_effective_rent,
                    "price_effective_buyout": p_effective_buyout - points_awarded,
                    "url": url,
                    "discount_official": 0,
                    "points_awarded": points_awarded,
                    "program_exemption": program_exemption,
                    "variants": item_variants
                })
                added_count += 1
            
            if added_count == 0:
                print(f"    Warning: No items added for {model_name}. Map: {price_map}")

    except Exception as e:
        print(f"Error scraping Rakuten: {e}")
        import traceback
        traceback.print_exc()

    print(f"Rakuten: Found {len(items)} items")
    return items


async def scrape_ahamo(page):
    print("Scraping ahamo...")
    items = []
    try:
        url = "https://ahamo.com/products/iphone/"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        links = await page.locator("a.a-product-thumbnail-link").all()
        print(f"ahamo: Found {len(links)} links")
        
        for i, link in enumerate(links):
            # Name
            name_el = link.locator(".a-product-thumbnail__name")
            if await name_el.count() == 0:
                name_el = link.locator(".a-product-thumbnail-link__name")
            
            if await name_el.count() == 0:
                 continue
                 
            model_name = await name_el.first.text_content()
            model_name = model_name.strip()
            
            # --- Price Extraction V2 (Gross vs Effective) ---
            
            # 1. Gross Price (定価)
            # Located in .a-product-thumbnail__price (e.g. 133,265)
            price_gross = 0
            gross_el = link.locator(".a-product-thumbnail__price .a-price-amount").first
            if await gross_el.count() > 0:
                raw = await gross_el.text_content()
                m = re.search(r'([\d,]+)', raw)
                if m: price_gross = int(m.group(1).replace(',', ''))

            # 2. Effective Rent (実質負担)
            # Located in Kaedoki section "Customer Burden"
            price_effective_rent = 0
            rent_el = link.locator(".a-product-thumbnail-link__kaedoki-campaign-content-price-item-price .a-price-amount").first
            if await rent_el.count() > 0:
                raw = await rent_el.text_content()
                m = re.search(r'([\d,]+)', raw)
                if m: price_effective_rent = int(m.group(1).replace(',', ''))
            
            # 3. Official Discount (割引)
            discount_official = 0
            disc_el = link.locator(".a-product-thumbnail-link__kaedoki-campaign-content-price-item-discount .a-price-amount").first
            if await disc_el.count() > 0:
                raw = await disc_el.text_content()
                m = re.search(r'([\d,]+)', raw)
                if m: discount_official = int(m.group(1).replace(',', ''))

            # Fallback for old/simple cards
            if price_gross == 0:
                 fallback = link.locator(".a-product-thumbnail-link__price-number")
                 if await fallback.count() > 0:
                     raw = await fallback.first.text_content()
                     m = re.search(r'([\d,]+)', raw)
                     if m: price_gross = int(m.group(1).replace(',', ''))
            
            # 4. Calculation
            # ahamo d-point campaign?
            # User request: "points_awarded"
            # We can try to extract "d-point" from "Benefit" section if we want advanced logic.
            # For now, initialize to 0 or check if previously extracted text has "point".
            points_awarded = 0
            
            program_exemption = 0
            price_effective_buyout = price_gross - discount_official - points_awarded
            
            if price_effective_rent > 0 and price_gross > 0:
                # Exemption = Gross - Discount - Rent - Points?
                # Usually Rent is calculated BEFORE points in ahamo display, OR points are separate.
                # Let's assume Rent displayed is "after program", but points are separate cashback.
                # So Effective Rent (User Def) = Displayed Rent - Points.
                program_exemption = price_gross - discount_official - price_effective_rent
                if program_exemption < 0: program_exemption = 0
                
                # Apply points to effective rent
                price_effective_rent = price_effective_rent - points_awarded

            if price_effective_rent == 0 and price_effective_buyout > 0:
                price_effective_rent = price_effective_buyout

            # Storage (Inferred)
            storage = "Wait for detail" 
            if "15" in model_name or "16" in model_name or "17" in model_name:
                storage = "128GB"
            elif "SE" in model_name:
                storage = "64GB"
            else:
                storage = "Unknown"

            if price_gross > 0:
                 items.append({
                    "carrier": "ahamo",
                    "model": model_name,
                    "storage": storage,
                    "price_gross": price_gross,               
                    "discount_official": discount_official,   
                    "program_exemption": program_exemption, 
                    "points_awarded": points_awarded,
                    "price_effective_rent": price_effective_rent,      
                    "price_effective_buyout": price_effective_buyout,  
                    "variants": [],
                    "url": url
                })

    except Exception as e:
        print(f"Error scraping ahamo: {e}")
        import traceback
        traceback.print_exc()

    print(f"ahamo: Found {len(items)} items")
    return items

async def scrape_uq(page):
    print("Scraping UQ mobile...")
    items = []
    try:
        url = "https://www.uqwimax.jp/mobile/iphone/"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        product_links = await page.locator("a[href*='/mobile/iphone/']").all()
        hrefs = set()
        for link in product_links:
            href = await link.get_attribute("href")
            if href and "iphone" in href and href.count('/') > 3:
                if not href.startswith("http"):
                    href = "https://www.uqwimax.jp" + href
                hrefs.add(href)
        
        model_urls = [h for h in hrefs if re.search(r'/iphone/\d+|se', h)]
        print(f"UQ: Found model URLs: {len(model_urls)}")

        for model_url in model_urls:
            try:
                await page.goto(model_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                
                model_name = ""
                potential_headers = ["h1", ".product-name", "title"]
                for ph in potential_headers:
                    els = await page.locator(ph).all()
                    for el in els:
                        txt = await el.text_content()
                        if "iPhone" in txt:
                            model_name = txt.strip()
                            break
                    if model_name: break
                
                if not model_name: model_name = "Unknown iPhone"
                
                content = await page.content()
                
                matches = re.finditer(r'(64|128|256|512|1T)GB.*?機種代金\s*[:：]?\s*([\d,]+)円', content, re.DOTALL)
                
                discount_official = 0
                disc_match = re.search(r'最大割引額.*?(-?[\d,]+)円', content)
                if disc_match:
                    d_str = disc_match.group(1).replace(',', '').replace('-', '')
                    discount_official = int(d_str) 
                else: 
                     discount_official = 22000
                
                # UQ Points? (au PAY)
                points_awarded = 0
                
                found = False
                for m in matches:
                    storage = m.group(1) + "GB"
                    if "T" in m.group(1): storage = "1TB"
                    
                    price_gross = int(m.group(2).replace(',', ''))
                    
                    program_exemption = 0
                    
                    price_effective_buyout = price_gross - discount_official - points_awarded
                    price_effective_rent = price_effective_buyout - program_exemption
                    if price_effective_rent < 0: price_effective_rent = 0

                    if not any(i['model'] == model_name and i['storage'] == storage for i in items):
                         items.append({
                            "carrier": "UQ mobile",
                            "model": model_name,
                            "storage": storage,
                            "price_gross": price_gross,
                            "discount_official": discount_official,
                            "program_exemption": program_exemption,
                            "points_awarded": points_awarded,
                            "price_effective_rent": price_effective_rent,
                            "price_effective_buyout": price_effective_buyout,
                            "variants": [],
                            "url": model_url
                        })
                         found = True
                
                if not found:
                    matches_v2 = re.finditer(r'(64|128|256|512|1T)GB.*?([\d,]{4,})円', content, re.DOTALL)
                    for m in matches_v2:
                        storage = m.group(1) + "GB"
                        if "T" in m.group(1): storage = "1TB"
                        price_gross = int(m.group(2).replace(',', ''))
                        if price_gross < 20000: continue

                        price_effective_buyout = price_gross - discount_official - points_awarded
                        price_effective_rent = price_effective_buyout
                        
                        if not any(i['model'] == model_name and i['storage'] == storage for i in items):
                             items.append({
                                "carrier": "UQ mobile",
                                "model": model_name,
                                "storage": storage,
                                "price_gross": price_gross,
                                "discount_official": discount_official,
                                "program_exemption": 0,
                                "points_awarded": points_awarded,
                                "price_effective_rent": price_effective_rent,
                                "price_effective_buyout": price_effective_buyout,
                                "variants": [],
                                "url": model_url
                            })

            except Exception as e:
                print(f"UQ Error on {model_url}: {e}")

    except Exception as e:
        print(f"Error scraping UQ: {e}")

    print(f"UQ: Found {len(items)} items")
    return items

async def main():
    async with async_playwright() as p:
        # Launch browser (headless=False for debug if needed, but usually True)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = await context.new_page()

        rakuten_data = await scrape_rakuten(page)
        ahamo_data = await scrape_ahamo(page)
        uq_data = await scrape_uq(page)

        all_data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "items": rakuten_data + ahamo_data + uq_data
        }

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
            
        print(f"Data saved to {DATA_FILE}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
