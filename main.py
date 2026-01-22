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

# 共通ヘッダー：本物のブラウザになりすます
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

def fetch_janpara(jan):
    url = f"https://www.janpara.co.jp/sale/search/result/?KEYWORDS={jan}&CHKOUTRE=ON"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 価格タグのクラス名が動的に変わる可能性があるため、複数のパターンで抽出
        price_tags = soup.select(".item_price, .price_detail, .price")
        prices = []
        for p in price_tags:
            if "品切れ" in p.parent.get_text(): continue
            num = "".join(re.findall(r'\d+', p.get_text()))
            if num: prices.append(int(num))
        return min(prices) if prices else None
    except:
        return None

def fetch_iosis(jan):
    url = f"https://iosys.co.jp/items?q={jan}"
    try:
        # イオシスはブロックが厳しいためセッションを維持
        session = requests.Session()
        res = session.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        price_tags = soup.select(".item-list__price, .price")
        prices = []
        for p in price_tags:
            num = "".join(re.findall(r'\d+', p.get_text()))
            if num: prices.append(int(num))
        return min(prices) if prices else None
    except:
        return None

def main():
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("SPREADSHEET_ID")).get_worksheet(0)
    jan_list = sheet.col_values(1)[1:] 
    
    for i, jan in enumerate(jan_list, start=2):
        print(f"--- 行{i} 処理開始: {jan} ---")
        if not jan or len(str(jan)) < 10: continue
        
        price_jan = fetch_janpara(jan)
        time.sleep(2) # サイトへの負荷を下げてブロックを回避
        price_io = fetch_iosis(jan)
        
        print(f"じゃんぱら: {price_jan}, イオシス: {price_io}")
        
        valid = [p for p in [price_jan, price_io] if p is not None]
        if valid:
            final_p = min(valid)
            source = "じゃんぱら" if final_p == price_jan else "イオシス"
            sheet.update_cell(i, 2, final_p)
            sheet.update_cell(i, 3, f"{source}在庫あり")
            print(f"書き込み成功: {final_p}")
        else:
            sheet.update_cell(i, 3, "在庫なし（またはブロック）")
        
        time.sleep(3)

if __name__ == "__main__":
    main()
