import yfinance as yf
import pandas as pd
import datetime
import time
import requests

# --- 1. 參數與自定義區 ---
SEARCH_RANGE = 0.01  
DEFAULT_MA = 20

CUSTOM_CONFIG = {
    "V": (19, 0.01),      
    "AAPL": (20, 0.01),   
    "NVDA": (10, 0.015),  
    "LULU": (60, 0.01),
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

def get_clean_name(ticker_obj, symbol):
    try:
        # 優先用快速 info 抓取，失敗則回傳代碼
        name = ticker_obj.info.get('shortName', symbol)
        for suffix in [" Inc.", " Corp.", " Corporation", " Ltd.", " plc"]:
            name = name.replace(suffix, "")
        return name
    except:
        return symbol

def fetch_earnings_date(t_obj, today_date):
    """ 強化的財報抓取函數，包含重試機制 """
    for _ in range(3):  # 最多重試 3 次
        try:
            # 優先嘗試 get_calendar
            cal = t_obj.get_calendar()
            if cal and 'Earnings Date' in cal:
                e_dt = cal['Earnings Date'][0].replace(tzinfo=None)
                return e_dt.date()
            
            # 次要嘗試 get_earnings_dates
            e_df = t_obj.get_earnings_dates()
            if e_df is not None and not e_df.empty:
                e_df.index = e_df.index.tz_localize(None)
                future = e_df.index[e_df.index.date >= today_date]
                if not future.empty:
                    return future.min().date()
        except:
            time.sleep(1) # 失敗就等一秒再試
            continue
    return None

def main():
    # 建立偽裝 Session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    data = yf.download(TICKERS, period="100d", interval="1d", progress=False, session=session)['Close']
    passed = []
    today = datetime.datetime.now()
    today_date = today.date()
    
    for ticker in TICKERS:
        try:
            col = data[ticker].dropna()
            if col.empty: continue
            
            ma_days, specific_range = CUSTOM_CONFIG.get(ticker, (DEFAULT_MA, SEARCH_RANGE))
            if len(col) < ma_days: continue
            
            ma_val = col.rolling(ma_days).mean().iloc[-1]
            price = col.iloc[-1]
            diff_ratio = (price / ma_val) - 1
            
            if abs(diff_ratio) <= specific_range:
                t_obj = yf.Ticker(ticker, session=session)
                
                # 使用強化函數抓取日期
                e_date = fetch_earnings_date(t_obj, today_date)
                
                earnings_str = "N/A"
                is_near = False
                
                if e_date:
                    earnings_str = e_date.strftime('%Y-%m-%d')
                    delta = (e_date - today_date).days
                    if 0 <= delta <= 7:
                        is_near = True

                passed.append({
                    "Symbol": ticker,
                    "Name": get_clean_name(t_obj, ticker),
                    "Price": round(float(price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio), 
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": earnings_str,
                    "Warning": is_near
                })
                time.sleep(0.5) # 增加間隔防止被封 IP
                
        except: continue

    passed.sort(key=lambda x: x['Diff_Val'], reverse=True)
    
    now = today.strftime("%Y-%m-%d %H:%M:%S")
    rows = ""
    for x in passed:
        badge_color = "bg-success" if x['Diff_Val'] >= 0 else "bg-danger"
        header_color = "bg-danger" if x['Warning'] else "bg-primary"
        bg_style = "background-color: #fff5f5;" if x['Warning'] else ""
        warning_tag = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""
        
        rows += f"""
        <div class="card mb-4 shadow border-0" style="{bg_style}">
            <div class="card-header d-flex justify-content-between align-items-center {header_color} text-white">
                <h5 class="mb-0">{x['Name']} ({x['Symbol']}){warning_tag}</h5>
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

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>均線回測報告</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f7f6; }}
            .container {{ max-width: 850px; }}
        </style>
    </head>
    <body class="py-5">
        <div class="container">
            <h2 class="text-center mb-2">🎯 精選均線回測標的</h2>
            <p class="text-center text-muted small">依偏離度排序 (+0.99% → -0.99%)<br>更新時間: {now} (UTC)</p>
            <hr>
            {rows if passed else '<div class="alert alert-info text-center">目前無標的在均線 1% 範圍內</div>'}
        </div>
    </body>
    </html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
