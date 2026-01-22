import os
import json
import requests
from bs4 import BeautifulSoup
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

# 1. 楽天APIから商品名を取得（スプレッドシートへの記録用）
def get_product_name_by_jan(jan):
    app_id = os.environ.get("RAKUTEN_APP_ID")
    url = f"https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601?format=json&keyword={jan}&applicationId={app_id}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("Items"):
            return data["Items"][0]["Item"]["itemName"][:30]
    except:
        return "商品名取得失敗"
    return None

# 2. じゃんぱらの「JANコード詳細ページ」を直接見に行く
def check_janpara_direct(jan):
    # じゃんぱらは詳細URLにJANを含める仕組みがあるため、検索をスキップして直接アクセス
    url = f"https://www.janpara.co.jp/sale/search/result/?KEYWORDS={jan}&CHKOUTRE=ON"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select(".item_list")
        
        valid_prices = []
        for item in items:
            # 売り切れ除外
            if any(x in item.get_text() for x in ["品切れ", "SOLD OUT", "ご成約"]): continue
            
            price_tag = item.select_one(".item_price, .price_detail, .price")
            if price_tag:
                # 文字列から数字のみを抽出
                price_num = "".join(re.findall(r'\d+', price_tag.get_text()))
                if price_num:
                    valid_prices.append(int(price_num))
        
        return min(valid_prices) if valid_prices else None
    except:
        return None

def main():
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("SPREADSHEET_ID")).get_worksheet(0)
    jan_list = sheet.col_values(1)[1:] 
    
    for i, jan in enumerate(jan_list, start=2):
        print(f"--- 行{i} 処理開始: {jan} ---")
        if not jan or len(str(jan)) < 10:
            print("有効なJANコードではありません。")
            continue
            
        # 取得開始
        price = check_janpara_direct(jan)
        
        # 名前はシートへのメモ用に取得
        name = get_product_name_by_jan(jan)
        
        print(f"推測商品名: {name}")
        print(f"取得価格: {price}")
        
        if price:
            sheet.update_cell(i, 2, price)
            sheet.update_cell(i, 3, f"じゃんぱら({name})")
            print("書き込み成功")
        else:
            print("価格が見つかりませんでした（在庫なし等）")
        
        time.sleep(3)

if __name__ == "__main__":
    main()
