import yfinance as yf
import pandas as pd
import datetime
import requests
import io

SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def main():
    session = requests.Session()
    
    try:
        response = session.get(SHEET_URL, params={'cb': datetime.datetime.now().timestamp()})
        response.encoding = 'utf-8'
        df = pd.read_csv(io.StringIO(response.text))
        # 強力清洗：去除所有隱形空格
        df.columns = [str(c).strip() for c in df.columns]
        debug_headers = list(df.columns)
        debug_first_row = df.iloc[0].to_dict() if not df.empty else "Empty"
    except Exception as e:
        print(f"Read error: {e}")
        return

    tickers = df['Ticker'].dropna().astype(str).str.strip().tolist() if 'Ticker' in df.columns else []
    
    results_html = ""
    if tickers:
        data = yf.download(tickers, period="150d", group_by='ticker', progress=False)
        
        for _, row in df.iterrows():
            try:
                symbol = str(row['Ticker']).strip().upper()
                # 判定 Hold：只要包含 Y (不論大小寫、空格)
                h_val = str(row.get('Hold', '')).strip().upper()
                is_hold = 'Y' in h_val
                
                ma_len = int(row.get('MA', 20))
                
                s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
                price = s_data['Close'].iloc[-1]
                ma_val = s_data['Close'].rolling(ma_len).mean().iloc[-1]
                diff = (price / ma_val) - 1
                
                if is_hold or abs(diff) <= 0.01:
                    results_html += f"<div><h3>{symbol} (Hold: {h_val})</h3><p>{ma_len}MA Diff: {diff*100:.2f}%</p></div>"
            except: continue

    now = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    
    # 診斷訊息：如果網頁還是空白，至少我們能看到這段文字
    debug_info = f"""
    <div class="alert alert-warning small">
        <b>[診斷資訊]</b><br>
        1. 偵測到的標頭: {debug_headers}<br>
        2. 第一筆資料樣貌: {debug_first_row}<br>
        3. 解析出的 Tickers: {tickers[:5]}...
    </div>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html><head><meta charset="utf-8"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
        <body class="p-5"><div class="container">
        <h2>📊 監控診斷面板</h2>
        <p>更新時間: {now}</p>
        {debug_info}
        <hr>
        {results_html if results_html else "<h4>⚠️ 篩選後無符合標的，請確認上述『第一筆資料』中的 Hold 是否確實為 Y</h4>"}
        </div></body></html>''')

if __name__ == "__main__":
    main()
