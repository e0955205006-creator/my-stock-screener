import yfinance as yf
import pandas as pd
import datetime
import time
import requests

# --- 1. 參數與自定義區 ---
SEARCH_RANGE = 0.01  
DEFAULT_MA = 20

# 持股紀錄區 (代碼必須與下面 TICKERS 列表完全一致)
MY_PORTFOLIO = {
    "ARMK": "2026-05-01 買入",
    "V": "長期持有計畫",
}

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

def fetch_earnings_date_safe(t_obj, today_date):
    try:
        cal = t_obj.get_calendar()
        if cal and isinstance(cal, dict) and 'Earnings Date' in cal:
            d_list = cal['Earnings Date']
            if d_list and len(d_list) > 0:
                # 轉為本地日期並移除時區
                return d_list[0].astimezone(None).date()
        
        e_df = t_obj.get_earnings_dates()
        if e_df is not None and not e_df.empty:
            # 確保索引是 datetime 格式
            e_df.index = pd.to_datetime(e_df.index)
            future = e_df.index[e_df.index.date >= today_date]
            if not future.empty:
                return future.min().date()
    except:
        pass
    return None

def main():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    # 修改：改為循環下載單一股票資料，確保穩定度
    passed = []
    today_dt = datetime.datetime.now()
    today_date = today_dt.date()
    
    print(f"--- 啟動掃描: {today_date} ---")

    for ticker in TICKERS:
        try:
            # 改為獲取單一 Ticker 對象
            t_obj = yf.Ticker(ticker, session=session)
            hist = t_obj.history(period="150d")
            if hist.empty or len(hist) < DEFAULT_MA: continue
            
            price = hist['Close'].iloc[-1]
            ma_days, specific_range = CUSTOM_CONFIG.get(ticker, (DEFAULT_MA, SEARCH_RANGE))
            ma_val = hist['Close'].rolling(ma_days).mean().iloc[-1]
            diff_ratio = (price / ma_val) - 1
            
            # 核心判斷：持股優先
            is_portfolio = ticker.upper() in [k.upper() for k in MY_PORTFOLIO.keys()]
            
            if is_portfolio or abs(diff_ratio) <= specific_range:
                e_date = fetch_earnings_date_safe(t_obj, today_date)
                
                earnings_str = "N/A"
                is_near = False
                
                if e_date:
                    earnings_str = e_date.strftime('%Y-%m-%d')
                    delta = (e_date - today_date).days
                    if 0 <= delta <= 7:
                        is_near = True
                
                # Debug 印出 ARMK 狀態
                if ticker == "ARMK":
                    print(f"[DEBUG] ARMK: 持股={is_portfolio}, 偏離={diff_ratio:.4f}, 財報={earnings_str}, 預警={is_near}")

                passed.append({
                    "Symbol": ticker,
                    "Name": ticker, # 簡化名稱獲取避免報錯
                    "Price": round(float(price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio), 
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": earnings_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_portfolio,
                    "Note": MY_PORTFOLIO.get(ticker, "")
                })
                time.sleep(0.5)
        except Exception as e:
            print(f"跳過 {ticker}: {e}")
            continue

    # --- 關鍵排序：1.持股置頂 2.偏離度由大到小 ---
    passed.sort(key=lambda x: (not x['Is_Portfolio'], -x['Diff_Val']))
    
    rows = ""
    for x in passed:
        # 決定顏色邏輯：持股優先顯示黑色，否則財報週顯示紅色，否則藍色
        if x['Is_Portfolio']:
            header_color = "bg-dark"
            p_tag = f'<span class="badge bg-warning text-dark ms-2">💰 持有中: {x["Note"]}</span>'
        elif x['Warning']:
            header_color = "bg-danger"
            p_tag = ""
        else:
            header_color = "bg-primary"
            p_tag = ""
            
        warn_tag = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""
        badge_color = "bg-success" if x['Diff_Val'] >= 0 else "bg-danger"
        bg_style = "background-color: #fff5f5;" if x['Warning'] else ""

        rows += f"""
        <div class="card mb-4 shadow border-0" style="{bg_style}">
            <div class="card-header d-flex justify-content-between align-items-center {header_color} text-white">
                <h5 class="mb-0">{x['Symbol']} {p_tag} {warn_tag}</h5>
                <span class="badge bg-light text-dark">下次財報: {x['Earnings']}</span>
            </div>
            <div class="card-body p-3">
                <div class="d-flex justify-content-between mb-2">
                    <span><b>{x['MA_Days']}MA 偏離距離:</b> <span class="badge {badge_color}">{x['Diff_Str']}</span></span>
                    <span><b>目前股價:</b> ${x['Price']}</span>
                </div>
                <div id="tv_{x['Symbol']}" style="height: 400px;"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({{
                  "autosize": true, "symbol": "{x['Symbol']}", "interval": "D", "timezone": "Etc/UTC",
                  "theme": "light", "style": "1", "locale": "zh_TW",
                  "container_id": "tv_{x['Symbol']}", "hide_top_toolbar": true,
                  "studies": [ {{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {x['MA_Days']} }} }} ]
                }});
                </script>
            </div>
        </div>"""

    # ... 後續生成 HTML 檔案邏輯保持不變 ...
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head><meta charset="UTF-8"><title>均線回測</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="py-5"><div class="container">
        <h2 class="text-center mb-4">🎯 持股追蹤與均線篩選</h2>
        <div class="text-center mb-4">
            <span class="badge bg-dark">黑色：已持股</span>
            <span class="badge bg-danger">紅色：近期財報</span>
            <span class="badge bg-primary">藍色：符合均線標的</span>
        </div>
        {rows if passed else '<p class="text-center">暫無符合條件標的</p>'}
    </div></body></html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
