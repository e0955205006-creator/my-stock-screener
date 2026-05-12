import yfinance as yf
import pandas as pd
import datetime
import requests
import io

# 1. 基本配置
SHEET_ID = "17stsDM0pLhb_oVvqEaTufVrd00HXa6NwlRSNVYStBkE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def backtest_strategy(df_history, ma_series):
    """
    執行你的買賣策略回測：
    - 買入：股價回測 MA * 1.015 時買入
    - 賣出：收盤跌破 MA 賣出 (或買入隔日若前日收盤低於MA則開盤賣)
    """
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
            # 買入策略：觸及 MA * 1.015
            if high > trigger_buy and low <= trigger_buy:
                buy_price = trigger_buy
                in_position = True
                buy_day_index = i
                # 如果買入當天收盤就破線，下回合處理
                if close < ma: continue
        else:
            exit_price = None
            # 賣出策略 1：買入隔天檢查，若前日收盤已破 MA，則隔日開盤賣出
            if i == buy_day_index + 1 and subset['Close'].iloc[i-1] < ma_subset.iloc[i-1]:
                exit_price = open_p
            # 賣出策略 2：當日收盤破 MA
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
    """從 MA 15 測到 35，找出報酬率最高的週期"""
    best_ret = -float('inf')
    best_res = (20, 0, 0, 0) # 預設回傳 20MA
    
    for ma_len in range(15, 36):
        ma_series = s_data['Close'].rolling(ma_len).mean()
        ret, win_rate, count = backtest_strategy(s_data, ma_series)
        if ret > best_ret:
            best_ret = ret
            best_res = (ma_len, ret, win_rate, count)
    return best_res

def main():
    # 設定今日日期（考慮時區）
    today_dt = datetime.datetime.now() + datetime.timedelta(hours=8)
    today_str = today_dt.strftime("%Y-%m-%d %H:%M")
    
    try:
        response = requests.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        print(f"讀取試算表失敗: {e}")
        return

    tickers_list = df['Ticker'].dropna().astype(str).str.strip().tolist()
    # 抓取 3 年歷史資料
    data = yf.download(tickers_list, period="3y", group_by='ticker', progress=False)

    all_data_list = []

    for _, row in df.iterrows():
        try:
            symbol = str(row['Ticker']).strip().upper()
            is_hold = str(row.get('Hold', '')).strip().upper() == 'Y'
            note = str(row.get('Note', '')) if pd.notnull(row.get('Note')) else ""
            
            s_data = data[symbol].dropna() if len(tickers_list) > 1 else data.dropna()
            if s_data.empty: continue
            
            # --- 核心：自動尋找 15-35MA 最佳參數 ---
            best_ma, ret, win_rate, count = find_best_ma(s_data)
            
            ma_series = s_data['Close'].rolling(best_ma).mean()
            current_price = s_data['Close'].iloc[-1]
            current_ma = ma_series.iloc[-1]
            diff = (current_price / current_ma) - 1
            
            # 財報日檢查邏輯
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

            if e_day_obj is None: # 備援：檢查試算表 Earnings 欄位
                sheet_val = row.get('Earnings', '')
                if pd.notnull(sheet_val) and str(sheet_val).strip() != "":
                    try:
                        sd = pd.to_datetime(sheet_val).date()
                        if sd >= today_dt.date(): e_day_obj = sd
                    except: pass

            if e_day_obj:
                e_day_str = e_day_obj.strftime('%Y-%m-%d')
            
            # --- 紅框判定：距離財報 7 天內 ---
            is_earning_soon = False
            if e_day_obj:
                days_to_earnings = (e_day_obj - today_dt.date()).days
                if 0 <= days_to_earnings <= 7:
                    is_earning_soon = True

            # 顯示判斷：持股 或 靠近最佳 MA 的 1% 範圍
            if is_hold or abs(diff) <= 0.01:
                bg = "bg-dark" if is_hold else "bg-primary"
                card_style = "border: 5px solid #dc3545; box-shadow: 0 0 15px rgba(220,53,69,0.3);" if is_earning_soon else ""
                warning_label = '<span class="badge bg-danger ms-2">⚠️ 財報週</span>' if is_earning_soon else ""
                
                card_html = f'''
                <div class="card mb-4 shadow" style="{card_style}">
                    <div class="card-header {bg} text-white d-flex justify-content-between align-items-center">
                        <div>
                            {symbol} 
                            <span class="badge bg-light text-dark ms-2">專屬 {best_ma}MA</span>
                            <small class="ms-2" style="color:#ffc107;">{note}</small>
                            {warning_label}
                        </div>
                        <div class="text-end">
                            <small style="color:{'#90ee90' if ret > 0 else '#ffcccb'}; font-weight:bold;">3Y最佳報酬: {ret:+.1f}%</small><br>
                            <small style="opacity:0.8;">勝率: {win_rate:.1f}% ({count}次)</small>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="mb-3">
                            <b>{best_ma}MA 偏離:</b> {diff*100:.2f}% | 
                            <b>現價:</b> ${current_price:.2f} | 
                            <b>財報日:</b> <span class="badge {'bg-danger' if is_earning_soon else 'bg-warning text-dark'}">{e_day_str}</span>
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
                all_data_list.append({'is_hold': is_hold, 'diff': diff, 'html': card_html})
        except Exception as ex:
            print(f"處理 {symbol} 出錯: {ex}")
            continue

    # 排序：持股優先，其餘按偏離度排序
    all_data_list.sort(key=lambda x: (not x['is_hold'], -x['diff']))
    
    # 輸出 HTML
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet"><title>MA尋優監控</title></head><body class="bg-light py-5"><div class="container" style="max-width:850px;"><h2 class="text-center mb-4">🧪 MA 參數尋優與監控 (15-35)</h2>{"".join([i['html'] for i in all_data_list])}<p class="text-center text-muted mt-4 small">最後更新: {today_str}</p></div></body></html>''')

if __name__ == "__main__":
    main()
