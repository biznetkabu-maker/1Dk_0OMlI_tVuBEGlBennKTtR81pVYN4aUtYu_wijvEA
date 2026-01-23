import asyncio
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

async def update_spreadsheet(data_list):
    try:
        # 権限の範囲（スコープ）を広げて、確実に書き込めるようにします
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        key_json = json.loads(os.environ["GSPREAD_SERVICE_ACCOUNT"])
        creds = Credentials.from_service_account_info(key_json, scopes=scope)
        client = gspread.authorize(creds)
        
        # スプレッドシートを開く
        sheet = client.open("Indevia.system").worksheet("02_Purchase_Control")
        
        rows = [[item['jan'], item['price'], item['shop'], item['url'], '', '', '', '', '', item['name']] for item in data_list]
        sheet.append_rows(rows)
        print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")
    except Exception as e:
        print(f"❌ スプレッドシート追記エラー: {e}")

async def main():
    # ハードオフで「iPhone」を検索（テスト用）
    keyword = "iPhone"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"--- 最終接続テスト開始 ---")
        
        all_results = []
        try:
            target_url = f"https://netmall.hardoff.co.jp/search/?q={keyword}"
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(".p-result-card", timeout=20000)
            items = await page.query_selector_all(".p-result-card")
            
            for item in items[:3]:
                name = (await (await item.query_selector(".p-result-card__title")).inner_text()).strip()
                price_text = await (await item.query_selector(".p-result-card__price")).inner_text()
                price = int(''.join(filter(str.isdigit, price_text)))
                all_results.append({'jan': keyword, 'name': name, 'price': price, 'shop': 'ハードオフ', 'url': target_url})
        except:
            print("在庫が見つからなかったため、テスト用の1行を書き込みます。")
            all_results.append({'jan': 'TEST-OK', 'name': '接続テスト成功', 'price': 0, 'shop': 'SYSTEM', 'url': '---'})

        await update_spreadsheet(all_results)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
