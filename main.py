import asyncio
import os
import json
import random
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

# 紳士的運用のための設定
NG_WORDS = ["ジャンク", "JUNK", "難あり", "訳あり", "故障"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

async def update_spreadsheet(data_list):
    """スプレッドシートに追記"""
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        key_json = json.loads(os.environ["GSPREAD_SERVICE_ACCOUNT"])
        creds = Credentials.from_service_account_info(key_json, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("Indevia.system").worksheet("02_Purchase_Control")
        rows = [[item['jan'], item['price'], item['shop'], item['url'], '', '', '', '', '', item['name']] for item in data_list]
        sheet.append_rows(rows)
        print(f"✅ {len(rows)}件を追記しました。")
    except Exception as e:
        print(f"❌ 更新エラー: {e}")

async def get_shop_data(page, shop_name, url, item_sel, name_sel, price_sel, keyword):
    await asyncio.sleep(random.uniform(2, 5)) # ランダム待機
    results = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_selector(item_sel, timeout=10000)
        items = await page.query_selector_all(item_sel)
        for item in items[:5]:
            n_el = await item.query_selector(name_sel)
            p_el = await item.query_selector(price_sel)
            if n_el and p_el:
                name = (await n_el.inner_text()).strip()
                if any(word in name for word in NG_WORDS): continue
                price = int(''.join(filter(str.isdigit, await p_el.inner_text())))
                results.append({'jan': keyword, 'price': price, 'shop': shop_name, 'url': url, 'name': name})
    except:
        print(f"⚠️ {shop_name} 取得失敗")
    return results

async def main():
    keyword = "4549995423319" # テスト用の商品番号
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = await context.new_page()
        all_res = []
        all_res.extend(await get_shop_data(page, "じゃんぱら", f"https://www.janpara.co.jp/sale/search/detail/?KEYWORDS={keyword}", ".search_result_item", ".item_name", ".price", keyword))
        all_res.extend(await get_shop_data(page, "ハードオフ", f"https://netmall.hardoff.co.jp/search/?q={keyword}", ".p-result-card", ".p-result-card__title", ".p-result-card__price", keyword))
        if all_res:
            await update_spreadsheet(all_res)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
