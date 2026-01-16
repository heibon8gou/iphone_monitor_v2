
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
                    if "iphone-17" in href: target_model = "iPhone 17"
                    elif "iphone-16e" in href: target_model = "iPhone 16e"
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
                    "monthly_payment": p_effective_rent // 24 if p_effective_rent > 0 else p_gross // 48,
                    "monthly_payment_phases": [],
                    "variants": item_variants
                })
                added_count += 1
            
            if added_count == 0:
                print(f"    Warning: No items added for {model_name}. Map: {price_map}")

    except Exception as e:
        print(f"Error scraping Rakuten: {e}")
        import traceback
        traceback.print_exc()

    # --- 4. Scrape Monthly Prices from Individual Product Pages ---
    print("Rakuten: Fetching monthly prices from individual product pages...")
    product_urls = {
        "iPhone 16e": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-16e/",
        "iPhone 16": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-16/",
        "iPhone 16 Plus": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-16-plus/",
        "iPhone 16 Pro": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-16-pro/",
        "iPhone 16 Pro Max": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-16-pro-max/",
        "iPhone 17": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-17/",
        "iPhone 17 Pro": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-17-pro/",
        "iPhone 17 Pro Max": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-17-pro-max/",
        "iPhone Air": "https://network.mobile.rakuten.co.jp/product/iphone/iphone-air/",
    }
    
    monthly_price_map = {}  # model -> monthly_price
    for model_name, product_url in product_urls.items():
        try:
            await page.goto(product_url, wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            page_text = await page.inner_text("body")
            
            # Pattern: X円/月 or X,XXX円/月 (monthly price display, including commas)
            monthly_matches = re.findall(r'([\d,]+)円/月', page_text)
            if monthly_matches:
                # Parse prices, removing commas
                prices = [int(p.replace(',', '')) for p in monthly_matches]
                # Filter: Device monthly payments are typically >= 1 yen for promos, but plan prices like 1,078円 should be ignored
                # Real device promotional prices are usually shown as 1円, 78円 etc (very low), or actual device payments (3000+ yen)
                # To distinguish: if we find a price <= 100 yen, it's likely a device promo price
                # Otherwise, filter out prices that look like plan prices (1000-2000 range)
                device_prices = [p for p in prices if p <= 100 or p >= 2000]
                if device_prices:
                    min_price = min(device_prices)
                    monthly_price_map[model_name] = min_price
                    print(f"  {model_name}: {min_price}円/月 (from page)")
        except Exception as e:
            print(f"  Error fetching {model_name}: {e}")
    
    # Update items with scraped monthly prices
    for item in items:
        model = item["model"]
        if model in monthly_price_map:
            old_price = item["monthly_payment"]
            new_price = monthly_price_map[model]
            if new_price < old_price:
                item["monthly_payment"] = new_price
                # Also update price_effective_rent to match
                item["price_effective_rent"] = new_price * 24

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
                    "monthly_payment": price_effective_rent // 24 if price_effective_rent > 0 else price_gross // 48,
                    "monthly_payment_phases": [],
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
                            "monthly_payment": price_effective_rent // 24 if price_effective_rent > 0 else price_gross // 24,
                            "monthly_payment_phases": [],
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
                                "monthly_payment": price_effective_rent // 24 if price_effective_rent > 0 else price_gross // 24,
                                "monthly_payment_phases": [],
                                "variants": [],
                                "url": model_url
                            })

            except Exception as e:
                print(f"UQ Error on {model_url}: {e}")

    except Exception as e:
        print(f"Error scraping UQ: {e}")

    print(f"UQ: Found {len(items)} items")
    return items


async def scrape_au(page):
    print("Scraping au...")
    items = []
    try:
        url = "https://www.au.com/iphone/"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)


        # Find model links
        # Au uses /iphone/product/...
        links = await page.locator("a").all()
        hrefs = []
        for link in links:
            href = await link.get_attribute("href")
            # Filter for valid product pages
            # Removed incorrect "product/iphone" exclusion which filtered out /iphone/product/iphone-16/
            if href and "/iphone/product/" in href:
                if not href.startswith("http"):
                    href = "https://www.au.com" + href
                hrefs.append(href)
        
        unique_urls = list(set(hrefs))
        # Filter for recent iPhones to capture relevant data
        target_urls = [u for u in unique_urls if any(m in u for m in ["iphone-17", "iphone-air", "iphone-16", "iphone-15", "iphone-14", "iphone-se"])]
        
        print(f"au: Found {len(target_urls)} model URLs")

        for model_url in target_urls:
            try:
                print(f"  Checking {model_url}")
                await page.goto(model_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                
                # Model Name
                title = await page.title()
                model_name = "Unknown iPhone"
                if "iPhone" in title:
                    # Extract "iPhone 16" etc from title "iPhone 16（...）| au"
                    # Capture until delimiter, including 【 for "iPhone 17【予約"
                    m = re.search(r'(iPhone\s?[^|（(・【]+)', title)
                    if m: 
                        model_name = m.group(1).strip()
                        # Remove "の予約" or similar trailing garbage if regex missed it
                        model_name = re.sub(r'の予約.*', '', model_name)
                        model_name = model_name.replace("予約", "").strip()
                
                content = await page.content()
                
                # 1. Gross Price (Cash Price)
                price_gross = 0
                gross_match = re.search(r'現金販売価格／支払総額：([\d,]+)円', content)
                if gross_match:
                    price_gross = int(gross_match.group(1).replace(',', ''))
                
                # 2. Effective Rent (Program Content)
                price_effective_rent = 0
                
                # Look for "スマホトクするプログラム" block
                # We use locator to find the section then find the price inside
                program_sections = await page.locator("div.program-inner").all()
                for section in program_sections:
                    text = await section.text_content()
                    if "スマホトクするプログラム" in text and "実質負担額" in text:
                        # Find the price element inside this section
                        # Usually .text-amount-price strong
                        price_el = section.locator(".text-amount-price strong").first
                        if await price_el.count() > 0:
                            p_text = await price_el.text_content()
                            price_effective_rent = int(p_text.replace(',', ''))
                            break
                            
                # 3. Points (Optional, usually 0 for carrier base unless campaign)
                points_awarded = 0
                
                # 4. Storage
                # au usually defaults to lowest storage. 
                # Scrapping all storages requires clicking buttons.
                # For now, let's assume "Start From" price (Lowest Storage).
                storage = "最小容量"
                # If we want to capture the storage size from the active button:
                checked_label = page.locator("label.cmp-form-options__label--checked").first
                if await checked_label.count() > 0:
                     st_text = await checked_label.text_content()
                     if "GB" in st_text or "TB" in st_text:
                         storage = st_text.strip()
                
                # Calc logic
                discount_official = 0 
                # If Effective rent is significantly lower, it implies program.
                # Program Exemption = Gross - Rent (roughly)
                program_exemption = 0
                price_effective_buyout = price_gross # Usually same as gross unless points
                
                if price_effective_rent > 0 and price_gross > 0:
                    program_exemption = price_gross - price_effective_rent
                elif price_effective_rent == 0 and price_gross > 0:
                     # If no program price found, effective rent is gross
                     price_effective_rent = price_gross

                if price_gross > 0:
                     items.append({
                        "carrier": "au",
                        "model": model_name,
                        "storage": storage,
                        "price_gross": price_gross,
                        "discount_official": discount_official,
                        "program_exemption": program_exemption,
                        "points_awarded": points_awarded,
                        "price_effective_rent": price_effective_rent,
                        "price_effective_buyout": price_effective_buyout,
                        "monthly_payment": price_effective_rent // 24 if price_effective_rent > 0 else price_gross // 48,
                        "monthly_payment_phases": [],
                        "variants": [],
                        "url": model_url
                    })

            except Exception as e:
                print(f"  au Error on {model_url}: {e}")
                
    except Exception as e:
        print(f"Error scraping au: {e}")

    print(f"au: Found {len(items)} items")
    return items


async def scrape_softbank(page):
    print("Scraping SoftBank...")
    items = []
    try:
        # Softbank logic: Main page -> Model page -> Price section
        url = "https://www.softbank.jp/iphone/"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Links
        links = await page.locator("a[href*='/iphone/iphone-']").all()
        hrefs = set()
        for link in links:
            href = await link.get_attribute("href")
            # /iphone/iphone-16/ or similar
            if href and re.search(r'/iphone/iphone-[\w-]+/?$', href):
                 if not href.startswith("http"):
                    href = "https://www.softbank.jp" + href
                 hrefs.add(href)
        
        target_urls = [u for u in hrefs if "price" not in u and "spec" not in u] # Avoid sub-pages
        print(f"SoftBank: Found {len(target_urls)} model URLs")
        
        for model_url in target_urls:
            try:
                # print(f"  Checking {model_url}")
                await page.goto(model_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                
                model_name = "Unknown iPhone"
                title = await page.title()
                if "iPhone" in title:
                    # Split by common delimiters including '・' used by SoftBank for multiple models
                    # "iPhone 16 Pro・iPhone 16 Pro Max..." -> "iPhone 16 Pro"
                    raw_name = title.split("|")[0].strip()
                    # regex to grab the first "iPhone X" part until a dot or space-delimiter
                    # or just split by '・' or '【'
                    model_name = re.split(r'[・【]', raw_name)[0].strip()
                    model_name = re.split(r'[・【]', raw_name)[0].strip()
                    # Clean generic suffixes
                    model_name = model_name.replace("【予約・購入】", "").strip()
                    model_name = model_name.replace("予約", "").strip()
                
                content = await page.content()
                
                # 1. Gross Price
                price_gross = 0
                g_regex = re.search(r'総額.*?([\d,]+)円', content)
                if g_regex:
                    price_gross = int(g_regex.group(1).replace(',', ''))
                
                # 2. Effective Rent (2-year total)
                price_effective_rent = 0
                
                tokusapo_section = page.locator(".mobile-page-u96-app-model-price-applied-model-price__card--tokusapo-plus")
                if await tokusapo_section.count() > 0:
                     section_text = await tokusapo_section.text_content()
                     m = re.search(r'支払総額.*?([\d,]+)円', section_text)
                     if m:
                         price_effective_rent = int(m.group(1).replace(',', ''))
                
                if price_effective_rent == 0:
                     r_match = re.search(r'実質負担金.*?([\d,]+)円', content)
                     if r_match: price_effective_rent = int(r_match.group(1).replace(',', ''))

                # 3. Monthly Payment Phases (SoftBank特有)
                # 新トクするサポートの各期間の月額を取得
                monthly_payment_phases_dict = {}  # Use dict to deduplicate by period
                monthly_payment = 0
                
                # Pattern: "1～12回" followed by amount, "13～24回", "25～48回"
                # Try to find payment rows in the pricing section
                price_rows = await page.locator(".mobile-page-u96-app-model-price-item-row").all()
                
                for row in price_rows:
                    try:
                        row_text = await row.text_content()
                        # Check for period patterns like "1～12回"
                        period_match = re.search(r'(\d+)[～~](\d+)回', row_text)
                        if period_match:
                            period = f"{period_match.group(1)}～{period_match.group(2)}回"
                            
                            # Skip if already processed this period
                            if period in monthly_payment_phases_dict:
                                continue
                            
                            # Extract amount - could be a number or "お支払い不要"
                            if "お支払い不要" in row_text:
                                amount = 0
                            else:
                                amount_match = re.search(r'([\d,]+)円', row_text)
                                if amount_match:
                                    amount = int(amount_match.group(1).replace(',', ''))
                                    # Previously filtered < 100, but 1 yen is valid for campaigns
                                    if amount < 1:
                                        print(f"Skipping invalid amount: {amount}")
                                        continue
                                else:
                                    continue
                            
                            monthly_payment_phases_dict[period] = amount
                    except:
                        continue
                
                # Convert dict to list
                monthly_payment_phases = [{"period": k, "amount": v} for k, v in monthly_payment_phases_dict.items()]
                
                # Fallback: Try regex on full content if no rows found
                if not monthly_payment_phases:
                    # Look for patterns like "1～12回...3,640円"
                    phase_patterns = [
                        (r'1[～~]12回.*?([\d,]+)円', "1～12回"),
                        (r'13[～~]24回.*?([\d,]+)円', "13～24回"),
                        (r'25[～~]48回.*?([\d,]+)円', "25～48回"),
                    ]
                    for pattern, period in phase_patterns:
                        m = re.search(pattern, content)
                        if m:
                            amount = int(m.group(1).replace(',', ''))
                            if amount >= 1:  # Accept valid promo amounts like 1 yen
                                monthly_payment_phases.append({
                                    "period": period,
                                    "amount": amount
                                })
                    
                    # Check for "お支払い不要" periods
                    if "25～48回" not in [p["period"] for p in monthly_payment_phases]:
                        if re.search(r'25[～~]48回.*?お支払い不要', content):
                            monthly_payment_phases.append({"period": "25～48回", "amount": 0})
                
                # Sort phases by period start number
                monthly_payment_phases.sort(key=lambda x: int(re.search(r'^(\d+)', x["period"]).group(1)) if re.search(r'^(\d+)', x["period"]) else 0)
                
                # Calculate monthly_payment
                # Use first phase amount if valid, otherwise calculate from 2-year total
                if monthly_payment_phases and monthly_payment_phases[0]["amount"] >= 1:
                    monthly_payment = monthly_payment_phases[0]["amount"]
                elif price_effective_rent > 0:
                    monthly_payment = price_effective_rent // 24
                
                if price_gross > 0:
                     items.append({
                        "carrier": "SoftBank",
                        "model": model_name,
                        "storage": "最小容量",
                        "price_gross": price_gross,
                        "discount_official": 0,
                        "program_exemption": price_gross - price_effective_rent if price_effective_rent else 0,
                        "points_awarded": 0,
                        "price_effective_rent": price_effective_rent if price_effective_rent else price_gross,
                        "price_effective_buyout": price_gross,
                        "monthly_payment": monthly_payment,
                        "monthly_payment_phases": monthly_payment_phases,
                        "variants": [],
                        "url": model_url
                    })
            except Exception as e:
                print(f"  SoftBank Error {model_url}: {e}")

    except Exception as e:
        print(f"Error scraping SoftBank: {e}")
    
    print(f"SoftBank: Found {len(items)} items")
    return items

async def scrape_docomo(page):
    print("Scraping docomo... (v3 fast)")
    items = []
    try:
        # Docomo Online Shop is structured
        url = "https://onlineshop.docomo.ne.jp/products/iphone/index.html"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        # Product Cards
        cards = await page.locator("a[href*='/products/mobile/details/']").all()

        print(f"Docomo: Found {len(cards)} product cards")
        
        card_urls = []
        for card in cards:
            href = await card.get_attribute("href")
            # Updated filter to match selector
            if href and "/products/mobile/details/" in href:
                 if not href.startswith("http"):
                     if href.startswith("/"):
                         href = "https://onlineshop.docomo.ne.jp" + href
                     else:
                         href = "https://onlineshop.docomo.ne.jp/products/iphone/" + href 
                 card_urls.append(href)
        
        unique_urls = list(set(card_urls))
        
        for p_url in unique_urls:
            try:
                await page.goto(p_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000) # Shorter wait, just need HTML
                
                # Wait for title to populate (retry logic)
                for _ in range(5):
                    title = await page.title()
                    if "|" in title and "iPhone" in title:
                        break
                    await page.wait_for_timeout(500)
                
                # Docomo title: "iPhone 17 Pro | ドコモオンラインショップ"
                if "|" in title:
                    model_name = title.split('|')[0].strip()
                elif "iPhone" in title:
                    model_name = title.strip()
                
                # Cleanup "の予約・購入" suffixes if present
                model_name = re.sub(r'の予約.*', '', model_name)
                model_name = re.sub(r'【.*', '', model_name)
                model_name = model_name.replace("予約", "").strip()
                model_name = re.split(r'[・【]', model_name)[0].strip()

                # Fallback to H1 if title failed or produced "Unknown"
                if "iPhone" not in model_name or len(model_name) > 50 or model_name == "Unknown iPhone":
                    try:
                         h1 = await page.locator("h1").first.text_content()
                         if h1 and "iPhone" in h1:
                             model_name = h1.strip()
                             # Clean h1 too
                             model_name = re.sub(r'の予約.*', '', model_name)
                             model_name = re.sub(r'【.*', '', model_name)
                             model_name = model_name.replace("予約", "").strip()
                             model_name = re.split(r'[・【]', model_name)[0].strip()
                    except:
                        pass
                        
                # Get full content for fast regex
                content = await page.content()

                # Price extraction
                price_gross = 0
                price_effective_rent = 0
                
                try:
                    # 1. Gross Price
                    # Search for "現金販売価格"
                    # "支払い総額/現金販売価格" ... "214,940円"
                    m_g = re.search(r'現金販売価格.*?([\d,]+)円', content)
                    if m_g:
                        price_gross = int(m_g.group(1).replace(',', ''))
                    
                    if price_gross == 0:
                         m_g2 = re.search(r'支払い総額.*?([\d,]+)円', content)
                         if m_g2: price_gross = int(m_g2.group(1).replace(',', ''))

                    # 2. Effective Rent
                    # Look for "お客さま負担額" (Customer Burden)
                    # Use findAll to get candidates, pick the largely plausible one?
                    # Or specific pattern: "お客さま負担額" then some chars then number
                    m_r = re.search(r'お客さま負担額.*?([\d,]+)円', content)
                    if m_r:
                         price_effective_rent = int(m_r.group(1).replace(',', ''))
                    
                    # Safety check: If rent is impossibly low (e.g. monthly), ignore it
                    if price_effective_rent > 0 and price_effective_rent < 10000:
                         # Try finding another price
                         # Sometimes the Monthly price appears first.
                         # Try finding "実質負担金"
                         m_r2 = re.search(r'実質負担金.*?([\d,]+)円', content)
                         if m_r2: 
                             price_effective_rent = int(m_r2.group(1).replace(',', ''))
                         
                         # If still low, just set to 0 to fallback to gross
                         if price_effective_rent < 10000:
                             price_effective_rent = 0

                except Exception as e:
                    print(f"  Price extract error for {model_name}: {e}")

                if price_gross > 0:
                     effective = price_effective_rent if price_effective_rent else price_gross
                     items.append({
                        "carrier": "docomo",
                        "model": model_name,
                        "storage": "最小容量",
                        "price_gross": price_gross,
                        "discount_official": 0,
                        "program_exemption": price_gross - price_effective_rent if price_effective_rent else 0,
                        "points_awarded": 0,
                        "price_effective_rent": effective,
                        "price_effective_buyout": price_gross,
                        "monthly_payment": effective // 24 if effective > 0 else price_gross // 48,
                        "monthly_payment_phases": [],
                        "variants": [],
                        "url": p_url
                    })
            except Exception as e:
                print(f"  Docomo Detail Error: {e}")
                
    except Exception as e:
        print(f"Error scraping docomo: {e}")
    
    print(f"Docomo: Found {len(items)} items")
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
        au_data = await scrape_au(page)
        sb_data = await scrape_softbank(page)
        docomo_data = await scrape_docomo(page)

        all_data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "items": rakuten_data + ahamo_data + uq_data + au_data + sb_data + docomo_data
        }

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
            
        print(f"Data saved to {DATA_FILE}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
