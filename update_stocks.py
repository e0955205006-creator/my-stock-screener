import yfinance as yf
import pandas as pd
import datetime
import time
import requests

# --- 1. 參數與自定義區 ---
SEARCH_RANGE = 0.01  
DEFAULT_MA = 20

# 持股紀錄區 (代碼請務必大寫)
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

CUSTOM_CONFIG = {
    "V": (19, 0.01),      
    "AAPL": (20, 0.01),   
    "NVDA": (10, 0.015),  
    "LULU": (60, 0.01),
}

def fetch_earnings_date_safe(t_obj):
    """ 極度魯棒的日期抓取 """
    try:
        cal = t_obj.get_calendar()
        if cal and 'Earnings Date' in cal:
            # 取得第一個日期並強制轉為 naive date
            return cal['Earnings Date'][0].astimezone(None).replace(tzinfo=None).date()
        
        e_df = t_obj.get_earnings_dates()
        if e_df is not None and not e_df.empty:
            # 取出未來日期中最接近的一個
            future = e_df.index[e_df.index.tz_localize(None).date >= datetime.date.today()]
            if not future.empty:
                return future.min().to_pydatetime().date()
    except:
        pass
    return None

def main():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    # 確保買入名單大寫對齊
    my_portfolio_upper = {k.upper(): v for k, v in MY_PORTFOLIO.items()}
    
    # 下載數據
    data = yf.download(TICKERS, period="150d", interval="1d", progress=False, session=session)['Close']
    passed = []
    today = datetime.date.today()
    
    for ticker in TICKERS:
        try:
            if ticker not in data.columns: continue
            col = data[ticker].dropna()
            if col.empty: continue
            
            ma_days, specific_range = CUSTOM_CONFIG.get(ticker, (DEFAULT_MA, SEARCH_RANGE))
            ma_val = col.rolling(ma_days).mean().iloc[-1]
            price = col.iloc[-1]
            diff_ratio = (price / ma_val) - 1
            
            # --- 判斷邏輯 ---
            is_portfolio = ticker.upper() in my_portfolio_upper
            
            if is_portfolio or abs(diff_ratio) <= specific_range:
                t_obj = yf.Ticker(ticker, session=session)
                e_date = fetch_earnings_date_safe(t_obj)
                
                earnings_str = "N/A"
                is_near = False
                
                if e_date:
                    earnings_str = e_date.strftime('%Y-%m-%d')
                    # 只要距離 7 天內，或甚至是今天，都算預警
                    delta = (e_date - today).days
                    if 0 <= delta <= 7:
                        is_near = True

                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "Diff_Val": float(diff_ratio), 
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": earnings_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_portfolio,
                    "Note": my_portfolio_upper.get(ticker.upper(), ""),
                    "MA_Days": ma_days
                })
        except: continue

    # --- 關鍵排序：1. 持股優先 (0 為優先) 2. 財報預警優先 (0 為優先) 3. 偏離度 ---
    # 因為 Python 排序 False(0) 在 True(1) 前面，我們用 bool 取反來達成目的
    passed.sort(key=lambda x: (not x['Is_Portfolio'], not x['Warning'], -x['Diff_Val']))
    
    rows = ""
    for x in passed:
        # 決定顏色 (持股黑標題，財報週紅標題，其餘藍)
        if x['Is_Portfolio']:
            header_color = "bg-dark"
            tag = f'<span class="badge bg-warning text-dark ms-2">💰 持有: {x["Note"]}</span>'
        elif x['Warning']:
            header_color = "bg-danger"
            tag = ""
        else:
            header_color = "bg-primary"
            tag = ""

        warn_badge = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""
        badge_color = "bg-success" if x['Diff_Val'] >= 0 else "bg-danger"

        rows += f"""
        <div class="card mb-4 shadow border-0" style="{'border: 2px solid #dc3545;' if x['Warning'] else ''}">
            <div class="card-header d-flex justify-content-between align-items-center {header_color} text-white">
                <h5 class="mb-0">{x['Symbol']} {tag} {warn_badge}</h5>
                <span class="badge bg-light text-dark">下次財報: {x['Earnings']}</span>
            </div>
            <div class="card-body p-3">
                <div class="d-flex justify-content-between mb-2">
                    <span><b>{x['MA_Days']}MA 距離:</b> <span class="badge {badge_color}">{x['Diff_Str']}</span></span>
                    <span><b>價格:</b> ${x['Price']}</span>
                </div>
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

    # 生成 HTML (略，同之前邏輯)
    # ...
    # 此處請接續原本將 rows 填入 html_content 並寫入 index.html 的代碼

if __name__ == "__main__":
    main()
