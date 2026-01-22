import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import re

def get_gspread_client():
    json_creds = os.environ.get("GSPREAD_SERVICE_ACCOUNT")
    creds_dict = json.loads(json_creds)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 1. 楽天API：価格も同時に取得するように改良（最も確実）
def fetch_rakuten_lowest(jan):
    app_id = os.environ.get("RAKUTEN_APP_ID")
    url = f"https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601?format=json&keyword={jan}&applicationId={app_id}&sort=%2BitemPrice"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("Items"):
            # 最安値と商品名を取得
            price = data["Items"][0]["Item"]["itemPrice"]
            name = data["Items"][0]["Item"]["itemName"][:20]
            return price, name
    except:
        pass
    return None, None

# 2. メルカリの検索結果から相場を推測（ブロックに強い）
def fetch_mercari_price(jan):
    # メルカリの公開検索用URL（非公式だが比較的安定）
    url = f"https://jp.mercari.com/search?keyword={jan}&status=on_sale"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        # 価格情報を正規表現で無理やり抜き出す
        prices = re.findall(r'price\\":(\d+)', res.text)
        if prices:
            valid_prices = [int(p) for p in prices if int(p) > 1000]
            return min(valid_prices)
    except:
        pass
    return None

def main():
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("SPREADSHEET_ID")).get_worksheet(0)
    jan_list = sheet.col_values(1)[1:] 
    
    for i, jan in enumerate(jan_list, start=2):
        print(f"--- 行{i} 処理開始: {jan} ---")
        if not jan: continue
        
        # まずは楽天APIで最安値を探す（APIなので100%ブロックされない）
        r_price, r_name = fetch_rakuten_lowest(jan)
        print(f"楽天最安値: {r_price}")
        
        # 補助としてメルカリ相場も見る
        m_price = fetch_mercari_price(jan)
        print(f"メルカリ相場: {m_price}")
        
        # スプレッドシートへ書き込み
        if r_price:
            sheet.update_cell(i, 2, r_price)
            sheet.update_cell(i, 3, f"楽天最安({r_name})")
            print(f"書き込み完了: {r_price}")
        elif m_price:
            sheet.update_cell(i, 2, m_price)
            sheet.update_cell(i, 3, "メルカリ在庫あり")
            print(f"書き込み完了: {m_price}")
        else:
            sheet.update_cell(i, 3, "市場在庫なし")
        
        time.sleep(2)

if __name__ == "__main__":
    main()
