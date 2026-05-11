import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/export?format=csv"

def main():
    # 取得台北時間
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_date = today_dt.date()
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    session = requests.Session()
    
    print("正在下載雲端試算表...")
    try:
        response = session.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print("讀取失敗: " + str(e))
        return

    tickers_list = df['Ticker'].dropna().astype(str).str.strip().tolist()
    # 批次下載價格數據 (效率較高)
    data = yf.download(tickers_list, period="150d", group_by='ticker', progress=False)

    hold_cards = ""    # 存放持股 (Y)
    watch_cards = ""   # 存放觀察股

    # --- TradingView 模板 (避開 Python 大括號解析) ---
    tv_template = """
    <div id="tv_SYMBOL_PLACEHOLDER" style="height:400px;"></div>
    <script src="https://s3.tradingview.com/tv.js"></script>
    <script>
    new TradingView.widget({
      "autosize": true, "symbol": "SYMBOL_PLACEHOLDER", "interval": "D", "theme": "light", "style": "1", "locale": "zh_TW",
      "container_id": "tv_SYMBOL_PLACEHOLDER", "hide_top_toolbar": true,
      "studies": [ { "id": "MASimple@tv-basicstudies", "inputs": { "length": MA_LEN_PLACEHOLDER } } ]
    });
    </script>
    """

    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            ma_len = str(int(row.get('MA', 20)))
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            
            # --- 財報日邏輯：自動抓取 + 效期判定 + 試算表補位 ---
            e_day = "N/A"
            border_style = "border: none;" 
            
            # A. 嘗試從 Yahoo 自動抓取
            try:
                t_obj = yf.Ticker(symbol)
                cal = t_obj.calendar
                if cal is not None and not cal.empty and 'Earnings Date' in cal.index:
                    raw_e_dt = cal.loc['Earnings Date'].iloc[0].date()
                    # 只有當 Yahoo 給的日期是「今天或未來」才採用
                    if raw_e_dt >= today_date:
                        e_day = raw_e_dt.strftime('%Y-%m-%d')
            except: 
                e_day = "N/A"

            # B. 如果 Yahoo 沒抓到（或是過期的），改用試算表手動填寫的
            if e_day == "N/A":
                e_val = row.get('Earnings', '')
                if pd.notnull(e_val) and str(e_val).strip().lower() != 'nan':
                    e_day = str(e_val).strip()

            # C. 財報預警：判斷是否在 7 日內 (觸發紅框)
            if e_day != "N/A":
                try:
                    target_dt = datetime.datetime.strptime(e_day, '%Y-%m-%d').date()
                    delta = (target_dt - today_date).days
                    if 0 <= delta <= 7:
                        border_style = "border: 4px solid #dc3545; box-shadow: 0 0 15px rgba(220,53,69,0.4);"
                except: pass

            # --- 價格運算 ---
            s_data = data[symbol].dropna() if len(tickers_list) > 1 else data.dropna()
            if s_data.empty: continue
            
            price = s_data['Close'].iloc[-1]
            ma_val = s_data['Close'].rolling(int(ma_len)).mean().iloc[-1]
            diff = (price / ma_val) - 1
            
            # 顯示判定
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                d_color = "text-danger" if diff < 0 else "text-success"
                
                # 建立卡片 HTML
                card = '<div class="card mb-4 shadow" style="' + border_style + '">'
                card += '<div class="card-header ' + bg + ' text-white d-flex justify-content-between">'
                card += '<span>' + symbol + ' <b style="color:#ffc107;">' + (note if is_hold else "") + '</b></span>'
                card += '<small>財報日: ' + e_day + '</small></div>'
                card += '<div class="card-body"><p><b>' + ma_len + 'MA 偏離:</b> '
                card += '<span class="' + d_color + '" style="font-weight:bold;">' + "{:.2f}%".format(diff*100) + '</span> | '
                card += '<b>價格:</b> $' + "{:.2f}".format(price) + '</p>'
                
                # 替換圖表模板
                current_tv = tv_template.replace("SYMBOL_PLACEHOLDER", symbol).replace("MA_LEN_PLACEHOLDER", ma_len)
                card += current_tv
                card += '</div></div>'
                
                # 持股置頂分流
                if is_hold: hold_cards += card
                else: watch_cards += card
        except: continue

    # 組合最終頁面
    final_content = hold_cards + watch_cards
    page = '<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    page += '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>'
    page += '<body class="bg-light py-5"><div class="container" style="max-width:800px;">'
    page += '<div class="text-center mb-5"><h2 class="fw-bold">🎯 美股全自動監控儀表板</h2>'
    page += '<p class="text-muted small">最後更新: ' + today_str + ' (台北時間)</p>'
    page += '<div class="badge bg-danger">紅框提示：財報將於 7 日內發布</div></div>'
    page += final_content if final_content else '<p class="text-center">目前無符合條件股票</p>'
    page += '</div></body></html>'

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("✅ 全部任務完成，網頁已更新")

if __name__ == "__main__":
    main()
