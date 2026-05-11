import yfinance as yf
import pandas as pd
import datetime
import requests
import io
import os

# =================================================================
# 1. 外部資源配置
# =================================================================
# 你的 Google 試算表 ID
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 預設參數 (當試算表沒填時使用)
DEFAULT_MA = 20
SEARCH_RANGE = 0.01

def main():
    today = datetime.date.today()
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    print("正在從 Google 試算表讀取設定...")
    try:
        response = session.get(SHEET_URL)
        response.encoding = 'utf-8'
        # 讀取 CSV 並強力清洗標頭空白
        config_df = pd.read_csv(io.StringIO(response.text))
        config_df.columns = config_df.columns.str.strip()
        print(f"試算表讀取成功，欄位名稱為: {list(config_df.columns)}")
    except Exception as e:
        print(f"❌ 讀取試算表失敗，請檢查權限或 ID: {e}")
        return

    # 建立查找清單 (過濾掉代號欄位為空的行)
    tickers = config_df['股票代號'].dropna().astype(str).str.strip().tolist()
    if not tickers:
        print("❌ 試算表中沒有找到任何股票代號，請檢查 A 欄標題是否為『股票代號』")
        return

    # 下載數據
    print(f"正在掃描 {len(tickers)} 檔股票數據...")
    try:
        raw_df = yf.download(tickers, period="150d", interval="1d", group_by='ticker', progress=False, session=session)
    except Exception as e:
        print(f"❌ Yahoo Finance 下載失敗: {e}")
        return

    passed = []

    # 逐行處理
    for index, row in config_df.iterrows():
        ticker = str(row['股票代號']).strip().upper()
        if not ticker or ticker == 'NAN' or ticker == '': continue
        
        try:
            # 數據提取邏輯
            if len(tickers) == 1:
                df_stock = raw_df.dropna()
            else:
                if ticker in raw_df.columns:
                    df_stock = raw_df[ticker].dropna()
                elif isinstance(raw_df.columns, pd.MultiIndex) and ticker in raw_df.columns.levels[0]:
                    df_stock = raw_df[ticker].dropna()
                else: continue
                
            if df_stock.empty: continue
            
            # --- 1. 讀取設定 (MA 與 持股狀態) ---
            ma_val_raw = row.get('MA設定', DEFAULT_MA)
            ma_days = int(ma_val_raw) if pd.notnull(ma_val_raw) else DEFAULT_MA
            
            hold_status = str(row.get('是否持股', '')).strip()
            is_hold = True if hold_status == "是" else False
            
            note = str(row.get('備註', '')) if pd.notnull(row.get('備註')) else ""
            manual_e = str(row.get('手動財報日', '')).strip()

            # --- 2. 計算指標 ---
            close_price = df_stock['Close'].iloc[-1]
            ma_line = df_stock['Close'].rolling(ma_days).mean().iloc[-1]
            diff_ratio = (close_price / ma_line) - 1
            
            # --- 3. 判定顯示條件 ---
            if is_hold or abs(diff_ratio) <= SEARCH_RANGE:
                # 財報處理：完全依照試算表，若沒填就是 N/A
                e_str = manual_e if manual_e not in ['nan', ''] else "N/A"
                is_near = False
                
                # 只有在手動有填日期時，才亮紅色預警框
                if e_str != "N/A":
                    try:
                        e_date_obj = datetime.datetime.strptime(e_str[:10], '%Y-%m-%d').date()
                        if 0 <= (e_date_obj - today).days <= 7:
                            is_near = True
                    except:
                        pass

                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(close_price), 2),
                    "MA_Days": ma_days,
                    "Diff_Val": float(diff_ratio),
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": e_str,
                    "Warning": is_near,
                    "Is_Portfolio": is_hold,
                    "Note": note
                })
        except Exception as e:
            print(f"處理 {ticker} 時略過: {e}")
            continue

    # 排序：持股(0) > 財報預警(0) > 偏離度
    passed.sort(key=lambda x: (not x['Is_Portfolio'], not x['Warning'], -x['Diff_Val']))

    # 生成 HTML
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
        <h2 class="text-center mb-2">🎯 雲端後台監控儀表板</h2>
        <p class="text-center text-muted small">更新時間 (台北): {now_str}</p>
        <div class="alert alert-secondary text-center small">資料來源：Google 試算表 (ID: {SHEET_ID})</div>
        <hr>{rows_html if passed else '<div class="alert alert-warning text-center">暫無符合條件標的，請確認試算表是否有選『是』或符合偏離度。</div>'}
    </div></body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_final)

if __name__ == "__main__":
    main()
