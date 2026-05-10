import yfinance as yf
import pandas as pd
import datetime
import os

# =================================================================
# 1. 全局配置區 (以後改這裡即可)
# =================================================================
DEFAULT_MA = 20        # 預設均線天數 (例如 20, 60)
SEARCH_RANGE = 0.01    # 預設偏離範圍 (0.01 代表 1%)

# 持股紀錄區 { "代碼": "備註內容" }
MY_PORTFOLIO = {
    "ARMK": "2026-05-01 買入",
    "V": "長期持有計畫",
}

# 財報日手動修正區 (當 API 抓不到或 N/A 時，會強制顯示此日期並判斷紅框)
MANUAL_EARNINGS = {
    "ARMK": "2026-05-12",
}

# 特殊標的自定義設定 { "代碼": (MA天數, 偏離範圍) }
# 例如 V 想看 19MA, 偏離度 1%
CUSTOM_CONFIG = {
    "V": (19, 0.01),
}

# 均線篩選觀察名單 (除了持股外，你想掃描的 190 檔名單請放在這)
TICKERS = [
    "INTU", "GOOGL", "PLUS", "AXP", "AIT", "NVO", "ACN", "AGM", "BKNG", "GAJG", 
    "ASML", "AME", "AAPL", "IBP", "PAYC", "URI", "GIB", "AEE", "XEL", "WEC", 
    "LNT", "CTAS", "CPK", "CHE", "HD", "UNH", "ADP", "APD", "ATO", "COST", 
    "MA", "V", "CW", "GD", "DPZ", "DRI", "ECL", "EME", "FIX", "GRMN", 
    "HEI", "ICFI", "IDA", "IEX", "ITW", "JKHY", "MZTI", "II", "LOW", "MCD", 
    "MCO", "MLM", "MSS", "MSCI", "HCA", "DKS", "ODFL", "OMC", "PKG", "RACE", 
    "RMD", "ROP", "ROST", "RSG", "SHW", "SNA", "SNX", "SSD", "TMQ", "TSCO", 
    "TTC", "TXRH", "WDFC", "WSO", "ZTS", "UNP", "MLR", "A_SN", "AYI", "SAIC", 
    "TJX", "MSFT", "ETN", "CMG", "FTNT", "TYL", "CPAY", "ASR", "ANET", "MIDD", 
    "LOPE", "ADUS", "CRL", "NFLX", "SAIA", "MEDP", "RBC", "MTD", "FFIV", "FIVE", 
    "EW", "BURL", "ULTA", "SAM", "ISRG", "COO", "AZO", "BJ", "VEEV", "ICLR", 
    "ADBE", "FICO", "IDXX", "QLYS", "EEFT", "TREX", "SNPS", "TTD", "CPRT", "DECK",
    "JNJ", "UNF", "AN", "ALGN", "HON", "LULU", "PH", "PWR", "CSL", "EVRG", 
    "CP", "CHD", "FBIN", "AAP", "CSGS", "ED", "DTE", "CMS", "CHKP", "CAJPY", 
    "AWK", "AWR", "ARTNA", "AGCO", "AEP", "ADM", "ADI", "ACNB", "AAON", "VZ", 
    "MDT", "GIII", "EHC", "DOV", "MMM", "CNI", "APH", "AOS", "AMCX", "ALLE", 
    "ALG", "AKAM", "AEQ", "BR", "CASY", "ARMK", "CSCO", "CL", "COLM", "BFAM", 
    "BDL", "APTV", "AMAT", "CNXN", "CMI", "CMCSA", "CLX", "CHH", "CGNX", "CDW", 
    "CDNS", "CCI", "CAKE", "CAE", "CACI", "BWA", "BOOT", "BDX", "BCPC", "BCE", 
    "BBSI", "BAH", "AVY", "AWI", "INTC", "ATR"
]

# =================================================================
# 2. 核心程式邏輯 (一般不需要修改)
# =================================================================

def main():
    today = datetime.date.today()
    print(f"正在執行掃描... 今日日期: {today}")
    
    # 下載數據，使用 group_by 確保結構穩定
    df_all = yf.download(TICKERS, period="150d", interval="1d", group_by='ticker', progress=False)
    
    passed = []
    portfolio_upper = {k.upper(): v for k, v in MY_PORTFOLIO.items()}

    for ticker in TICKERS:
        try:
            if ticker not in df_all.columns.levels[0]: continue
            df_stock = df_all[ticker].dropna()
            if df_stock.empty: continue
            
            # 取得該標的的專屬設定 (如果沒有就用預設)
            ma_days, specific_range = CUSTOM_CONFIG.get(ticker, (DEFAULT_MA, SEARCH_RANGE))
            
            close_series = df_stock['Close']
            price = close_series.iloc[-1]
            ma_val = close_series.rolling(ma_days).mean().iloc[-1]
            diff_ratio = (price / ma_val) - 1
            
            is_portfolio = ticker.upper() in portfolio_upper

            # 判斷邏輯：是持股 OR 符合偏離範圍
            if is_portfolio or abs(diff_ratio) <= specific_range:
                # 財報抓取邏輯
                e_str = MANUAL_EARNINGS.get(ticker, "N/A")
                is_near = False
                
                if e_str == "N/A":
                    try:
                        t_obj = yf.Ticker(ticker)
                        cal = t_obj.calendar
                        if cal is not None and 'Earnings Date' in cal:
                            e_dt = cal['Earnings Date'][0].date()
                            e_str = e_dt.strftime('%Y-%m-%d')
                    except: pass
                
                # 判斷是否亮紅燈 (7天內)
                if e_str != "N/A":
                    e_date_obj = datetime.datetime.strptime(e_str, '%Y-%m-%d').date()
                    delta = (e_date_obj - today).days
                    if 0 <= delta <= 7:
                        is_near = True

                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": e_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_portfolio,
                    "Note": portfolio_upper.get(ticker.upper(), "")
                })
        except Exception as e:
            print(f"處理 {ticker} 時跳過: {e}")
            continue

    # 排序：持股(0) > 非持股(1)，接著按偏離度降序
    passed.sort(key=lambda x: (0 if x['Is_Portfolio'] else 1, -x['Diff_Val']))

    # 生成 HTML
    rows_html = ""
    for x in passed:
        # 樣式決定：持股黑、預警紅、一般藍
        header_cls = "bg-dark" if x['Is_Portfolio'] else ("bg-danger" if x['Warning'] else "bg-primary")
        card_style = "border: 3px solid #dc3545;" if x['Warning'] else ""
        badge_p = f'<span class="badge bg-warning text-dark ms-2">💰 持有: {x["Note"]}</span>' if x['Is_Portfolio'] else ""
        badge_w = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""

        rows_html += f"""
        <div class="card mb-4 shadow-sm" style="{card_style}">
            <div class="card-header d-flex justify-content-between align-items-center {header_cls} text-white">
                <h5 class="mb-0">{x['Symbol']} {badge_p} {badge_w}</h5>
                <span class="badge bg-light text-dark">財報日: {x['Earnings']}</span>
            </div>
            <div class="card-body p-3">
                <p class="mb-2">
                    <b>{x['MA_Days']}MA 偏離:</b> 
                    <span class="{"text-danger" if x['Diff_Val'] < 0 else "text-success"}" style="font-weight:bold;">
                        {x['Diff_Str']}
                    </span> 
                    | <b>目前價格:</b> ${x['Price']}
                </p>
                <div id="tv_{x['Symbol']}" style="height: 400px;"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({{
                  "autosize": true,
                  "symbol": "{x['Symbol']}",
                  "interval": "D",
                  "theme": "light",
                  "style": "1",
                  "locale": "zh_TW",
                  "container_id": "tv_{x['Symbol']}",
                  "hide_top_toolbar": true,
                  "studies": [ {{ 
                      "id": "MASimple@tv-basicstudies", 
                      "inputs": {{ "length": {x['MA_Days']} }} 
                  }} ]
                }});
                </script>
            </div>
        </div>"""

    # 台北時間顯示
    now_str = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    
    html_final = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>均線回測儀表板</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f7f6; font-family: "Microsoft JhengHei", sans-serif; }}
            .container {{ max-width: 850px; }}
            .card {{ border-radius: 12px; overflow: hidden; }}
        </style>
    </head>
    <body class="py-5">
        <div class="container">
            <h2 class="text-center mb-2">🎯 持股與均線監控</h2>
            <p class="text-center text-muted small">更新時間 (台北): {now_str}</p>
            <div class="d-flex justify-content-center mb-4 gap-2">
                <span class="badge bg-dark">已持股</span>
                <span class="badge bg-danger">近期財報</span>
                <span class="badge bg-primary">均線觀察</span>
            </div>
            <hr>
            {rows_html if passed else '<div class="alert alert-warning text-center">暫無符合條件標的</div>'}
        </div>
    </body>
    </html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)

if __name__ == "__main__":
    main()
