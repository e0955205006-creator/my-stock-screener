import yfinance as yf
import pandas as pd
import datetime

# --- 1. 策略自定義區 (可針對不同股票細膩設定) ---
# 格式: "代號": (MA天數, 偏移比例)
# 偏移比例說明: 0.99 代表低於均線 1%, 0.98 代表低於 2%
CUSTOM_CONFIG = {
    "AAPL": (20, 0.99),   # 蘋果：20MA, 跌破1%
    "NVDA": (10, 0.97),   # 輝達：波段快，改用10MA, 跌破3%
    "NFLX": (20, 0.98),   # 奈飛：20MA, 跌破2%
    "LULU": (60, 0.995),  # Lululemon: 慣性較長，用60MA, 跌破0.5%
    "JNJ": (20, 0.998),   # 強生：極其穩定，跌破0.2%就觸發
}

# 預設參數 (若上面沒設定，就跑這個)
DEFAULT_MA = 20
DEFAULT_OFFSET = 0.99 

# --- 2. 完整公司名單 (依據 4 張圖片內容整理) ---
TICKERS = [
    # 圖片 1c2d6c.jpg (標配名單)
    "INTU", "GOOGL", "PLUS", "AXP", "AIT", "NVO", "ACN", "AGM", "BKNG", "GAJG", 
    "ASML", "AME", "AAPL", "IBP", "PAYC", "URI", "GIB", "AEE", "XEL", "WEC", 
    "LNT", "CTAS", "CPK", "CHE", "HD", "UNH", "ADP", "APD", "ATO", "COST", 
    "MA", "V", "CW", "GD", "DPZ", "DRI", "ECL", "EME", "FIX", "GRMN", 
    "HEI", "ICFI", "IDA", "IEX", "ITW", "JKHY", "MZTI", "II", "LOW", "MCD", 
    "MCO", "MLM", "MSS", "MSCI", "HCA", "DKS", "ODFL", "OMC", "PKG", "RACE", 
    "RMD", "ROP", "ROST", "RSG", "SHW", "SNA", "SNX", "SSD", "TMQ", "TSCO", 
    "TTC", "TXRH", "WDFC", "WSO", "ZTS", "UNP", "MLR", "A_SN", "AYI", "SAIC", 
    "TJX", "MSFT", "ETN",
    
    # 圖片 1c2c95.jpg (成長與雲端)
    "CMG", "FTNT", "TYL", "CPAY", "ASR", "ANET", "MIDD", "LOPE", "ADUS", "CRL", 
    "NFLX", "SAIA", "MEDP", "RBC", "MTD", "FFIV", "FIVE", "EW", "BURL", "ULTA", 
    "SAM", "ISRG", "COO", "AZO", "BJ", "VEEV", "ICLR", "ADBE", "FICO", "IDXX", 
    "QLYS", "EEFT", "TREX", "SNPS", "TTD", "CPRT", "DECK",
    
    # 圖片 1c2974.jpg (超級 B+ 公司)
    "JNJ", "UNF", "AN", "ALGN", "HON", "LULU", "PH", "PWR",
    
    # 圖片 1c290f.jpg (B 級績效公司)
    "CSL", "EVRG", "CP", "CHD", "FBIN", "AAP", "CSGS", "ED", "DTE", "CMS", 
    "CHKP", "CAJPY", "AWK", "AWR", "ARTNA", "AGCO", "AEP", "ADM", "ADI", "ACNB", 
    "AAON", "VZ", "MDT", "GIII", "EHC", "DOV", "MMM", "CNI", "APH", "AOS", 
    "AMCX", "ALLE", "ALG", "AKAM", "AEQ", "BR", "CASY", "ARMK", "CSCO", "CL", 
    "COLM", "BFAM", "BDL", "APTV", "AMAT", "CNXN", "CMI", "CMCSA", "CLX", "CHH", 
    "CGNX", "CDW", "CDNS", "CCI", "CAKE", "CAE", "CACI", "BWA", "BOOT", "BDX", 
    "BCPC", "BCE", "BBSI", "BAH", "AVY", "AWI", "INTC", "ATR"
]

def main():
    # 抓取數據 (取 100 天以滿足不同 MA 需求)
    data = yf.download(TICKERS, period="100d", interval="1d", progress=False)['Close']
    passed = []
    
    for ticker in TICKERS:
        try:
            col = data[ticker].dropna()
            if col.empty: continue
            
            # 判斷參數：有自定義用自定義，否則用預設
            ma_days, offset = CUSTOM_CONFIG.get(ticker, (DEFAULT_MA, DEFAULT_OFFSET))
            
            if len(col) < ma_days: continue
            
            ma_val = col.rolling(ma_days).mean().iloc[-1]
            price = col.iloc[-1]
            
            # 篩選邏輯
            if price <= (ma_val * offset):
                diff = ((price / ma_val) - 1) * 100
                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "MA_Type": f"{ma_days}MA",
                    "MA_Val": round(float(ma_val), 2),
                    "Threshold": f"-{(1-offset)*100:.1f}%",
                    "Diff": f"{diff:.2f}%"
                })
        except:
            continue

    # 按偏離幅度排序
    passed = sorted(passed, key=lambda x: float(x['Diff'].replace('%','')))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # --- 生成網頁 HTML ---
    rows = ""
    for x in passed:
        rows += f"""
        <tr>
            <td><a href="https://www.tradingview.com/chart/?symbol={x['Symbol']}" target="_blank" class="btn btn-sm btn-outline-info fw-bold">{x['Symbol']} 🔗</a></td>
            <td>${x['Price']}</td>
            <td><span class="badge bg-secondary">{x['MA_Type']}</span> ${x['MA_Val']}</td>
            <td class="text-warning">{x['Threshold']}</td>
            <td class="text-danger fw-bold">{x['Diff']}</td>
        </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8"><title>美股精細化篩選報告</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #0f172a; color: #f1f5f9; }}
            .card {{ background-color: #1e293b; border: none; border-radius: 15px; }}
            .table {{ color: #cbd5e1; border-color: #334155; }}
            .text-info {{ color: #38bdf8 !important; }}
        </style>
    </head>
    <body class="p-5">
        <div class="container card shadow-xl p-4">
            <h2 class="text-info">🎯 多參數自動篩選報告</h2>
            <p class="text-secondary small">更新時間 (UTC): {now} | 掃描總數: {len(TICKERS)}</p>
            <div class="table-responsive">
                <table class="table table-hover mt-3">
                    <thead><tr><th>代碼 (點擊看圖)</th><th>現價</th><th>基準均線</th><th>設定門檻</th><th>目前偏離</th></tr></thead>
                    <tbody>{rows if passed else '<tr><td colspan="5" class="text-center py-5">目前無符合條件股票</td></tr>'}</tbody>
                </table>
            </div>
        </div>
    </body>
    </html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    main()
