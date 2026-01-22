import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# Google Sheets 認証
def get_gspread_client():
    json_creds = os.environ.get("GSPREAD_SERVICE_ACCOUNT")
    creds_dict = json.loads(json_creds)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# じゃんぱらで価格を取得
def check_janpara_gold(jan):
    # 検索URLを「在庫あり」に絞らない設定に変更して試す
    url = f"https://www.janpara.co.jp/sale/search/result/?KEYWORDS={jan}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 商品リストを取得
        items = soup.find_all(class_="item_list")
        
        valid_prices = []
        for item in items:
            # 価格が書かれているタグを広く探す
            price_tag = item.select_one(".item_price, .price_detail, .price")
            
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                # 数字以外の文字を消す
                price_text = price_text.replace("￥", "").replace(",", "").replace("円", "").replace("税込み", "")
                try:
                    price = int(price_text)
                    valid_prices.append(price)
                except:
                    continue
        
        return min(valid_prices) if valid_prices else None

    except Exception as e:
        print(f"Error: {e}")
        return None

# メイン処理
def main():
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("SPREADSHEET_ID")).get_worksheet(0)
    
    jan_list = sheet.col_values(1)[1:]
    
    for i, jan in enumerate(jan_list, start=2):
        if not jan: continue
        
        price = check_janpara_gold(jan)
        print(f"JAN: {jan}, price: {price}")
        
        if price:
            sheet.update_cell(i, 2, price)
            sheet.update_cell(i, 3, "じゃんぱら修正版")
        
        time.sleep(3) # サイトに嫌われないよう少し長めに待機

if __name__ == "__main__":
    main()
