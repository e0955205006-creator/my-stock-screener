import yfinance as yf
import pandas as pd
import datetime
import os

# --- 1. 參數設定 ---
SEARCH_RANGE = 0.01  
CUSTOM_CONFIG = {
    "V": (19, 0.01),      
    "AAPL": (20, 0.01),   
    "NVDA": (10, 0.015),  
    "LULU": (60, 0.01),
}
DEFAULT_MA = 20

# 190 檔名單 (已縮減，請確認你的 TICKERS 列表完整)
TICKERS = ["INTU", "GOOGL", "PLUS", "AXP", "AIT", "NVO", "ACN", "AGM", "BKNG", "GAJG", "ASML", "AME", "AAPL", "IBP", "PAYC", "URI", "GIB", "AEE", "XEL", "WEC", "LNT", "CTAS", "CPK", "CHE", "HD", "UNH", "ADP", "APD", "ATO", "COST", "MA", "V", "CW", "GD", "DPZ", "DRI", "ECL", "EME", "FIX", "GRMN", "HEI", "ICFI", "IDA", "IEX", "ITW", "JKHY", "MZTI", "II", "LOW", "MCD", "MCO", "MLM", "MSS", "MSCI", "HCA", "DKS", "ODFL", "OMC", "PKG", "RACE", "RMD", "ROP", "ROST", "RSG", "SHW", "SNA", "SNX", "SSD", "TMQ", "TSCO", "TTC", "TXRH", "WDFC", "WSO", "ZTS", "UNP", "MLR", "A_SN", "AYI", "SAIC", "TJX", "MSFT", "ETN", "CMG", "FTNT", "TYL", "CPAY", "ASR", "ANET", "MIDD", "LOPE", "ADUS", "CRL", "NFLX", "SAIA", "MEDP", "RBC", "MTD", "FFIV", "FIVE", "EW", "BURL", "ULTA", "SAM", "ISRG", "COO", "AZO", "BJ", "VEEV", "ICLR", "ADBE", "FICO", "IDXX", "QLYS", "EEFT", "TREX", "SNPS", "TTD", "CPRT", "DECK", "JNJ", "UNF", "AN", "ALGN", "HON", "LULU", "PH", "PWR", "CSL", "EVRG", "CP", "CHD", "FBIN", "AAP", "CSGS", "ED", "DTE", "CMS", "CHKP", "CAJPY", "AWK", "AWR", "ARTNA", "AGCO", "AEP", "ADM", "ADI", "ACNB", "AAON", "VZ", "MDT", "GIII", "EHC", "DOV", "MMM", "CNI", "APH", "AOS", "AMCX", "ALLE", "ALG", "AKAM", "AEQ", "BR", "CASY", "ARMK", "CSCO", "CL", "COLM", "BFAM", "BDL", "APTV", "AMAT", "CNXN", "CMI", "CMCSA", "CLX", "CHH", "CGNX", "CDW", "CDNS", "CCI", "CAKE", "CAE", "CACI", "BWA", "BOOT", "BDX", "BCPC", "BCE", "BBSI", "BAH", "AVY", "AWI", "INTC", "ATR"]

def main():
    data = yf.download(TICKERS, period="100d", interval="1d", progress=False)['Close']
    passed = []
    today = datetime.datetime.now()
    
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
                t_obj = yf.Ticker(ticker)
                
                # 獲取財報日期
                earnings_date = "N/A"
                is_near_earnings = False
                try:
                    cal = t_obj.calendar
                    if 'Earnings Date' in cal and cal['Earnings Date']:
                        e_date = cal['Earnings Date'][0] # 取得第一個預估日
                        earnings_date = e_date.strftime('%Y-%m-%d')
                        # 檢查是否在未來 7 天內
                        if 0 <= (e_date.replace(tzinfo=None) - today).days <= 7:
                            is_near_earnings = True
                except: pass

                passed.append({
                    "Symbol": ticker,
                    "Name": t_obj.info.get('shortName', ticker),
                    "Price": round(float(price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": abs(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": earnings_date,
                    "Warning": is_near_earnings
                })
        except: continue

    passed = sorted(passed, key=lambda x: x['Diff_Val'])
    now = today.strftime("%Y-%m-%d %H:%M:%S")
    
    rows = ""
    for x in passed:
        # 如果接近財報日，使用警告色背景 (Bootstrap table-danger)
        bg_style = "background-color: #fff5f5;" if x['Warning'] else ""
        warning_tag = '<span class="badge bg-danger ms-2">⚠️ 財報預警</span>' if x['Warning'] else ""
        
        rows += f"""
        <div class="card mb-4 shadow border-0" style="{bg_style}">
            <div class="card-header d-flex justify-content-between align-items-center {'bg-danger text-white' if x['Warning'] else 'bg-primary text-white'}">
                <h5 class="mb-0">{x['Name']} ({x['Symbol']}) {warning_tag}</h5>
                <span class="badge {'bg-light text-danger' if x['Warning'] else 'bg-light text-dark'}">
                    下次財報: {x['Earnings']}
                </span>
            </div>
            <div class="card-body p-3">
                <div class="d-flex justify-content-between mb-2">
                    <span><b>{x['MA_Days']}MA 偏離:</b> {x['Diff_Str']}</span>
                    <span><b>目前股價:</b> ${x['Price']}</span>
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

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>均線回測+財報預警</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body {{ background-color: #f4f7f6; }} .container {{ max-width: 800px; }}</style>
    </head>
    <body class="py-5"><div class="container">
        <h2 class="text-center mb-4">🎯 均線回測標的 (含財報預警)</h2>
        <div class="text-center mb-4">
            <span class="badge bg-danger">紅色：7天內公佈財報</span>
            <span class="badge bg-primary">藍色：正常觀察</span>
        </div>
        {rows if passed else '<div class="text-center p-5">目前無標的在 1% 範圍內</div>'}
    </div></body></html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
