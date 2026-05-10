import yfinance as yf
import pandas as pd
import datetime
import requests
import os

# =================================================================
# 1. 全局配置區
# =================================================================
DEFAULT_MA = 20
SEARCH_RANGE = 0.01

# 持股紀錄區 (代碼請大寫)
MY_PORTFOLIO = {
    "ARMK": "2026-05-01 買入",
    "V": "長期持有計畫",
}

# 財報日修正
MANUAL_EARNINGS = {
    "ARMK": "2026-05-12",
}

# 特殊均線設定
CUSTOM_CONFIG = {
    "V": (19, 0.01),
    "AAPL": (20, 0.01),
    "NVDA": (10, 0.015),
}

TICKERS = ["INTU", "GOOGL", "PLUS", "AXP", "AIT", "NVO", "ACN", "AGM", "BKNG", "GAJG", "ASML", "AME", "AAPL", "IBP", "PAYC", "URI", "GIB", "AEE", "XEL", "WEC", "LNT", "CTAS", "CPK", "CHE", "HD", "UNH", "ADP", "APD", "ATO", "COST", "MA", "V", "CW", "GD", "DPZ", "DRI", "ECL", "EME", "FIX", "GRMN", "HEI", "ICFI", "IDA", "IEX", "ITW", "JKHY", "MZTI", "II", "LOW", "MCD", "MCO", "MLM", "MSS", "MSCI", "HCA", "DKS", "ODFL", "OMC", "PKG", "RACE", "RMD", "ROP", "ROST", "RSG", "SHW", "SNA", "SNX", "SSD", "TMQ", "TSCO", "TTC", "TXRH", "WDFC", "WSO", "ZTS", "UNP", "MLR", "A_SN", "AYI", "SAIC", "TJX", "MSFT", "ETN", "CMG", "FTNT", "TYL", "CPAY", "ASR", "ANET", "MIDD", "LOPE", "ADUS", "CRL", "NFLX", "SAIA", "MEDP", "RBC", "MTD", "FFIV", "FIVE", "EW", "BURL", "ULTA", "SAM", "ISRG", "COO", "AZO", "BJ", "VEEV", "ICLR", "ADBE", "FICO", "IDXX", "QLYS", "EEFT", "TREX", "SNPS", "TTD", "CPRT", "DECK", "JNJ", "UNF", "AN", "ALGN", "HON", "LULU", "PH", "PWR", "CSL", "EVRG", "CP", "CHD", "FBIN", "AAP", "CSGS", "ED", "DTE", "CMS", "CHKP", "CAJPY", "AWK", "AWR", "ARTNA", "AGCO", "AEP", "ADM", "ADI", "ACNB", "AAON", "VZ", "MDT", "GIII", "EHC", "DOV", "MMM", "CNI", "APH", "AOS", "AMCX", "ALLE", "ALG", "AKAM", "AEQ", "BR", "CASY", "ARMK", "CSCO", "CL", "COLM", "BFAM", "BDL", "APTV", "AMAT", "CNXN", "CMI", "CMCSA", "CLX", "CHH", "CGNX", "CDW", "CDNS", "CCI", "CAKE", "CAE", "CACI", "BWA", "BOOT", "BDX", "BCPC", "BCE", "BBSI", "BAH", "AVY", "AWI", "INTC", "ATR"]

# =================================================================
# 2. 核心邏輯
# =================================================================

def main():
    today = datetime.date.today()
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    port_upper = {k.upper(): v for k, v in MY_PORTFOLIO.items()}
    conf_upper = {k.upper(): v for k, v in CUSTOM_CONFIG.items()}

    print("正在下載所有股票數據...")
    # 強制使用 group_by='ticker' 獲取穩定結構
    try:
        raw_df = yf.download(TICKERS, period="150d", interval="1d", group_by='ticker', progress=False, session=session)
    except Exception as e:
        print(f"下載失敗: {e}")
        return

    passed = []

    for ticker in TICKERS:
        try:
            t_up = ticker.upper()
            
            # 兼容不同版本的 yfinance 索引格式
            if t_up in raw_df.columns:
                df_stock = raw_df[t_up].dropna()
            elif isinstance(raw_df.columns, pd.MultiIndex) and t_up in raw_df.columns.levels[0]:
                df_stock = raw_df[t_up].dropna()
            else:
                continue
                
            if df_stock.empty or 'Close' not in df_stock.columns:
                continue
            
            # 獲取 MA 設定
            ma_days, spec_range = conf_upper.get(t_up, (DEFAULT_MA, SEARCH_RANGE))
            
            # 計算數據
            close_price = df_stock['Close'].iloc[-1]
            ma_val = df_stock['Close'].rolling(ma_days).mean().iloc[-1]
            diff_ratio = (close_price / ma_val) - 1
            
            is_hold = t_up in port_upper

            # 判定是否顯示
            if is_hold or abs(diff_ratio) <= spec_range:
                # 財報日處理
                e_str = MANUAL_EARNINGS.get(t_up, "N/A")
                is_near = False
                
                if e_str == "N/A":
                    try:
                        t_obj = yf.Ticker(t_up, session=session)
                        cal = t_obj.calendar
                        if cal is not None and 'Earnings Date' in cal:
                            e_dt = cal['Earnings Date'][0].date()
                            e_str = e_dt.strftime('%Y-%m-%d')
                    except:
                        pass
                
                if e_str != "N/A":
                    try:
                        e_date_obj = datetime.datetime.strptime(e_str, '%Y-%m-%d').date()
                        if 0 <= (e_date_obj - today).days <= 7:
                            is_near = True
                    except:
                        pass

                passed.append({
                    "Symbol": t_up,
                    "Price": round(float(close_price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": e_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_hold,
                    "Note": port_upper.get(t_up, "")
                })
        except Exception as e:
            print(f"處理 {ticker} 時出錯: {e}")
            continue

    # 排序：持股置頂 > 財報預警 > 偏離度
    passed.sort(key=lambda x: (not x['Is_Portfolio'], not x['Warning'], -x['Diff_Val']))

    # 生成網頁內容
    rows_html = ""
    for x in passed:
        header_cls = "bg-dark" if x['Is_Portfolio'] else ("bg-danger" if x['Warning'] else "bg-primary")
        card_border = "border: 3px solid #dc3545;" if x['Warning'] else ""
        badge_p = f'<span class="badge bg-warning text-dark ms-2">💰 持有: {x["Note"]}</span>' if x['Is_Portfolio'] else ""
        badge_w = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""

        rows_html += f"""
        <div class="card mb-4 shadow-sm" style="{card_border}">
            <div class="card-header d-flex justify-content-between align-items-center {header_cls} text-white">
                <h5 class="mb-0">{x['Symbol']} {badge_p} {badge_w}</h5>
                <span class="badge bg-light text-dark">財報日: {x['Earnings']}</span>
            </div>
            <div class="card-body p-3">
                <p class="mb-2"><b>{x['MA_Days']}MA 偏離:</b> <span class="{"text-danger" if x['Diff_Val'] < 0 else "text-success"}" style="font-weight:bold;">{x['Diff_Str']}</span> | <b>價格:</b> ${x['Price']}</p>
                <div id="tv_{x['Symbol']}" style="height: 400px;"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({{
                  "autosize": true, "symbol": "{x['Symbol']}", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
                  "container_id": "tv_{x['Symbol']}", "hide_top_toolbar": true,
                  "studies": [ {{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {x['MA_Days']} }} }} ]
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
        <h2 class="text-center mb-2">🎯 持股與均線監控</h2>
        <p class="text-center text-muted small">更新時間 (台北): {now_str}</p>
        <hr>{rows_html if passed else '<div class="alert alert-warning text-center">暫無符合條件標的</div>'}
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)

if __name__ == "__main__":
    main()
