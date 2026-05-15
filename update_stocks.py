import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 基本配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def backtest_strategy(df_history, ma_series):
    """回測並記錄每一筆交易細節（含手續費與勝率）"""
    total_return = 0.0
    trades_count = 0
    success_trades = 0
    in_position = False
    buy_price_raw = 0.0
    buy_date = None
    buy_day_index = -1
    trade_logs = []
    
    fee_buy_rate = 0.0008          # 0.08%
    fee_sell_rate = 0.0008206      # 0.08% + 0.00206%
    
    start_idx = ma_series.first_valid_index()
    if start_idx is None: return -999, 0, 0, []
    
    subset = df_history.loc[start_idx:]
    ma_subset = ma_series.loc[start_idx:]

    for i in range(len(subset)):
        close = subset['Close'].iloc[i]
        high = subset['High'].iloc[i]
        low = subset['Low'].iloc[i]
        open_p = subset['Open'].iloc[i]
        date = subset.index[i].strftime('%Y-%m-%d')
        ma = ma_subset.iloc[i]
        trigger_buy = ma * 1.015
        
        if not in_position:
            if high > trigger_buy and low <= trigger_buy:
                buy_price_raw = trigger_buy
                buy_date = date
                in_position = True
                buy_day_index = i
                if close < ma: continue
        else:
            exit_price_raw = None
            if i == buy_day_index + 1 and subset['Close'].iloc[i-1] < ma_subset.iloc[i-1]:
                exit_price_raw = open_p
            elif close < ma:
                exit_price_raw = close
            
            if exit_price_raw is not None:
                cost = buy_price_raw * (1 + fee_buy_rate)
                proceeds = exit_price_raw * (1 - fee_sell_rate)
                trade_ret = (proceeds / cost) - 1
                total_return += trade_ret
                trades_count += 1
                if trade_ret > 0: success_trades += 1
                
                trade_logs.append({
                    'buy_date': buy_date, 'buy_p': round(buy_price_raw, 3),
                    'sell_date': date, 'sell_p': round(exit_price_raw, 3),
                    'ret': f"{trade_ret*100:+.2f}%", 'is_win': trade_ret > 0
                })
                in_position = False
                
    win_rate = (success_trades / trades_count * 100) if trades_count > 0 else 0.0
    return total_return * 100, win_rate, trades_count, trade_logs

def find_best_ma(s_data):
    """從 15-35MA 尋找扣除手續費後報酬率最高的週期"""
    best_ret = -float('inf')
    best_res = (20, 0, 0, 0, [])
    for ma_len in range(15, 36):
        ma_series = s_data['Close'].rolling(ma_len).mean()
        ret, win_rate, count, logs = backtest_strategy(s_data, ma_series)
        if ret > best_ret:
            best_ret = ret
            best_res = (ma_len, ret, win_rate, count, logs)
    return best_res

def main():
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    
    try:
        response = requests.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"Sheet讀取失敗: {e}"); return

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
            
            # 1. 自動尋優與回測
            best_ma, ret, win_rate, count, logs = find_best_ma(s_data)
            current_price = s_data['Close'].iloc[-1]
            current_ma = s_data['Close'].rolling(best_ma).mean().iloc[-1]
            diff = (current_price / current_ma) - 1

            # 2. 財報日判定邏輯 (API 優先 -> 工作表備援)
            e_day_obj = None
            e_day_str = "N/A"
            try:
                t_obj = yf.Ticker(symbol)
                cal = t_obj.calendar
                if cal is not None and not cal.empty and 'Earnings Date' in cal.index:
                    raw_e = cal.loc['Earnings Date'].iloc[0]
                    if hasattr(raw_e, 'date') and raw_e.date() >= today_dt.date():
                        e_day_obj = raw_e.date()
            except: pass

            if e_day_obj is None:
                sheet_val = row.get('Earnings', '')
                if pd.notnull(sheet_val) and str(sheet_val).strip() != "":
                    try:
                        sd = pd.to_datetime(sheet_val).date()
                        if sd >= today_dt.date(): e_day_obj = sd
                    except: pass
            
            if e_day_obj: e_day_str = e_day_obj.strftime('%Y-%m-%d')
            
            # 3. 紅框警示邏輯 (7天內)
            is_earning_soon = False
            if e_day_obj:
                if 0 <= (e_day_obj - today_dt.date()).days <= 7: is_earning_soon = True

            # 4. 篩選與 HTML 生成
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                card_style = "border: 5px solid #dc3545; box-shadow: 0 0 15px rgba(220,53,69,0.3);" if is_earning_soon else ""
                
                # 建立明細表格
                log_rows = "".join([f"<tr class='{'table-success' if l['is_win'] else ''}'><td>{l['buy_date']}</td><td>{l['buy_p']}</td><td>{l['sell_date']}</td><td>{l['sell_p']}</td><td>{l['ret']}</td></tr>" for l in logs])

                card_html = f'''
                <div class="card mb-4 shadow" style="{card_style}">
                    <div class="card-header {bg} text-white d-flex justify-content-between align-items-center">
                        <div>
                            {symbol} <span class="badge bg-light text-dark ms-2">專屬 {best_ma}MA</span>
                            {f'<span class="badge bg-danger ms-2">⚠️ 財報週</span>' if is_earning_soon else ''}
                        </div>
                        <div class="text-end">
                            <small style="color:{'#90ee90' if ret > 0 else '#ffcccb'}; font-weight:bold;">3Y淨報酬: {ret:+.1f}%</small><br>
                            <small style="opacity:0.8;">勝率: {win_rate:.1f}% ({count}次)</small>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="mb-3">
                            <b>{best_ma}MA 偏離:</b> {diff*100:.2f}% | <b>現價:</b> ${current_price:.2f} | 
                            <b>財報日:</b> <span class="badge {'bg-danger' if is_earning_soon else 'bg-warning text-dark'}">{e_day_str}</span>
                        </p>
                        
                        <button class="btn btn-sm btn-outline-secondary mb-3" type="button" data-bs-toggle="collapse" data-bs-target="#logs_{symbol}">查看 {count} 筆進出明細</button>
                        <div class="collapse" id="logs_{symbol}">
                            <div class="table-responsive mb-3" style="max-height: 300px;">
                                <table class="table table-sm table-hover small text-center">
                                    <thead class="table-light"><tr><th>買入日期</th><th>買入價</th><th>賣出日期</th><th>賣出價</th><th>損益</th></tr></thead>
                                    <tbody>{log_rows}</tbody>
                                </table>
                            </div>
                        </div>

                        <div id="tv_{symbol}" style="height:400px;"></div>
                        <script src="https://s3.tradingview.com/tv.js"></script>
                        <script>
                            new TradingView.widget({{
                                "autosize": true, "symbol": "{symbol}", "interval": "D", "theme": "light",
                                "style": "1", "locale": "zh_TW", "container_id": "tv_{symbol}",
                                "hide_top_toolbar": true, "hide_side_toolbar": true,
                                "studies": [{{ "id": "MASimple@tv-basicstudies", "inputs": {{ "length": {best_ma} }} }}],
                                "overrides": {{
                                    "mainSeriesProperties.candleStyle.upColor": "#f63538",
                                    "mainSeriesProperties.candleStyle.downColor": "#1aa308",
                                    "mainSeriesProperties.candleStyle.borderUpColor": "#f63538",
                                    "mainSeriesProperties.candleStyle.borderDownColor": "#1aa308",
                                    "mainSeriesProperties.candleStyle.wickUpColor": "#f63538",
                                    "mainSeriesProperties.candleStyle.wickDownColor": "#1aa308"
                                }}
                            }});
                        </script>
                    </div>
                </div>'''
                all_data_list.append({'is_hold': is_hold, 'ret': ret, 'html': card_html})
        except: continue

    all_data_list.sort(key=lambda x: (not x['is_hold'], -x['ret']))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script><title>策略監控</title></head><body class="bg-light py-5"><div class="container" style="max-width:850px;"><h2 class="text-center mb-4">📈 策略尋優監控 (含交易對帳單)</h2>{"".join([i['html'] for i in all_data_list])}</div></body></html>''')

if __name__ == "__main__":
    main()
