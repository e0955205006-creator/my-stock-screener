import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 核心配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&timestamp={datetime.datetime.now().timestamp()}"

def main():
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = session.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"讀取試算表失敗: {e}")
        return

    tickers = df['Ticker'].dropna().astype(str).str.strip().tolist()
    data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)

    cards = []
    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            ma_len = int(row.get('MA', 20)) if pd.notnull(row.get('MA')) else 20
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            e_day = str(row.get('Earnings', 'N/A'))
            
            s_data = data[symbol].dropna() if len(tickers) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(ma_len).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                d_color = "text-danger" if diff < 0 else "text-success"
                
                # 拆解 HTML 避免 Python 大括號衝突
                h = f'<div class="card mb-4 shadow border-0">'
                h += f'<div class="card-header {bg} text-white d-flex justify-content-between"><span>{symbol} <b>{note if is_hold else ""}</b></span><small>財報: {e_day}</small></div>'
                h += f'<div class="card-body"><p><b>{ma_len}MA 偏離:</b> <span class="{d_color}">{diff*100:.2f}%</span> | <b>價格:</b> ${price:.2f}</p>'
                h += f'<div id="tv_{symbol}" style="height:400px;"></div>'
                h += '<script src="https://s3.tradingview.com/tv.js"></script><script>'
                h += f'new TradingView.widget({{"autosize": true, "symbol": "{symbol}", "interval": "D", "theme": "light", "container_id": "tv_{symbol}", "hide_top_toolbar": true, "studies": [{{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {ma_len} }} }}] }});'
                h += '</script></div></div>'
                cards.append(h)
        except:
            continue

    results_html = "".join(cards)
    
    final_html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="bg-light py-5"><div class="container" style="max-width:800px;"><div class="text-center mb-4"><h2 class="fw-bold">🎯 美股連動監控儀表板</h2><p class="text-muted">最後更新: {today_str}</p></div>
    {results_html if results_html else '<p class="text-center">目前無符合條件股票</p>'}</div></body></html>'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("✅ index.html 成功生成")

if __name__ == "__main__":
    main()
