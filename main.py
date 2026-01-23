import asyncio
import os
import json
import re
import gspread
import httpx
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

# --- 設定エリア ---
SHEET_NAME = "Indevia.system"
WORKSHEET_NAME = "02_Purchase_Control"

# --- 共通：スプレッドシート更新 ---
async def update_spreadsheet(data_list):
    if not data_list:
        print("⚠️ 書き込むデータがないためスキップします。")
        return
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        key_json = json.loads(os.getenv("GSPREAD_SERVICE_ACCOUNT"))
        creds = Credentials.from_service_account_info(key_json, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)

        rows = [
            [item['jan'], item['price'], item['shop'], item['url'], '', '', '', '', '', item['name']]
            for item in data_list
        ]
        sheet.append_rows(rows)
        print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")
    except Exception as e:
        print(f"❌ スプレッドシートエラー: {e}")

# --- 1. 楽天 API ---
async def fetch_rakuten(keyword):
    app_id = os.getenv("1090738828110170361")
    if not app_id: return []
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {"applicationId": app_id, "keyword": keyword, "hits": 3, "format": "json", "sort": "+itemPrice"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, params=params)
        if res.status_code != 200: return []
        items = res.json().get("Items", [])
        return [{
            'jan': keyword, 'name': i['Item']['itemName'], 'price': i['Item']['itemPrice'],
            'shop': '楽天', 'url': i['Item']['itemUrl']
        } for i in items]

# --- 2. Yahoo API ---
async def fetch_yahoo(keyword):
    client_id = os.getenv("dmVyPTIwMjUwNyZpZD03VXZSWXFucXo2Jmhhc2g9WVdNMk1qQmlORGRpWmpKbE1UaGxNQQ")
    if not client_id: return []
    url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
    headers = {"User-Agent": f"YahooAppID: {client_id}"}
    params = {"query": keyword, "results": 3, "sort": "+price"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, params=params, headers=headers)
        if res.status_code != 200: return []
        hits = res.json().get("hits", [])
        return [{
            'jan': keyword, 'name': h['name'], 'price': h['price'],
            'shop': 'Yahoo', 'url': h['url']
        } for h in hits]

# --- 3. じゃんぱら Scraping (Playwright) ---
async def fetch_janpara(page, keyword):
    results = []
    try:
        url = f"https://www.janpara.co.jp/sale/search/detail/?KEYWORDS={keyword}"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # ハードオフで成功した「リンク抽出ロジック」をじゃんぱら用に最適化
        links = await page.query_selector_all('a')
        for link in links:
            text = await link.inner_text()
            href = await link.get_attribute('href')
            # じゃんぱらの商品リンクは通常 "/sale/search/detail/?ITMCODE=" を含む
            if text and "円" in text and href and "ITMCODE" in href:
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                price = 0
                for l in lines:
                    nums = re.findall(r'\d+', l.replace(',', ''))
                    if nums and "円" in l:
                        price = int("".join(nums))
                        break
                if price > 0:
                    results.append({
                        'jan': keyword, 'name': max(lines, key=len), 'price': price,
                        'shop': 'じゃんぱら', 'url': f"https://www.janpara.co.jp{href}"
                    })
            if len(results) >= 3: break
    except Exception as e:
        print(f"⚠️ じゃんぱらエラー: {e}")
    return results

# --- メイン処理 ---
async def main():
    keyword = "iPhone 15 128GB" # 検索ワード
    all_data = []

    # API系を実行
    print(f"🔍 {keyword} を各サイトで検索中...")
    all_data.extend(await fetch_rakuten(keyword))
    all_data.extend(await fetch_yahoo(keyword))

    # スクレイピング系を実行
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        all_data.extend(await fetch_janpara(page, keyword))
        
        await browser.close()

    # スプレッドシートへ一括書き込み
    await update_spreadsheet(all_data)
    print("--- 全工程終了 ---")

if __name__ == "__main__":
    asyncio.run(main())
