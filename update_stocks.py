import yfinance as yf
import pandas as pd
import datetime
import os

# --- 配置區 ---
SEARCH_RANGE = 0.01
DEFAULT_MA = 20

# 持股紀錄區
MY_PORTFOLIO = {
    "ARMK": "2026-05-01 買入",
    "V": "長期持有計畫",
}

# 財報日手動修正區 (當 API 抓不到 N/A 時，會自動引用這裡的日期)
MANUAL_EARNINGS = {
    "ARMK": "2026-05-12",
    "NVDA": "2026-05-20", # 舉例
}

TICKERS = ["INTU", "GOOGL", "PLUS", "AXP", "AIT", "NVO", "ACN", "AGM", "BKNG", "GAJG", "ASML", "AME", "AAPL", "IBP", "PAYC", "URI", "GIB", "AEE", "XEL", "WEC", "LNT", "CTAS", "CPK", "CHE", "HD", "UNH", "ADP", "APD", "ATO", "COST", "MA", "V", "CW", "GD", "DPZ", "DRI", "ECL", "EME", "FIX", "GRMN", "HEI", "ICFI", "IDA", "IEX", "ITW", "JKHY", "MZTI", "II", "LOW", "MCD", "MCO", "MLM", "MSS", "MSCI", "HCA", "DKS", "ODFL", "OMC", "PKG", "RACE", "RMD", "ROP", "ROST", "RSG", "SHW", "SNA", "SNX", "SSD", "TMQ", "TSCO", "TTC", "TXRH", "WDFC", "WSO", "ZTS", "UNP", "MLR", "A_SN", "AYI", "SAIC", "TJX", "MSFT", "ETN", "CMG", "FTNT", "TYL", "CPAY", "ASR", "ANET", "MIDD", "LOPE", "ADUS", "CRL", "NFLX", "SAIA", "MEDP", "RBC", "MTD", "FFIV", "FIVE", "EW", "BURL", "ULTA", "SAM", "ISRG", "COO", "AZO", "BJ", "VEEV", "ICLR", "ADBE", "FICO", "IDXX", "QLYS", "EEFT", "TREX", "SNPS", "TTD", "CPRT", "DECK", "JNJ", "UNF", "AN", "ALGN", "HON", "LULU", "PH", "PWR", "CSL", "EVRG", "CP", "CHD", "FBIN", "AAP", "CSGS", "ED", "DTE", "CMS", "CHKP", "CAJPY", "AWK", "AWR", "ARTNA", "AGCO", "AEP", "ADM", "ADI", "ACNB", "AAON", "VZ", "MDT", "GIII", "EHC", "DOV", "MMM", "CNI", "APH", "AOS", "AMCX", "ALLE", "ALG", "AKAM", "AEQ", "BR", "CASY", "ARMK", "CSCO", "CL", "COLM", "BFAM", "BDL", "APTV", "AMAT", "CNXN", "CMI", "CMCSA", "CLX", "CHH", "CGNX", "CDW", "CDNS", "CCI", "CAKE", "CAE", "CACI", "BWA", "BOOT", "BDX", "BCPC", "BCE", "BBSI", "BAH", "AVY", "AWI", "INTC", "ATR"]

def main():
    today = datetime.date.today()
    print("正在下載數據...")
    df_all = yf.download(TICKERS, period="100d", interval="1d", group_by='ticker', progress=False)
    
    passed = []
    portfolio_upper = {k.upper(): v for k, v in MY_PORTFOLIO.items()}

    for ticker in TICKERS:
        try:
            if ticker not in df_all.columns.levels[0]: continue
            df_stock = df_all[ticker].dropna()
            if df_stock.empty: continue
            
            close_series = df_stock['Close']
            price = close_series.iloc[-1]
            ma_val = close_series.rolling(DEFAULT_MA).mean().iloc[-1]
            diff_ratio = (price / ma_val) - 1
            is_portfolio = ticker.upper() in portfolio_upper

            if is_portfolio or abs(diff_ratio) <= SEARCH_RANGE:
                # --- 強化版財報抓取 ---
                e_str = MANUAL_EARNINGS.get(ticker, "N/A") # 優先用手動輸入的
                is_near = False
                
                # 如果手動沒輸入，才去抓 API
                if e_str == "N/A":
                    try:
                        t_obj = yf.Ticker(ticker)
                        cal = t_obj.calendar
                        if cal is not None and 'Earnings Date' in cal:
                            e_dt = cal['Earnings Date'][0].date()
                            e_str = e_dt.strftime('%Y-%m-%d')
                    except: pass
                
                # 判斷是否要亮紅燈 (Warning)
                if e_str != "N/A":
                    e_date_obj = datetime.datetime.strptime(e_str, '%Y-%m-%d').date()
                    if 0 <= (e_date_obj - today).days <= 7:
                        is_near = True

                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": e_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_portfolio,
                    "Note": portfolio_upper.get(ticker.upper(), "")
                })
        except: continue

    # 排序：持股(0) > 非持股(1)
    passed.sort(key=lambda x: (0 if x['Is_Portfolio'] else 1, -x['Diff_Val']))

    # 生成 HTML
    rows_html = ""
    for x in passed:
        header_cls = "bg-dark" if x['Is_Portfolio'] else ("bg-danger" if x['Warning'] else "bg-primary")
        # 財報預警卡片：增加紅色邊框
        card_style = "border: 3px solid #dc3545;" if x['Warning'] else ""
        badge_p = f'<span class="badge bg-warning text-dark ms-2">💰 持有: {x["Note"]}</span>' if x['Is_Portfolio'] else ""
        badge_w = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""

        rows_html += f"""
        <div class="card mb-4 shadow-sm" style="{card_style}">
            <div class="card-header d-flex justify-content-between align-items-center {header_cls} text-white">
                <h5 class="mb-0">{x['Symbol']} {badge_p} {badge_w}</h5>
                <span class="badge bg-light text-dark">財報日: {x['Earnings']}</span>
            </div>
            <div class="card-body">
                <p><b>20MA 偏離:</b> <span class="{"text-danger" if x['Diff_Val'] < 0 else "text-success"}">{x['Diff_Str']}</span> | <b>價格:</b> ${x['Price']}</p>
                <div id="tv_{x['Symbol']}" style="height: 400px;"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({{
                  "autosize": true, "symbol": "{x['Symbol']}", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
                  "container_id": "tv_{x['Symbol']}", "hide_top_toolbar": true,
                  "studies": [ {{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": 20 }} }} ]
                }});
                </script>
            </div>
        </div>"""

    now_str = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    html_final = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head><meta charset="UTF-8"><title>監控報告</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="bg-light py-5"><div class="container" style="max-width: 800px;">
        <h2 class="text-center mb-4">🎯 持股與均線監控</h2>
        <p class="text-center text-muted small">更新時間 (台北): {now_str}</p>
        <div class="d-flex justify-content-center mb-4 gap-2">
            <span class="badge bg-dark">已持股</span> <span class="badge bg-danger">近期財報</span> <span class="badge bg-primary">均線標的</span>
        </div>
        <hr>{rows_html if passed else '<div class="alert alert-warning text-center">暫無符合條件標的</div>'}
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)

if __name__ == "__main__":
    main()
