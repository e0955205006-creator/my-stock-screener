import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# =================================================================
# 1. 核心配置 (Google 試算表連動)
# =================================================================
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
# 加入 timestamp 防止 GitHub 抓到 Google 的舊快取
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&timestamp={datetime.datetime.now().timestamp()}"

def main():
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在從雲端後台讀取設定...")
    try:
        response = session.get(SHEET_URL)
        response.encoding = 'utf-8'
        df = pd.read_csv(io.StringIO(response.text))
        # 強力清洗：去除所有標題前後空格
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"讀取試算表失敗: {e}")
        return

    # 檢查必要欄位 (Ticker)
    if 'Ticker' not in df.columns:
        print(f"錯誤：找不到 'Ticker' 欄位。目前欄位有: {list(df.columns)}")
        return
        
    tickers = df['Ticker'].dropna().astype(str).str.strip().tolist()
    if not tickers:
        print("試算表內無有效代號。")
        return

    print(f"正在抓取 {len(tickers)} 檔股票數據...")
    try:
        # 下載數據
        raw_data = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)
    except Exception as e:
        print(f"Yahoo Finance 下載失敗: {e}")
        return

    results_html = ""
    # 用於診斷的資訊
    debug_list = []

    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            if symbol == 'NAN' or not symbol: continue
            
            # 讀取設定 (Hold 判定 Y/N)
            hold_raw = str(row.get('Hold', 'N')).strip().upper()
            is_hold = 'Y' in hold_raw
            
            ma_len = int(row.get('MA', 20)) if pd.notnull(row.get('MA')) else 20
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            e_day = str(row.get('Earnings', 'N/A'))
            
            # 數據提取
            if len(tickers) == 1:
                df_stock = raw_data.dropna()
            else:
                df_stock = raw_data[symbol].dropna()
                
            if df_stock.empty: continue
            
            price = df_stock['Close'].iloc[-1]
            ma_val = df_stock['Close'].rolling(ma_len).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            # 判定顯示：持有(Y) 或 偏離 1% 內
            if is_hold or abs(diff) <= 0.01:
                bg_color = "bg-dark" if is_hold else "bg-primary"
                results_html += f"""
                <div class="card mb-4 shadow border-0">
                    <div class="card-header {bg_color} text-white d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">{symbol} {f'<span class="badge bg-warning text-dark ms-2">{note}</span>' if is_hold else ""}</h5>
                        <span class="badge bg-light text-dark">財報日: {e_day}</span>
                    </div>
                    <div class="card-body">
                        <p class="mb-2"><b>{ma_len}MA 偏離:</b> <span class="{"text-danger" if diff < 0 else "text-success"}" style="font-weight:bold;">{diff*100:.2f}%</span> | <b>目前價格:</b> ${price:.2f}</p>
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
            continue

    # 最終網頁生成
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>美股監控儀表板</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f7f6; font-family: sans-serif; }}
            .container {{ max-width: 800px; }}
            .card {{ border-radius: 12px; overflow: hidden; }}
        </style>
    </head>
    <body class="py-5">
        <div class="container">
            <div class="text-center mb-4">
                <h2 class="fw-bold">📈 美股雲端監控儀表板</h2>
                <p class="text-muted">最後更新：{today_str} (台北時間)</p>
                <div class="badge bg-secondary">連動後台：Google Sheets (Ticker/Hold/MA)</div>
            </div>
            <hr>
            {results_html if results_html else '<div class="alert alert-warning text-center">目前無符合條件股票 (請檢查試算表 Hold 是否為 Y)</div>'}
            
            <div class="mt-5 p-3 bg-white rounded shadow-sm">
                <h6 class="text-muted border-bottom pb-2">系統診斷資訊</h6>
                <small class="text-muted">
                    偵測標頭: {list(df.columns)} <br>
                    第一行 Hold 內容: {df.iloc[0].get('Hold', 'N/A')} <br>
                    總分析檔數: {len(tickers)}
                </small>
            </div>
        </div>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ index.html 成功更新！")

if __name__ == "__main__":
    main()
