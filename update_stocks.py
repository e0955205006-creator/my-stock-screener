import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def backtest_strategy(df_history, ma_series):
    """執行買賣策略回測並計算報酬與勝率"""
    total_return = 0.0
    trades_count = 0
    success_trades = 0
    in_position = False
    buy_price = 0.0
    buy_day_index = -1
    
    start_idx = ma_series.first_valid_index()
    if start_idx is None: return -999, 0, 0
    
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
            if high > trigger_buy and low <= trigger_buy:
                buy_price = trigger_buy
                in_position = True
                buy_day_index = i
                if close < ma: continue
        else:
            exit_price = None
            if i == buy_day_index + 1 and subset['Close'].iloc[i-1] < ma_subset.iloc[i-1]:
                exit_price = open_p
            elif close < ma:
                exit_price = close
            
            if exit_price is not None:
                trade_ret = (exit_price / buy_price) - 1
                total_return += trade_ret
                trades_count += 1
                if trade_ret > 0: success_trades += 1
                in_position = False
                
    win_rate = (success_trades / trades_count * 100) if trades_count > 0 else 0.0
    return total_return * 100, win_rate, trades_count

def find_best_ma(s_data):
    """從 15MA 到 35MA 尋找報酬率最高的週期"""
    best_ret = -float('inf')
    best_res = (20, 0, 0, 0)
    for ma_len in range(15, 36):
        ma_series = s_data['Close'].rolling(ma_len).mean()
        ret, win_rate, count = backtest_strategy(s_data, ma_series)
        if ret > best_ret:
            best_ret = ret
            best_res = (ma_len, ret, win_rate, count)
    return best_res

def main():
    # 今日日期與時區處理
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    
    try:
        response = requests.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"Sheet Error: {e}")
        return

    tickers_list = df['Ticker'].dropna().astype(str).str.strip().tolist()
    data = yf.download(tickers_list, period="3y", group_by='ticker', progress=False)

    all_data_list = []

    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            
            s_data = data[symbol].dropna() if len(tickers_list) > 1 else data.dropna()
            if s_data.empty: continue
            
            # --- 1. 自動尋找 15-35 最佳 MA ---
            best_ma, ret, win_rate, count = find_best_ma(s_data)
            
            current_price = s_data['Close'].iloc[-1]
            current_ma = s_data['Close'].rolling(best_ma).mean().iloc[-1]
            diff = (current_price / current_ma) - 1
            
            # --- 2. 財報日判定 (API優先 -> 工作表備援) ---
            e_day_obj = None
            e_day_str = "N/A"
            try:
                t_obj = yf.Ticker(symbol)
                cal = t_obj.calendar
                if cal is not None and not cal.empty and 'Earnings Date' in cal.index:
                    raw_e = cal.loc['Earnings Date'].iloc[0]
                    if hasattr(raw_e, 'date'): raw_e = raw_e.date()
                    if raw_e >= today_dt.date(): e_day_obj = raw_e
            except: pass

            if e_day_obj is None:
                sheet_val = row.get('Earnings', '')
                if pd.notnull(sheet_val) and str(sheet_val).strip() != "":
                    try:
                        sd = pd.to_datetime(sheet_val).date()
                        if sd >= today_dt.date(): e_day_obj = sd
                    except: pass
            
            if e_day_obj: e_day_str = e_day_obj.strftime('%Y-%m-%d')

            # --- 3. 視覺警示判定 ---
            is_earning_soon = False
            if e_day_obj:
                days_diff = (e_day_obj - today_dt.date()).days
                if 0 <= days_diff <= 7: is_earning_soon = True

            # --- 4. 篩選與 HTML 生成 ---
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                card_style = "border: 5px solid #dc3545; box-shadow: 0 0 15px rgba(220,53,69,0.3);" if is_earning_soon else ""
                
                card_html = f'''
                <div class="card mb-4 shadow" style="{card_style}">
                    <div class="card-header {bg} text-white d-flex justify-content-between align-items-center">
                        <div>
                            {symbol} <span class="badge bg-light text-dark ms-2">專屬 {best_ma}MA</span>
                            {f'<span class="badge bg-danger ms-2">⚠️ 財報週</span>' if is_earning_soon else ''}
                        </div>
                        <div class="text-end">
                            <small style="color:{'#90ee90' if ret > 0 else '#ffcccb'}; font-weight:bold;">3Y最佳報酬: {ret:+.1f}%</small><br>
                            <small style="opacity:0.8;">勝率: {win_rate:.1f}% ({count}次)</small>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="mb-3">
                            <b>{best_ma}MA 偏離:</b> {diff*100:.2f}% | <b>現價:</b> ${current_price:.2f} | 
                            <b>財報日:</b> <span class="badge {'bg-danger' if is_earning_soon else 'bg-warning text-dark'}">{e_day_str}</span>
                            {f'<br><small class="text-muted">備註: {note}</small>' if note else ''}
                        </p>
                        <div id="tv_{symbol}" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>
                            new TradingView.widget({{
                                "autosize": true, "symbol": "{symbol}", "interval": "D", "theme": "light",
                                "style": "1", "locale": "zh_TW", "container_id": "tv_{symbol}",
                                "hide_top_toolbar": true, "hide_side_toolbar": true,
                                "studies": [{{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {best_ma} }} }}]
                            }});
                        </script>
                    </div>
                </div>'''
                # 紀錄資料以便後續排序
                all_data_list.append({
                    'is_hold': is_hold, 
                    'ret': ret, 
                    'html': card_html
                })
        except: continue

    # --- 關鍵修正：排序邏輯 ---
    # 先按 is_hold 排序 (True=1, False=0，所以加負號讓 True 在前)
    # 再按 ret (報酬率) 排序 (由大到小，所以加負號)
    all_data_list.sort(key=lambda x: (not x['is_hold'], -x['ret']))
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"><title>策略排序監控</title></head><body class="bg-light py-5"><div class="container" style="max-width:850px;"><h2 class="text-center mb-4">📈 最佳 MA 策略監控 (依報酬排序)</h2>{"".join([i['html'] for i in all_data_list])}<p class="text-center text-muted mt-4 small">最後更新: {today_str}</p></div></body></html>''')

if __name__ == "__main__":
    main()
