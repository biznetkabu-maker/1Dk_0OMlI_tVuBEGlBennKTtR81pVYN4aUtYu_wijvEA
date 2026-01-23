import asyncio
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

async def update_spreadsheet(data_list):
    try:
        scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
        key_json = json.loads(os.environ["GSPREAD_SERVICE_ACCOUNT"])
        creds = Credentials.from_service_account_info(key_json, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("Indevia.system").worksheet("02_Purchase_Control")
        rows = [[item['jan'], item['price'], item['shop'], item['url'], '', '', '', '', '', item['name']] for item in data_list]
        sheet.append_rows(rows)
        print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")
    except Exception as e:
        print(f"❌ スプレッドシート追記エラー: {e}")

async def main():
    # ハードオフで「iPhone」を検索します（確実に在庫があるため）
    keyword = "iPhone"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"--- 最終テスト（ハードオフ）開始: {keyword} ---")
        all_results = []
        
        try:
            # ハードオフの検索ページへ
            target_url = f"https://netmall.hardoff.co.jp/search/?q={keyword}"
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
            # 商品カードが表示されるのを待つ
            await page.wait_for_selector(".p-result-card", timeout=20000)
            items = await page.query_selector_all(".p-result-card")
            
            for item in items[:5]:
                name_el = await item.query_selector(".p-result-card__title")
                price_el = await item.query_selector(".p-result-card__price")
                
                if name_el and price_el:
                    name = (await name_el.inner_text()).strip()
                    price_text = await price_el.inner_text()
                    price = int(''.join(filter(str.isdigit, price_text)))
                    
                    all_results.append({
                        'jan': keyword, 'name': name, 'price': price,
                        'shop': 'ハードオフ', 'url': target_url
                    })
                    print(f"発見: {name} / {price}円")
                    
        except Exception as e:
            print(f"⚠️ 調査中エラー: {e}")

        # 結果があれば書き込む
        if all_results:
            await update_spreadsheet(all_results)
        else:
            # 万が一在庫がない場合でも、システム疎通確認として1行書きます
            print("❌ 在庫なしのため、ダミーデータを書き込みます。")
            dummy = [{'jan': 'TEST-OK', 'price': 0, 'shop': 'SUCCESS', 'url': '---', 'name': 'システム連携成功'}]
            await update_spreadsheet(dummy)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
