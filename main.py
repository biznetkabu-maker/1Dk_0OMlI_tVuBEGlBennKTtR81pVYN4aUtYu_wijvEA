import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 設定 ---
RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID")

def get_gspread_client():
    json_creds = os.environ.get("GSPREAD_SERVICE_ACCOUNT")
    creds_dict = json.loads(json_creds)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 1. JANコードから商品名を楽天APIで取得
def get_product_name_by_jan(jan):
    if not RAKUTEN_APP_ID:
        return None
    url = f"https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601?format=json&keyword={jan}&applicationId={RAKUTEN_APP_ID}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("Items"):
            full_name = data["Items"][0]["Item"]["itemName"]
            # 不要な単語を削り、検索しやすい最初の2単語程度を抽出
            clean_name = full_name.replace("【", " ").replace("】", " ").replace("中古", "").replace("新品", "").replace("★", "")
            words = clean_name.split()
            return " ".join(words[:2]) if len(words) >= 2 else clean_name.strip()
    except:
        return None
    return None

# 2. じゃんぱらで価格を取得（解析精度を大幅強化）
def check_janpara_by_name(product_name):
    if not product_name:
        return None
    # 検索キーワードをエンコードしてURL作成
    url = f"https://www.janpara.co.jp/sale/search/result/?KEYWORDS={product_name}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # じゃんぱらの商品リストの各枠を特定
        items = soup.select(".item_list")
        
        valid_prices = []
        for item in items:
            # 価格が書かれている複数の可能性をチェック
            price_tag = item.select_one(".item_price, .price_detail, .price, span[class*='price']")
            
            if price_tag:
                # 「12,800円」などの文字列から数字だけを抽出
                price_text = "".join(filter(str.isdigit, price_tag.get_text()))
                if price_text:
                    valid_prices.append(int(price_text))
        
        # 最安値を返す
        return min(valid_prices) if valid_prices else None
    except Exception as e:
        print(f"解析エラー: {e}")
        return None

# メイン処理
def main():
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("SPREADSHEET_ID")).get_worksheet(0)
    jan_list = sheet.col_values(1)[1:] 
    
    for i, jan in enumerate(jan_list, start=2):
        print(f"--- 行{i} 処理開始 ---")
        if not jan: continue
            
        product_name = get_product_name_by_jan(jan)
        print(f"JAN: {jan} -> 商品名推測: {product_name}")
        
        price = check_janpara_by_name(product_name)
        print(f"結果価格: {price}")
        
        if price:
            print(f"スプレッドシートに書き込み中: {price}")
            sheet.update_cell(i, 2, price) 
            sheet.update_cell(i, 3, f"じゃんぱら({product_name})") 
        
        time.sleep(3)

if __name__ == "__main__":
    main()
