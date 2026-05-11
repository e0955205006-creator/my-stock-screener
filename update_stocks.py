import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# =================================================================
# 1. 配置區 (這部分程式會自動讀取你的 Google 試算表)
# =================================================================
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
DEFAULT_MA = 20
SEARCH_RANGE = 0.01

def main():
    today = datetime.date.today()
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在從雲端後台讀取設定...")
    try:
        response = session.get(SHEET_URL)
        response.encoding = 'utf-8'
        config_df = pd.read_csv(io.StringIO(response.text))
        config_df.columns = config_df.columns.str.strip()
    except Exception as e:
        print(f"讀取失敗: {e}")
        return

    # 清洗代號清單
    tickers = config_df['股票代號'].dropna().astype(str).str.strip().tolist()
    if not tickers:
        print("試算表內無代號，任務結束。")
        return

    print(f"正在分析 {len(tickers)} 檔股票...")
    # 下載數據
    raw_df = yf.download(tickers, period="150d", group_by='ticker', progress=False, session=session)

    passed = []
    for index, row in config_df.iterrows():
        ticker = str(row['股票代號']).strip().upper()
        if not ticker or ticker == 'NAN': continue
        
        try:
            # 數據提取
            if len(tickers) == 1:
                df_stock = raw_df.dropna()
            else:
                df_stock = raw_df[ticker].dropna()
                
            if df_stock.empty: continue
            
            # 讀取試算表中的個人化設定
            ma_days = int(row.get('MA設定', DEFAULT_MA))
            is_hold = str(row.get('是否持股', '')).strip() == "是"
            note = str(row.get('備註', '')) if pd.notnull(row.get('備註')) else ""
            manual_e = str(row.get('手動財報日', '')).strip()
            manual_e = manual_e if manual_e not in ['nan', ''] else "N/A"

            # 計算當前指標
            close_price = df_stock['Close'].iloc[-1]
            ma_val = df_stock['Close'].rolling(ma_days).mean().iloc[-1]
            diff_ratio = (close_price / ma_val) - 1
            
            # 判定是否要在網頁顯示
            if is_hold or abs(diff_ratio) <= SEARCH_RANGE:
                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(close_price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": manual_e,
                    "Is_Portfolio": is_hold,
                    "Note": note
                })
        except:
            continue

    # 排序：持有股票置頂，其餘按偏離度排序
    passed.sort(key=lambda x: (not x['Is_Portfolio'], -x['Diff_Val']))

    # 生成網頁 HTML 代碼
    rows_html = ""
    for x in passed:
        header_cls = "bg-dark" if x['Is_Portfolio'] else "bg-primary"
        badge_p = f'<span class="badge bg-warning text-dark ms-2">💰 持有中: {x["Note"]}</span>' if x['Is_Portfolio'] else ""

        rows_html += f"""
        <div class="card mb-4 shadow-sm">
            <div class="card-header d-flex justify-content-between align-items-center {header_cls} text-white">
                <h5 class="mb-0">{x['Symbol']} {badge_p}</h5>
                <span class="badge bg-light text-dark text-muted">手動財報日: {x['Earnings']}</span>
            </div>
            <div class="card-body p-3">
                <p class="mb-2"><b>{x['MA_Days']}MA 偏離:</b> <span class="{"text-danger" if x['Diff_Val'] < 0 else "text-success"}" style="font-weight:bold;">{x['Diff_Str']}</span> | <b>目前價格:</b> ${x['Price']}</p>
                <div id="tv_{x['Symbol']}" style="height: 400px;"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({{
                  "autosize": true, "symbol": "{x['Symbol']}", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
                  "container_id": "tv_{x['Symbol']}", "hide_top_toolbar": true, "save_image": false,
                  "studies": [ {{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {x['MA_Days']} }} }} ]
                }});
                </script>
            </div>
        </div>"""

    # 台北時間標註
    now_str = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    
    html_final = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>美股監控儀表板</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body {{ background-color: #f8f9fa; }} .container {{ max-width: 850px; }}</style>
    </head>
    <body class="py-5">
        <div class="container">
            <h2 class="text-center mb-1">📈 雲端連動監控系統</h2>
            <p class="text-center text-muted small">上次更新: {now_str} (台北時間)</p>
            <div class="alert alert-info py-2 text-center small">此頁面資料 100% 同步自你的 Google 試算表後台</div>
            <hr>
            {rows_html if passed else '<div class="alert alert-warning text-center">目前沒有符合偏離度 1% 內或設定持有的股票。</div>'}
        </div>
    </body>
    </html>"""

    # 寫入 index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)
    print("✅ index.html 已成功更新！")

if __name__ == "__main__":
    main()
