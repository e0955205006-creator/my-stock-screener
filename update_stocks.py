import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 配置
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
                bg = "bg-dark" if is_hold else "bg-primary"
                d_color = "text-danger" if diff < 0 else "text-success"
                
                # --- 核心改動：完全避開大括號解析 ---
                card = '<div class="card mb-4 shadow border-0">'
                card += '<div class="card-header ' + bg + ' text-white d-flex justify-content-between">'
                card += '<span>' + symbol + ' <b>' + (note if is_hold else "") + '</b></span>'
                card += '<small>財報: ' + e_day + '</small></div>'
                card += '<div class="card-body"><p><b>' + ma_len + 'MA 偏離:</b> '
                card += '<span class="' + d_color + '" style="font-weight:bold;">' + f"{diff*100:.2f}%" + '</span> | '
                card += '<b>價格:</b> $' + f"{price:.2f}" + '</p>'
                card += '<div id="tv_' + symbol + '" style="height:400px;"></div>'
                card += '<script src="https://s3.tradingview.com/tv.js"></script>'
                card += '<script>new TradingView.widget({'
                card += '"autosize": true, "symbol": "' + symbol + '", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",'
                card += '"container_id": "tv_' + symbol + '", "hide_top_toolbar": true,'
                card += '"studies": [ { "id": "MASimple@tv-basicstudies", "inputs": { "length": ' + ma_len + ' } } ]'
                card += '});</script></div></div>'
                results_html += card
        except: continue

    # 組合最終頁面
    page = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    page += '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>'
    page += '<body class="bg-light py-5"><div class="container" style="max-width:800px;">'
    page += '<div class="text-center mb-5"><h2 class="fw-bold">🎯 美股雲端連動儀表板</h2>'
    page += '<p class="text-muted small">最後更新: ' + today_str + '</p></div>'
    page += results_html if results_html else '<p class="text-center">無符合條件股票</p>'
    page += '</div></body></html>'

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)

if __name__ == "__main__":
    main()
