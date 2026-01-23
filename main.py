import asyncio
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

async def update_spreadsheet(data_list):
    """スプレッドシートに書き込む"""
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        key_json = json.loads(os.environ["GSPREAD_SERVICE_ACCOUNT"])
        creds = Credentials.from_service_account_info(key_json, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("Indevia.system").worksheet("02_Purchase_Control")
        
        # JAN, 価格, 店名, URL, 名称の順で作成
        rows = [[item['jan'], item['price'], item['shop'], item['url'], '', '', '', '', '', item['name']] for item in data_list]
        sheet.append_rows(rows)
        print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")
    except Exception as e:
        print(f"❌ スプレッドシート追記エラー: {e}")

async def main():
    # テストとして「iPhone」で検索します
    keyword = "iPhone"
    
    async with async_playwright() as p:
        # ブラウザを起動
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"--- 調査開始: {keyword} ---")
        all_results = []
        
        try:
            # じゃんぱらの検索結果ページへ直接移動
            target_url = f"https://www.janpara.co.jp/sale/search/detail/?KEYWORDS={keyword}"
            await page.goto(target_url, wait_until="domcontentloaded")
            
            # 商品の枠（最新のセレクタ）を待つ
            await page.wait_for_selector(".search_result_item", timeout=10000)
            
            # 商品リストを取得
            items = await page.query_selector_all(".search_result_item")
            
            for item in items[:5]: # 最初の5件だけ取得
                name_el = await item.query_selector(".item_name")
                price_el = await item.query_selector(".price")
                
                if name_el and price_el:
                    name = (await name_el.inner_text()).strip()
                    price_text = await price_el.inner_text()
                    # 数字以外（円やカンマ）を消して数値にする
                    price = int(''.join(filter(str.isdigit, price_text)))
                    
                    all_results.append({
                        'jan': keyword,
                        'name': name,
                        'price': price,
                        'shop': 'じゃんぱら',
                        'url': target_url
                    })
                    print(f"発見: {name} / {price}円")
                    
        except Exception as e:
            print(f"⚠️ 検索中にエラーが発生しました: {e}")

        # 結果があれば書き込む
        if all_results:
            await update_spreadsheet(all_results)
        else:
            print("❌ 商品が1件も見つかりませんでした。")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
