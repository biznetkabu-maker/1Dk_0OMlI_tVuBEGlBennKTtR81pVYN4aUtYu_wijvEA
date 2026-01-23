import asyncio
import os
import json
import re
import gspread
from google.oauth2.service_account import Credentials
from playwright.async_api import async_playwright

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

        # ワークシート名を再確認してください
        sheet = client.open("Indevia.system").worksheet("02_Purchase_Control")

        rows = [
            [
                item['jan'], item['price'], item['shop'], item['url'],
                '', '', '', '', '', item['name']
            ]
            for item in data_list
        ]

        if rows:
            sheet.append_rows(rows)
            print(f"✅ スプレッドシートに {len(rows)} 件書き込みました！")
        else:
            print("⚠️ 書き込むデータがありませんでした。")

    except Exception as e:
        print(f"❌ スプレッドシート追記エラー: {e}")

async def main():
    keyword = "iPhone"
    async with async_playwright() as p:
        # headless=True, User-Agent偽装あり
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("--- スクレイピング開始（汎用モード） ---")
        all_results = []

        try:
            target_url = f"https://netmall.hardoff.co.jp/search/?q={keyword}"
            print(f"アクセス中: {target_url}")
            
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
            # ページ読み込み後の安定化待機
            await page.wait_for_timeout(5000)
            
            title = await page.title()
            print(f"ページタイトル: {title}")

            # --- 新ロジック: クラス名に頼らず、リンク構造から商品を探す ---
            print("商品データを探索中...")
            
            # ページ内のすべてのリンク(aタグ)を取得
            links = await page.query_selector_all('a')
            print(f"ページ内のリンク総数: {len(links)}")
            
            valid_items = []
            
            for link in links:
                # リンクの中のテキストを取得
                text = await link.inner_text()
                href = await link.get_attribute('href')
                
                # 商品カードの条件推測:
                # 1. テキストに「円」が含まれている（価格表示がある）
                # 2. リンク先が存在し、適度に長い（詳細ページへのリンク）
                # 3. テキストがある程度の長さがある（商品名などが含まれている）
                if text and "円" in text and href and len(href) > 5:
                    # 重複除外やノイズ除去のため、テキストの長さで簡易フィルタ
                    if len(text) > 10:
                        valid_items.append(link)
                        # デバッグ用にテキストの一部を表示
                        # print(f"候補発見: {text[:20]}...")

            print(f"商品と思われるリンク数: {len(valid_items)}")

            # 上位3件を処理
            for item in valid_items[:3]:
                raw_text = await item.inner_text()
                # 余分な空白を除去
                lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                
                # --- 情報抽出ロジック ---
                name = "名称不明"
                price = 0
                
                # 一番長い行を「商品名」と仮定する
                if lines:
                    name = max(lines, key=len)
                
                # 「円」を含む行、または数字だけの行から価格を探す
                for line in lines:
                    # 数字のみを抽出
                    nums = re.findall(r'\d+', line)
                    if nums:
                        val = int("".join(nums))
                        # 価格としてありえそうな値（例: 100円以上）かつ、「円」が含まれる行を優先
                        if val > 100 and ("円" in line or "税込" in line):
                            price = val
                            break
                        # 見つからない場合は数字だけで判定（バックアップ）
                        elif val > 100 and price == 0:
                            price = val

                print(f"📦 取得データ: {name[:30]}... / {price}円")

                if price > 0:
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

        # データ取得数確認
        if len(all_results) == 0:
            print("⚠️ データが見つかりませんでした。HTML構造が大幅に異なっている可能性があります。")
            # 念のためテストデータを送る（接続確認用）
            all_results.append({
                'jan': 'TEST-NODATA',
                'name': 'データ取得なし(HTML構造要確認)',
                'price': 0,
                'shop': 'SYSTEM',
                'url': target_url
            })

        await update_spreadsheet(all_results)
        await browser.close()
        print("--- 処理終了 ---")

if __name__ == "__main__":
    asyncio.run(main())
