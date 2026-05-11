import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 你的 Google 試算表 ID
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def main():
    today = datetime.date.today()
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在讀取試算表...")
    try:
        response = session.get(SHEET_URL)
        response.encoding = 'utf-8'
        # 修正：強制去除標頭的所有空格
        config_df = pd.read_csv(io.StringIO(response.text))
        config_df.columns = [c.strip() for c in config_df.columns]
        print(f"成功讀取試算表，共有 {len(config_df)} 筆資料")
    except Exception as e:
        print(f"讀取失敗，請檢查權限或 ID: {e}")
        return

    # 取得代號並過濾空值
    tickers = config_df['股票代號'].dropna().astype(str).str.strip().tolist()
    if not tickers:
        print("警告：試算表中沒有找到任何股票代號！")
        return

    print(f"正在抓取數據: {tickers[:5]}...")
    try:
        # 下載 150 天數據
        raw_df = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)
    except Exception as e:
        print(f"Yahoo Finance 抓取失敗: {e}")
        return

    passed = []
    for index, row in config_df.iterrows():
        ticker = str(row['股票代號']).strip().upper()
        if ticker == 'NAN' or not ticker: continue
        
        try:
            # 取得該股數據
            if len(tickers) == 1:
                df_stock = raw_df.dropna()
            else:
                df_stock = raw_df[ticker].dropna()
                
            if df_stock.empty: continue
            
            # 讀取設定 (加入預設值防止出錯)
            ma_days = int(row.get('MA設定', 20))
            is_hold = str(row.get('是否持股', '')).strip() == "是"
            note = str(row.get('備註', '')) if pd.notnull(row.get('備註')) else ""
            manual_e = str(row.get('手動財報日', '')).strip()
            
            # 計算 MA
            close_price = df_stock['Close'].iloc[-1]
            ma_val = df_stock['Close'].rolling(ma_days).mean().iloc[-1]
            diff_ratio = (close_price / ma_val) - 1
            
            # 判定條件：持有者必過，非持有者需符合偏離度 1% 內
            if is_hold or abs(diff_ratio) <= 0.01:
                e_str = manual_e if manual_e not in ['nan', ''] else "N/A"
                
                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(close_price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": e_str,
                    "Is_Portfolio": is_hold,
                    "Note": note
                })
        except Exception as e:
            print(f"處理 {ticker} 時發生錯誤: {e}")

    # 生成 HTML (略，同前一份邏輯)
    # ... (請沿用之前的生成 HTML 代碼區塊)
    print(f"成功篩選出 {len(passed)} 檔標的")
