import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 設定
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
        df.columns = [c.strip() for c in df.columns] # 強制去除標題空格
    except Exception as e:
        print(f"讀取失敗: {e}")
        return

    tickers = df['股票代號'].dropna().astype(str).str.strip().tolist()
    print(f"正在分析 {len(tickers)} 檔...")
    data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)

    results_html = ""
    for _, row in df.iterrows():
        symbol = str(row['股票代號']).strip().upper()
        is_hold = str(row.get('是否持股', '')).strip() == "是"
        ma_len = int(row.get('MA設定', 20))
        note = str(row.get('備註', '')) if pd.notnull(row.get('備註')) else ""
        manual_e = str(row.get('手動財報日', 'N/A')).strip()

        try:
            s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(ma_len).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            # 只顯示「持有」或「偏離 1% 內」
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                results_html += f"""
                <div class="card mb-4 shadow">
                    <div class="card-header {bg} text-white d-flex justify-content-between">
                        <span>{symbol} {"(持有: "+note+")" if is_hold else ""}</span>
                        <small>財報日: {manual_e}</small>
                    </div>
                    <div class="card-body">
                        <p>{ma_len}MA 偏離: {diff*100:.2f}% | 價格: ${price:.2f}</p>
                        <div id="tv_{symbol}" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>new TradingView.widget({{"autosize":true,"symbol":"{symbol}","interval":"D","theme":"light","container_id":"tv_{symbol}","hide_top_toolbar":true,"studies":[{{"id":"MASimple@tv-basicstudies","inputs":{{"length":{ma_len}}}}}]}});</script>
                    </div>
                </div>"""
        except: continue

    now = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'<html><head><meta charset="utf-8"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light p-5"><div class="container" style="max-width:800px;"><h2 class="text-center">📈 監控儀表板</h2><p class="text-center text-muted">最後更新: {now}</p><hr>{results_html}</div></body></html>')

if __name__ == "__main__":
    main()
