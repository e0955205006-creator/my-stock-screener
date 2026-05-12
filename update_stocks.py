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
    放寬門檻版回測邏輯：
    - 買入：盤中觸及 (MA * 1.015)
    - 買入價：MA * 1.015
    - 賣出情境 A：直到某日「收盤價」跌破 MA，以該收盤價賣出
    - 賣出情境 B：若買進當天收盤就破線，則次日開盤價賣出
    """
    total_return = 0.0
    in_position = False
    buy_price = 0.0
    buy_day_index = -1
    
    start_idx = ma_series.first_valid_index()
    if start_idx is None: return 0.0
    
    subset = df_history.loc[start_idx:]
    ma_subset = ma_series.loc[start_idx:]

    for i in range(len(subset)):
        high = subset['High'].iloc[i]
        low = subset['Low'].iloc[i]
        close = subset['Close'].iloc[i]
        open_p = subset['Open'].iloc[i]
        ma = ma_subset.iloc[i]
        trigger_buy = ma * 1.015
        
        if not in_position:
            # 買入條件
            if high > trigger_buy and low <= trigger_buy:
                buy_price = trigger_buy
                in_position = True
                buy_day_index = i
                # 如果買入當天收盤就破線，標記並等待次日
                if close < ma: continue
        else:
            # 賣出邏輯
            # 情境 B：買進次日開盤賣 (處理當天買當天破的情況)
            if i == buy_day_index + 1 and subset['Close'].iloc[i-1] < ma_subset.iloc[i-1]:
                exit_price = open_p
                total_return += (exit_price / buy_price) - 1
                in_position = False
            # 情境 A (放寬)：直到「收盤價」跌破均線
            elif close < ma:
                exit_price = close
                total_return += (exit_price / buy_price) - 1
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
    # 下載 3 年數據
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
            
            # 財報日
            e_day = "N/A"
            try:
                cal = yf.Ticker(symbol).calendar
                if cal is not None and not cal.empty:
                    raw_e = cal.loc['Earnings Date'].iloc[0].date()
                    if raw_e >= today_dt.date(): e_day = raw_e.strftime('%Y-%m-%d')
            except: pass

            # 篩選 1% 或持股
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                ret_color = "#90ee90" if strategy_ret > 0 else "#ffcccb"
                
                card_html = f'''
                <div class="card mb-4 shadow">
                    <div class="card-header {bg} text-white d-flex justify-content-between align-items-center">
                        <div>{symbol} <b style="color:#ffc107;">{note if is_hold else ""}</b></div>
                        <div class="text-end">
                            <small style="color:{ret_color}; font-weight:bold;">3Y策略(收盤破才賣): {strategy_ret:+.1f}%</small><br>
                            <small>財報日: {e_day}</small>
                        </div>
                    </div>
                    <div class="card-body">
                        <p><b>{ma_len}MA 偏離:</b> {diff*100:.2f}% | <b>現價:</b> ${current_price:.2f}</p>
                        <div id="tv_{symbol}" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>
                            new TradingView.widget({{
                                "autosize": true, "symbol": "{symbol}", "interval": "D", "theme": "light",
                                "style": "1", "locale": "zh_TW", "container_id": "tv_{symbol}",
                                "hide_top_toolbar": true,
                                "studies": [{{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {ma_len} }} }}]
                            }});
                        </script>
                    </div>
                </div>'''
                all_data_list.append({'is_hold': is_hold, 'diff': diff, 'html': card_html})
        except: continue

    all_data_list.sort(key=lambda x: (not x['is_hold'], -x['diff']))
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="bg-light py-5"><div class="container" style="max-width:800px;"><h2 class="text-center mb-4">📈 趨勢波段策略監控儀表板</h2>{"".join([i['html'] for i in all_data_list])}</div><p class="text-center text-muted small">最後更新: {today_str}</p></body></html>''')

if __name__ == "__main__":
    main()
