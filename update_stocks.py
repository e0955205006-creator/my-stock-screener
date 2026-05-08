import yfinance as yf
import pandas as pd
import datetime

# --- 1. 參數自定義區 ---
# 預設：搜尋離 MA 只有 1% 距離的公司
SEARCH_RANGE = 0.01  # 0.01 代表正負 1% 以內

# 格式: "代號": (MA天數, 專屬搜尋範圍)
CUSTOM_CONFIG = {
    "AAPL": (20, 0.01),   
    "NVDA": (10, 0.015), # 波動大，稍微放寬到 1.5%
    "LULU": (60, 0.01),
}

DEFAULT_MA = 20

# --- 2. 完整公司名單 (190+ 檔) ---
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

def main():
    # 抓取數據
    data = yf.download(TICKERS, period="100d", interval="1d", progress=False)['Close']
    passed = []
    
    for ticker in TICKERS:
        try:
            col = data[ticker].dropna()
            if col.empty: continue
            
            ma_days, specific_range = CUSTOM_CONFIG.get(ticker, (DEFAULT_MA, SEARCH_RANGE))
            if len(col) < ma_days: continue
            
            ma_val = col.rolling(ma_days).mean().iloc[-1]
            price = col.iloc[-1]
            
            # 計算偏離度
            diff_ratio = (price / ma_val) - 1
            
            # 核心邏輯：絕對值小於門檻 (例如股價在 99% ~ 101% 之間)
            if abs(diff_ratio) <= specific_range:
                diff_pct = diff_ratio * 100
                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "MA_Type": f"{ma_days}MA",
                    "MA_Val": round(float(ma_val), 2),
                    "Diff_Val": diff_pct,
                    "Diff_Str": f"{diff_pct:+.2f}%"
                })
        except:
            continue

    # 排序：按照離均線「最近」的排在最前面 (絕對值排序)
    passed = sorted(passed, key=lambda x: abs(x['Diff_Val']))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- HTML 生成 ---
    rows = ""
    for x in passed:
        # 根據正負值決定顏色：高於均線綠色，低於均線紅色
        color_class = "text-success" if x['Diff_Val'] >= 0 else "text-danger"
        rows += f"""
        <tr>
            <td><a href="https://www.tradingview.com/chart/?symbol={x['Symbol']}" target="_blank" class="btn btn-sm btn-outline-info fw-bold">{x['Symbol']} 🔗</a></td>
            <td>${x['Price']}</td>
            <td><span class="badge bg-secondary">{x['MA_Type']}</span> ${x['MA_Val']}</td>
            <td class="{color_class} fw-bold">{x['Diff_Str']}</td>
            <td><span class="badge bg-light text-dark">均線扣抵中</span></td>
        </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>均線回測篩選報告</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #0f172a; color: #f1f5f9; }}
            .card {{ background-color: #1e293b; border: none; }}
            .table {{ color: #cbd5e1; }}
        </style>
    </head>
    <body class="p-5">
        <div class="container card shadow-lg p-4">
            <h2 class="text-info">🎯 均線附近 1% 標的追蹤</h2>
            <p class="text-secondary small">更新時間 (UTC): {now} | 篩選條件: 股價於均線 ±1% 範圍內</p>
            <div class="table-responsive">
                <table class="table table-hover mt-3">
                    <thead><tr><th>代碼</th><th>現價</th><th>基準均線</th><th>偏離距離</th><th>狀態</th></tr></thead>
                    <tbody>{rows if passed else '<tr><td colspan="5" class="text-center py-5">目前無標的在均線 1% 範圍內</td></tr>'}</tbody>
                </table>
            </div>
        </div>
    </body>
    </html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
