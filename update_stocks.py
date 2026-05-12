import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/export?format=csv"

def backtest_strategy(df_history, ma_series):
    """
    優化回測邏輯 (盤中觸價買進)：
    - 買入觸發價：trigger = 均線 * 1.015
    - 買入條件：當日最低價 <= trigger 且 當日最高價 > trigger (確保盤中觸及該價位)
    - 買入成交價：一律以 trigger 計算
    - 停利：持有期間盤中最高價 >= 買入價 * 1.05 (獲利 5%)
    - 離場：收盤價 < 當前均線
    """
    total_return = 0.0
    in_position = False
    buy_price = 0.0
    
    start_idx = ma_series.first_valid_index()
    if start_idx is None: return 0.0
    
    subset = df_history.loc[start_idx:]
    ma_subset = ma_series.loc[start_idx:]

    for i in range(len(subset)):
        high = subset['High'].iloc[i]
        low = subset['Low'].iloc[i]
        close = subset['Close'].iloc[i]
        ma = ma_subset.iloc[i]
        trigger_price = ma * 1.015
        
        if not in_position:
            # 修改點：確保盤中是有觸碰到 trigger_price 的 (High > trigger 且 Low <= trigger)
            if high > trigger_price and low <= trigger_price:
                buy_price = trigger_price
                in_position = True
        else:
            # 賣出邏輯
            # 1. 停利：盤中最高價達到買價 5%
            if high >= buy_price * 1.05:
                total_return += 0.05
                in_position = False
            # 2. 離場：收盤跌破均線
            elif close < ma:
                exit_return = (close / buy_price) - 1
                total_return += exit_return
                in_position = False
                
    return total_return * 100

def main():
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    
    try:
        response = requests.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except: return

    tickers_list = df['Ticker'].dropna().astype(str).str.strip().tolist()
    data = yf.download(tickers_list, period="3y", group_by='ticker', progress=False)

    all_data_list = []

    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            ma_len = int(row.get('MA', 20))
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            
            s_data = data[symbol].dropna() if len(tickers_list) > 1 else data.dropna()
            if s_data.empty: continue
            
            ma_series = s_data['Close'].rolling(ma_len).mean()
            strategy_ret = backtest_strategy(s_data, ma_series)
            
            current_price = s_data['Close'].iloc[-1]
            current_ma = ma_series.iloc[-1]
            diff = (current_price / current_ma) - 1
            
            # 財報日判定
            e_day = "N/A"
            try:
                cal = yf.Ticker(symbol).calendar
                if cal is not None and not cal.empty:
                    raw_e = cal.loc['Earnings Date'].iloc[0].date()
                    if raw_e >= today_dt.date(): e_day = raw_e.strftime('%Y-%m-%d')
            except: pass

            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                ret_color = "#90ee90" if strategy_ret > 0 else "#ffcccb"
                
                card_html = '<div class="card mb-4 shadow">'
                card_html += '<div class="card-header ' + bg + ' text-white d-flex justify-content-between align-items-center">'
                card_html += '<div>' + symbol + ' <b style="color:#ffc107;">' + (note if is_hold else "") + '</b></div>'
                card_html += '<div class="text-end"><small style="color:' + ret_color + '; font-weight:bold;">3Y策略(壓回買): ' + "{:+.1f}%".format(strategy_ret) + '</small><br><small>財報日: ' + e_day + '</small></div></div>'
                card_html += '<div class="card-body"><p><b>' + str(ma_len) + 'MA 偏離:</b> ' + "{:.2f}%".format(diff*100) + ' | <b>現價:</b> $' + "{:.2f}".format(current_price) + '</p>'
                card_html += '<div id="tv_' + symbol + '" style="height:400px;"></div>'
                card_html += '<script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({"autosize":true,"symbol":"' + symbol + '","interval":"D","theme":"light","style":"1","locale":"zh_TW","container_id":"tv_' + symbol + '","hide_top_toolbar":true,"studies":[{"id":"MASimple@tv-basicstudies","inputs":{"length":' + str(ma_len) + '}}]});</script></div></div>'

                all_data_list.append({'is_hold': is_hold, 'diff': diff, 'html': card_html})
        except: continue

    all_data_list.sort(key=lambda x: (not x['is_hold'], -x['diff']))
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write('<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light py-5"><div class="container" style="max-width:800px;"><h2 class="text-center mb-4">🎯 美股全自動策略儀表板</h2>' + "".join([i['html'] for i in all_data_list]) + '</div></body></html>')

if __name__ == "__main__":
    main()
