import yfinance as yf
import pandas as pd
import datetime
import requests
import io
import os
import subprocess

# =================================================================
# 1. 配置區
# =================================================================
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
DEFAULT_MA = 20
SEARCH_RANGE = 0.01

def main():
    today = datetime.date.today()
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在讀取試算表...")
    try:
        response = session.get(SHEET_URL)
        response.encoding = 'utf-8'
        config_df = pd.read_csv(io.StringIO(response.text))
        config_df.columns = config_df.columns.str.strip()
    except Exception as e:
        print(f"讀取失敗: {e}")
        return

    tickers = config_df['股票代號'].dropna().astype(str).str.strip().tolist()
    print(f"正在下載數據...")
    raw_df = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)

    passed = []
    for index, row in config_df.iterrows():
        ticker = str(row['股票代號']).strip().upper()
        if not ticker or ticker == 'NAN': continue
        try:
            if ticker in raw_df.columns: df_stock = raw_df[ticker].dropna()
            elif isinstance(raw_df.columns, pd.MultiIndex) and ticker in raw_df.columns.levels[0]: df_stock = raw_df[ticker].dropna()
            else: continue
            
            ma_days = int(row.get('MA設定', DEFAULT_MA))
            is_hold = str(row.get('是否持股', '')).strip() == "是"
            note = str(row.get('備註', '')) if pd.notnull(row.get('備註')) else ""
            manual_e = str(row.get('手動財報日', '')).strip()

            close_price = df_stock['Close'].iloc[-1]
            ma_val = df_stock['Close'].rolling(ma_days).mean().iloc[-1]
            diff_ratio = (close_price / ma_val) - 1
            
            if is_hold or abs(diff_ratio) <= SEARCH_RANGE:
                passed.append({
                    "Symbol": ticker, "Price": round(float(close_price), 2),
                    "MA_Days": ma_days, "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": manual_e if manual_e not in ['nan', ''] else "N/A",
                    "Is_Portfolio": is_hold, "Note": note
                })
        except: continue

    passed.sort(key=lambda x: (not x['Is_Portfolio'], -x['Diff_Val']))

    # --- 生成網頁 (略，與之前相同) ---
    now_str = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    rows_html = "".join([f'<div class="card mb-4">...{x["Symbol"]}...</div>' for x in passed]) # 這裡省略細節，請保持你原本的 HTML 生成邏輯
    
    # 這裡請補上你完整的 HTML 生成代碼 ...
    html_final = f"<html>...{now_str}...{rows_html}</html>" 

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)
    print("index.html 生成成功！")

if __name__ == "__main__":
    main()
