import asyncio
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

async def safe_text(item, selector):
    try:
        el = await item.query_selector(selector)
        if not el:
            return ""
        return (await el.inner_text()).strip()
    except:
        return ""

async def update_spreadsheet(data_list):
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        key_json_str = os.getenv("GSPREAD_SERVICE_ACCOUNT")
        if not key_json_str:
            raise RuntimeError("GSPREAD_SERVICE_ACCOUNT が設定されていません")

        key_json = json.loads(key_json_str)
        creds = Credentials.from_service_account_info(key_json, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open("Indevia.system").worksheet("02_Purchase_Control")

        rows = [
            [
                item['jan'], item['price'], item['shop'], item['url'],
                '', '', '', '', '', item['name']
            ]
            for item in data_list
        ]

        sheet.append_rows(rows)
        print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")

    except Exception as e:
        print(f"❌ スプレッドシート追記エラー: {e}")

async def main():
    keyword = "iPhone"
    async with async_playwright() as p:
        # 【重要修正】headless=Trueに戻し、User-Agentを偽装してボット判定を回避します
        browser = await p.chromium.launch(headless=True)
        
        # 一般的なブラウザ（Chrome on Windows）のふりをする設定
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("--- スクレイピング開始（Headlessモード） ---")
        all_results = []

        try:
            target_url = f"https://netmall.hardoff.co.jp/search/?q={keyword}"
            print(f"アクセス中: {target_url}")
            
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
            # ページタイトルを表示して、正しくアクセスできたか確認
            title = await page.title()
            print(f"ページタイトル: {title}")

            # 念のため少し待機
            await page.wait_for_timeout(3000)

            # --- デバッグ用：スクリーンショットを保存 ---
            # これで「なぜデータが取れないか」を目視確認できます（ファイル出力される場合）
            await page.screenshot(path="debug_page.png")
            print("📸 現在のページ状態を 'debug_page.png' に保存しました")

            # HTMLの一部を出力して、構造を確認
            content = await page.content()
            if "アクセスが拒否されました" in content or "Forbidden" in title:
                print("⚠️ サイトからアクセスブロックされています。")
            
            # セレクタ探索
            selector = ".p-result-card" # 古い可能性が高い
            # selector = ".item-card" # ← もしクラス名が変わっていたらここを変える候補

            items = await page.query_selector_all(selector)
            
            if len(items) == 0:
                print(f"⚠️ 指定したクラス名 ({selector}) が見つかりませんでした。")
                print("HTML構造が変わっているか、検索結果が0件か、ロードが完了していません。")
            else:
                print(f"検索結果: {len(items)} 件見つかりました")

            for item in items[:3]:
                name = await safe_text(item, ".p-result-card__title")
                price_text = await safe_text(item, ".p-result-card__price")
                
                price = 0
                if price_text:
                    import re
                    nums = re.findall(r'\d+', price_text)
                    if nums:
                        price = int("".join(nums))

                print(f"取得データ: {name} / {price}円")

                all_results.append({
                    'jan': keyword,
                    'name': name,
                    'price': price,
                    'shop': 'ハードオフ',
                    'url': target_url
                })

        except Exception as e:
            print(f"⚠️ エラー発生: {e}")
            import traceback
            traceback.print_exc()

        # データが取れなかった場合
        if not all_results:
            print("データなしのため、スプレッドシートには書き込みません（またはエラーログを記録します）")
            # デバッグ用に失敗ログを残すなら以下を有効化
            all_results.append({
                'jan': 'DEBUG-LOG',
                'name': f'取得失敗: タイトル[{title}]',
                'price': 0,
                'shop': 'SYSTEM',
                'url': '---'
            })

        await update_spreadsheet(all_results)
        await browser.close()
        print("--- 処理終了 ---")

if __name__ == "__main__":
    asyncio.run(main())
