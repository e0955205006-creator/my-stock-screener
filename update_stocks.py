import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 核心配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&timestamp={datetime.datetime.now().timestamp()}"

# 2. HTML 模板 (將 JavaScript 的 { } 寫死，不讓 Python 解析)
CARD_TEMPLATE = """
<div class="card mb-4 shadow border-0">
    <div class="card-header {{BG_CLASS}} text-white d-flex justify-content-between align-items-center">
        <h5 class="mb-0">{{SYMBOL}} <span class="badge bg-warning text-dark ms-2">{{NOTE}}</span></h5>
        <span class="badge bg-light text-dark">財報日: {{EARNINGS}}</span>
    </div>
    <div class="card-body">
        <p class="mb-2"><b>{{MA_LEN}}MA 偏離:</b> <span class="{{DIFF_COLOR}}" style="font-weight:bold;">{{DIFF_STR}}</span> | <b>目前價格:</b> ${{PRICE}}</p>
        <div id="tv_{{SYMBOL}}" style="height:400px;"></div>
        <script src="https://s3.tradingview.com/tv.js"></script>
        <script>
        new TradingView.widget({
          "autosize": true, "symbol": "{{SYMBOL}}", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
          "container_id": "tv_{{SYMBOL}}", "hide_top_toolbar": true,
          "studies": [ { "id": "MASimple@tv-basicstudies", "inputs": { "length": {{MA_LEN}} } } ]
        });
        </script>
    </div>
</div>
"""

def main():
    today_str = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = session.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"Read error: {e}")
        return

    tickers = df['Ticker'].dropna().astype(str).str.strip().tolist()
    data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)

    results_html = ""
    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            ma_len = str(int(row.get('MA', 20)))
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            e_day = str(row.get('Earnings', 'N/A'))
            
            s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(int(ma_len)).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            if is_hold or abs(diff) <= 0.01:
                # 執行字串替換
                c = CARD_TEMPLATE
                c = c.replace("{{SYMBOL}}", symbol)
                c = c.replace("{{BG_CLASS}}", "bg-dark" if is_hold else "bg-primary")
                c = c.replace("{{NOTE}}", note if is_hold else "")
                c = c.replace("{{EARNINGS}}", e_day)
                c = c.replace("{{MA_LEN}}", ma_len)
                c = c.replace("{{DIFF_COLOR}}", "text-danger" if diff < 0 else "text-success")
                c = c.replace("{{DIFF_STR}}", f"{diff*100:.2f}%")
                c = c.replace("{{PRICE}}", f"{price:.2f}")
                results_html += c
        except: continue

    page_html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light py-5"><div class="container" style="max-width:800px;"><h2 class="text-center fw-bold">🎯 美股連動儀表板</h2><p class="text-center text-muted">最後更新: {today_str}</p><hr>{results_html if results_html else '<p class="text-center">無符合條件股票</p>'}</div></body></html>'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page_html)

if __name__ == "__main__":
    main()
