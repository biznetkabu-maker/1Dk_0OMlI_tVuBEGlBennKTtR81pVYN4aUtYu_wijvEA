import asyncio
import os
import json
import re
import gspread
import httpx
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

# --- 設定 ---
SHEET_NAME = "Indevia.system"
WORKSHEET_NAME = "02_Purchase_Control"
LINE_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")  # 任意

def line_notify(msg):
    if not LINE_TOKEN:
        return
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    data = {"message": msg}
    try:
        httpx.post(url, headers=headers, data=data, timeout=10)
    except:
        pass

def get_gspread_client():
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    env_json = os.getenv("GSPREAD_SERVICE_ACCOUNT")
    if not env_json:
        raise ValueError("❌ Secrets 'GSPREAD_SERVICE_ACCOUNT' が設定されていません。")
    key_json = json.loads(env_json)
    creds = Credentials.from_service_account_info(key_json, scopes=scope)
    return gspread.authorize(creds)

async def update_spreadsheet(data_list):
    if not data_list:
        print("⚠️ 書き込むデータがないためスキップします。")
        return
    try:
        client = get_gspread_client()
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)

        rows = [[
            item['jan'],
            item['price'],
            item['shop'],
            item['url'],
            item.get('image', ''),
            item.get('category', ''),
            '',
            '',
            '',
            '',
            item['name']
        ] for item in data_list]

        sheet.append_rows(rows)
        print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")

    except Exception as e:
        print(f"❌ スプレッドシート書き込みエラー: {e}")

async def fetch_rakuten(keyword):
    app_id = os.getenv("RAKUTEN_APP_ID")
    if not app_id:
        return []

    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    params = {
        "applicationId": app_id,
        "keyword": keyword,
        "hits": 3,
        "format": "json",
        "sort": "+itemPrice"
    }

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, params=params)
            if res.status_code != 200:
                return []

            items = res.json().get("Items", [])
            results = []

            for i in items:
                item = i["Item"]
                results.append({
                    "jan": item.get("janCode") or keyword,
                    "name": item["itemName"],
                    "price": item["itemPrice"],
                    "shop": "楽天",
                    "url": item["itemUrl"],
                    "image": item.get("mediumImageUrls", [{}])[0].get("imageUrl", ""),
                    "category": item.get("genreId", "")
                })

            return results

        except:
            return []

async def fetch_yahoo(keyword):
    client_id = os.getenv("YAHOO_CLIENT_ID")
    if not client_id:
        return []

    url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
    params = {
        "appid": client_id,
        "query": keyword,
        "results": 3,
        "sort": "+price"
    }

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, params=params)

            if res.status_code != 200:
                print(f"⚠️ YahooAPIエラー: Status {res.status_code}")
                return []

            hits = res.json().get("hits", [])
            results = []

            for h in hits:
                results.append({
                    "jan": h.get("jan_code") or keyword,
                    "name": h.get("name"),
                    "price": h.get("price"),
                    "shop": "Yahoo",
                    "url": h.get("url"),
                    "image": h.get("image", {}).get("medium", ""),
                    "category": h.get("category_id", "")
                })

            return results

        except:
            return []

async def fetch_janpara(page, keyword):
    results = []
    try:
        url = f"https://www.janpara.co.jp/sale/search/detail/?KEYWORDS={keyword}"
        await page.goto(url, wait_until="load", timeout=60000)

        items = await page.query_selector_all("a")

        for item in items:
            text = await item.inner_text()
            href = await item.get_attribute("href")

            if text and "円" in text and href and "ITMCODE" in href:
                price_match = re.search(r"([0-9,]+)円", text.replace("\n", ""))
                if price_match:
                    price = int(price_match.group(1).replace(",", ""))
                    name = max([l.strip
