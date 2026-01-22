import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import urllib.parse

# --- 設定 ---
RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID")

def get_gspread_client():
    json_creds = os.environ.get("GSPREAD_SERVICE_ACCOUNT")
    creds_dict = json.loads(json_creds)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# 1. JANから商品名を取得（より具体的な型番を目指す）
def get_product_name_by_jan(jan):
    if not RAKUTEN_APP_ID: return None
    url = f"https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601?format=json&keyword={jan}&applicationId={RAKUTEN_APP_ID}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("Items"):
            full_name = data["Items"][0]["Item"]["itemName"]
            # ノイズ除去
            clean = full_name.replace("【", " ").replace("】", " ").replace("中古", "").replace("★", "")
            words = clean.split()
            # 検索精度を上げるため3単語程度使用
            return " ".join(words[:3]) if len(words) >= 3 else words[0]
    except:
        return None

# 2. じゃんぱらで「在庫あり」の価格のみを取得
def check_janpara_by_name(product_name):
    if not product_name: return None
    # 検索URL（在庫ありに絞り込むパラメータを付与）
    encoded_name = urllib.parse.quote(product_name)
    url = f"https://www.janpara.co.jp/sale/search/result/?KEYWORDS={encoded_name}&CHKOUTRE=ON"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # すべての商品リスト枠を取得
        items = soup.select(".item_list")
        valid_prices = []

        for item in items:
            # 売り切れ表示（「品切れ」や「SOLD OUT」など）がある枠は無視
            if "品切れ" in item.get_text() or "SOLD" in item.get_text().upper():
                continue
                
            # 価格タグを探す
            price_tag = item.select_one(".item_price, .price_detail, .price")
            if price_tag:
                # 数字のみを抽出
                price_num = "".join(filter(str.isdigit, price_tag.get_text()))
                if price_num:
                    valid_prices.append(int(price_num))
        
        return min(valid_prices) if valid_prices else None
    except:
        return None

# メイン処理
def main():
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("SPREADSHEET_ID")).get_worksheet(0)
    jan_list = sheet.col_values(1)[1:] 
    
    for i, jan in enumerate(jan_list, start=2):
        print(f"--- 行{i} 処理開始 ---")
        if not jan or len(str(jan)) < 10: continue
            
        name = get_product_name_by_jan(jan)
        print(f"JAN: {jan} -> 検索ワード: {name}")
        
        price = check_janpara_by_name(name)
        print(f"取得価格: {price}")
        
        if price:
            sheet.update_cell(i, 2, price)
            sheet.update_cell(i, 3, f"じゃんぱら({name})")
        
        time.sleep(3)

if __name__ == "__main__":
    main()
