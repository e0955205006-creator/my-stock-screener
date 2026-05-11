import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def main():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在讀取試算表...")
    try:
        response = session.get(SHEET_URL)
        response.encoding = 'utf-8'
        df = pd.read_csv(io.StringIO(response.text))
        # --- 自動對齊標題列 ---
        col_map = {c: c.strip() for c in df.columns}
        df = df.rename(columns=col_map)
        print(f"目前偵測到的標題: {list(df.columns)}")
    except Exception as e:
        print(f"讀取失敗: {e}")
        return

    # 找出『股票代號』那一欄
    ticker_col = [c for c in df.columns if '股票代號' in c or 'Ticker' in c]
    if not ticker_col:
        print("錯誤：找不到『股票代號』欄位！")
        return
    
    tickers = df[ticker_col[0]].dropna().astype(str).str.strip().tolist()
    print(f"正在抓取數據: {tickers[:5]}...")
    
    # 強制獲取數據，失敗也繼續
    try:
        data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)
    except:
        print("Yahoo Finance 下載發生部分錯誤")

    results_html = ""
    for _, row in df.iterrows():
        try:
            symbol = str(row[ticker_col[0]]).strip().upper()
            if symbol == 'NAN' or not symbol: continue
            
            # 取得該股設定 (使用模糊匹配避免標題多字)
            is_hold = any(str(row[c]).strip() == "是" for c in df.columns if '持股' in c)
            ma_setting = next((row[c] for c in df.columns if 'MA' in c), 20)
            ma_len = int(ma_setting) if pd.notnull(ma_setting) else 20
            note = next((str(row[c]) for c in df.columns if '備註' in c), "")
            note = note if note != 'nan' else ""
            
            # 抓取技術指標
            s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(ma_len).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            # 判定條件：持有 或 偏離 1% 內
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                results_html += f"""
                <div class="card mb-4 shadow">
                    <div class="card-header {bg} text-white d-flex justify-content-between">
                        <h5 class="mb-0">{symbol} {f'<span class="badge bg-warning text-dark ms-2">持股: {note}</span>' if is_hold else ""}</h5>
                    </div>
                    <div class="card-body">
                        <p>{ma_len}MA 偏離: <b style="color:{"red" if diff < 0 else "green"}">{diff*100:.2f}%</b> | 價格: ${price:.2f}</p>
                        <div id="tv_{symbol}" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>new TradingView.widget({{"autosize":true,"symbol":"{symbol}","interval":"D","theme":"light","container_id":"tv_{symbol}","hide_top_toolbar":true,"studies":[{{"id":"MASimple@tv-basicstudies","inputs":{{"length":{ma_len}}}}}]}});</script>
                    </div>
                </div>"""
        except: continue

    now = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>監控</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light p-5"><div class="container" style="max-width:850px;"><h2 class="text-center mb-4">📈 美股監控儀表板</h2><p class="text-center text-muted">最後更新 (台北): {now}</p><hr>{results_html}</div></body></html>')

if __name__ == "__main__":
    main()
