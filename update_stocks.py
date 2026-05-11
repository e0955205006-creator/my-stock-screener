import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 核心連動配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&timestamp={datetime.datetime.now().timestamp()}"

def main():
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在下載試算表...")
    try:
        response = session.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"讀取失敗: {e}")
        return

    tickers = df['Ticker'].dropna().astype(str).str.strip().tolist()
    print(f"下載股票數據: {tickers}")
    data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)

    results_html = ""
    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            ma_len = int(row.get('MA', 20)) if pd.notnull(row.get('MA')) else 20
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            e_day = str(row.get('Earnings', 'N/A'))
            
            # 數據處理
            s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(ma_len).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            # 篩選條件
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                diff_color = "text-danger" if diff < 0 else "text-success"
                
                # 使用 % 格式化避開 f-string 的大括號衝突
                card_template = '''
                <div class="card mb-4 shadow border-0">
                    <div class="card-header %s text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">%s <span class="badge bg-warning text-dark ms-2">%s</span></h5>
                        <span class="badge bg-light text-dark">財報日: %s</span>
                    </div>
                    <div class="card-body">
                        <p class="mb-2"><b>%sMA 偏離:</b> <span class="%s" style="font-weight:bold;">%.2f%%</span> | <b>目前價格:</b> $%.2f</p>
                        <div id="tv_%s" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>
                        new TradingView.widget({
                          "autosize": true, "symbol": "%s", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
                          "container_id": "tv_%s", "hide_top_toolbar": true,
                          "studies": [ { "id": "MASimple@tv-basicstudies", "inputs": { "length": %d } } ]
                        });
                        </script>
                    </div>
                </div>''' % (bg, symbol, note if is_hold else "", e_day, ma_len, diff_color, diff*100, price, symbol, symbol, symbol, ma_len)
                results_html += card_template
        except:
            continue

    final_html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>美股監控</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light py-5"><div class="container" style="max-width:800px;"><div class="text-center mb-5"><h2 class="fw-bold">🎯 美股雲端連動儀表板</h2><p class="text-muted">最後更新: {today_str} (台北)</p></div>{results_html if results_html else '<p class="text-center">目前無符合條件股票</p>'}</div></body></html>'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("✅ 網頁生成成功")

if __name__ == "__main__":
    main()
