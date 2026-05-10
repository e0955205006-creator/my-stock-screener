import yfinance as yf
import pandas as pd
import datetime
import os

# --- 1. 配置區 ---
SEARCH_RANGE = 0.01
DEFAULT_MA = 20

# 持股紀錄區 (代碼請務必大寫)
MY_PORTFOLIO = {
    "ARMK": "2026-05-01 買入",
    "V": "長期持有計畫",
}

# 這是你要掃描的 190 檔名單 (簡化顯示)
TICKERS = ["INTU", "GOOGL", "PLUS", "AXP", "AIT", "NVO", "ACN", "AGM", "BKNG", "GAJG", "ASML", "AME", "AAPL", "IBP", "PAYC", "URI", "GIB", "AEE", "XEL", "WEC", "LNT", "CTAS", "CPK", "CHE", "HD", "UNH", "ADP", "APD", "ATO", "COST", "MA", "V", "CW", "GD", "DPZ", "DRI", "ECL", "EME", "FIX", "GRMN", "HEI", "ICFI", "IDA", "IEX", "ITW", "JKHY", "MZTI", "II", "LOW", "MCD", "MCO", "MLM", "MSS", "MSCI", "HCA", "DKS", "ODFL", "OMC", "PKG", "RACE", "RMD", "ROP", "ROST", "RSG", "SHW", "SNA", "SNX", "SSD", "TMQ", "TSCO", "TTC", "TXRH", "WDFC", "WSO", "ZTS", "UNP", "MLR", "A_SN", "AYI", "SAIC", "TJX", "MSFT", "ETN", "CMG", "FTNT", "TYL", "CPAY", "ASR", "ANET", "MIDD", "LOPE", "ADUS", "CRL", "NFLX", "SAIA", "MEDP", "RBC", "MTD", "FFIV", "FIVE", "EW", "BURL", "ULTA", "SAM", "ISRG", "COO", "AZO", "BJ", "VEEV", "ICLR", "ADBE", "FICO", "IDXX", "QLYS", "EEFT", "TREX", "SNPS", "TTD", "CPRT", "DECK", "JNJ", "UNF", "AN", "ALGN", "HON", "LULU", "PH", "PWR", "CSL", "EVRG", "CP", "CHD", "FBIN", "AAP", "CSGS", "ED", "DTE", "CMS", "CHKP", "CAJPY", "AWK", "AWR", "ARTNA", "AGCO", "AEP", "ADM", "ADI", "ACNB", "AAON", "VZ", "MDT", "GIII", "EHC", "DOV", "MMM", "CNI", "APH", "AOS", "AMCX", "ALLE", "ALG", "AKAM", "AEQ", "BR", "CASY", "ARMK", "CSCO", "CL", "COLM", "BFAM", "BDL", "APTV", "AMAT", "CNXN", "CMI", "CMCSA", "CLX", "CHH", "CGNX", "CDW", "CDNS", "CCI", "CAKE", "CAE", "CACI", "BWA", "BOOT", "BDX", "BCPC", "BCE", "BBSI", "BAH", "AVY", "AWI", "INTC", "ATR"]

def main():
    # 下載數據
    raw_data = yf.download(TICKERS, period="100d", interval="1d", progress=False)
    # 處理 yfinance 多層索引問題
    if isinstance(raw_data.columns, pd.MultiIndex):
        close_data = raw_data['Close']
    else:
        close_data = raw_data

    passed = []
    today = datetime.date.today()
    my_portfolio_keys = [k.upper() for k in MY_PORTFOLIO.keys()]

    for ticker in TICKERS:
        try:
            if ticker not in close_data.columns: continue
            series = close_data[ticker].dropna()
            if series.empty: continue

            price = series.iloc[-1]
            ma_val = series.rolling(DEFAULT_MA).mean().iloc[-1]
            diff_ratio = (price / ma_val) - 1
            
            is_portfolio = ticker.upper() in my_portfolio_keys

            # 篩選條件：持有中 OR 進入 1% 範圍
            if is_portfolio or abs(diff_ratio) <= SEARCH_RANGE:
                t_obj = yf.Ticker(ticker)
                
                # 財報抓取 (加入多層 Try 確保不崩潰)
                e_str = "N/A"
                is_near = False
                try:
                    cal = t_obj.calendar
                    if cal is not None and 'Earnings Date' in cal:
                        e_dt = cal['Earnings Date'][0].date()
                        e_str = e_dt.strftime('%Y-%m-%d')
                        if 0 <= (e_dt - today).days <= 7:
                            is_near = True
                except:
                    pass

                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": e_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_portfolio,
                    "Note": MY_PORTFOLIO.get(ticker, "")
                })
        except:
            continue

    # --- 關鍵排序：持股置頂(0) > 非持股(1)，接著按偏離度降序 ---
    passed.sort(key=lambda x: (0 if x['Is_Portfolio'] else 1, -x['Diff_Val']))

    # 生成 HTML
    rows_html = ""
    for x in passed:
        # 樣式決定
        header_color = "bg-dark" if x['Is_Portfolio'] else ("bg-danger" if x['Warning'] else "bg-primary")
        card_border = "border: 3px solid #dc3545;" if x['Warning'] else ""
        p_tag = f'<span class="badge bg-warning text-dark ms-2">💰 持有: {x["Note"]}</span>' if x['Is_Portfolio'] else ""
        w_tag = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""

        rows_html += f"""
        <div class="card mb-4 shadow-sm" style="{card_border}">
            <div class="card-header d-flex justify-content-between align-items-center {header_color} text-white">
                <h5 class="mb-0">{x['Symbol']} {p_tag} {w_tag}</h5>
                <span class="badge bg-light text-dark">財報日: {x['Earnings']}</span>
            </div>
            <div class="card-body">
                <p class="mb-2"><b>20MA 偏離:</b> {x['Diff_Str']} | <b>價格:</b> ${x['Price']}</p>
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

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_final = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head><meta charset="UTF-8"><title>美股監控</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="bg-light py-5"><div class="container" style="max-width: 800px;">
        <h2 class="text-center mb-4">📈 持股追蹤與均線篩選</h2>
        <p class="text-center text-muted small">更新時間 (UTC): {now_str}</p>
        <hr>{rows_html if passed else '<p class="text-center">查無符合條件標的</p>'}
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)

if __name__ == "__main__":
    main()
