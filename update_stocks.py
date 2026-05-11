import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 配置 (請確保 SHEET_ID 正確)
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def main():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在讀取試算表...")
    try:
        # 加上 params={'t': datetime.datetime.now().timestamp()} 確保抓到 Google 最新的 CSV
        response = session.get(SHEET_URL, params={'cache_bust': datetime.datetime.now().timestamp()})
        response.encoding = 'utf-8'
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [c.strip() for c in df.columns] # 清除標頭空格
    except Exception as e:
        print(f"讀取失敗: {e}")
        return

    # 檢查必要欄位
    if 'Ticker' not in df.columns:
        print(f"錯誤：找不到 Ticker 欄位，目前標頭為: {list(df.columns)}")
        return
        
    tickers = df['Ticker'].dropna().astype(str).str.strip().tolist()
    print(f"清單內股票: {tickers}")
    
    try:
        data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)
    except:
        print("下載 Yahoo 數據失敗")
        return

    results_html = ""
    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            if symbol == 'NAN' or not symbol: continue
            
            # --- 判斷邏輯：對應你的 Y/N ---
            # 只要 Hold 欄位包含 "Y" (不分大小寫) 就視為持有
            hold_val = str(row.get('Hold', '')).strip().upper()
            is_hold = "Y" in hold_val 
            
            ma_len = int(row.get('MA', 20)) if pd.notnull(row.get('MA')) else 20
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            e_day = str(row.get('Earnings', 'N/A'))
            
            # 獲取價格與均線
            s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(ma_len).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            # 顯示判定：持有 (Y) 或 偏離 1% 內
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                results_html += f"""
                <div class="card mb-4 shadow border-0">
                    <div class="card-header {bg} text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">{symbol} {f'<span class="badge bg-warning text-dark ms-2">{note}</span>' if is_hold else ""}</h5>
                        <span class="badge bg-light text-dark">財報日: {e_day}</span>
                    </div>
                    <div class="card-body">
                        <p class="mb-2"><b>{ma_len}MA 偏離:</b> <span class="{"text-danger" if diff < 0 else "text-success"}">{diff*100:.2f}%</span> | <b>目前價格:</b> ${price:.2f}</p>
                        <div id="tv_{symbol}" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>
                        new TradingView.widget({{
                          "autosize": true, "symbol": "{symbol}", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
                          "container_id": "tv_{symbol}", "hide_top_toolbar": true,
                          "studies": [ {{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {ma_len} }} }} ]
                        }});
                        </script>
                    </div>
                </div>"""
        except Exception as e:
            print(f"處理 {symbol} 時發生錯誤: {e}")
            continue

    now = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    
    # 完整的網頁輸出
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>美股監控</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light py-5"><div class="container" style="max-width:850px;"><h2 class="text-center mb-0">🎯 美股雲端監控儀表板</h2><p class="text-center text-muted small mb-4">最後更新: {now} (台北)</p><div class="alert alert-secondary py-2 text-center small">連動後台：Google Sheets (Ticker/Hold/MA/Earnings/Note)</div><hr>{results_html if results_html else '<div class="alert alert-warning text-center">目前無符合條件股票 (請檢查試算表 Hold 是否為 Y)</div>'}</div></body></html>''')

if __name__ == "__main__":
    main()
