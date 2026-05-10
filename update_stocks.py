import yfinance as yf
import pandas as pd
import datetime
import time
import requests

# --- 1. 參數與自定義區 ---
SEARCH_RANGE = 0.01  
DEFAULT_MA = 20

# 持股紀錄區 (請確保代碼與 TICKERS 清單中一致)
MY_PORTFOLIO = {
    "ARMK": "2026-05-01 買入",
    "V": "長期持有計畫",
}

# 這裡列出所有要掃描的代碼
TICKERS = ["ARMK", "V", "AAPL", "NVDA", "INTU", "GOOGL", "MA"] # ...其餘代碼保持不變

def fetch_earnings_date_safe(t_obj, today_date):
    """ 強力修正版：確保日期計算不會出錯 """
    try:
        # 嘗試從 calendar 抓取
        cal = t_obj.get_calendar()
        if cal and isinstance(cal, dict) and 'Earnings Date' in cal:
            d_list = cal['Earnings Date']
            if d_list and len(d_list) > 0:
                # 關鍵修正：強制轉換為 naive date (不含時區)
                return d_list[0].astimezone(None).date()
        
        # 備援：從 earnings_dates 抓取
        e_df = t_obj.get_earnings_dates()
        if e_df is not None and not e_df.empty:
            # 找到大於等於今天的日期中最小的一個
            future_dates = e_df.index[e_df.index.date >= today_date]
            if not future_dates.empty:
                return future_dates.min().astimezone(None).date()
    except Exception as e:
        print(f"抓取財報日期失敗: {e}")
    return None

def main():
    session = requests.Session()
    # ... Headers 設定保持不變 ...

    data = yf.download(TICKERS, period="150d", interval="1d", progress=False)['Close']
    passed = []
    today_dt = datetime.datetime.now()
    today_date = today_dt.date()
    
    for ticker in TICKERS:
        try:
            if ticker not in data.columns: continue
            col = data[ticker].dropna()
            if len(col) < 60: continue
            
            price = col.iloc[-1]
            ma_val = col.rolling(DEFAULT_MA).mean().iloc[-1]
            diff_ratio = (price / ma_val) - 1
            
            # --- 持股判斷 ---
            is_portfolio = ticker in MY_PORTFOLIO
            
            # 符合 1% 條件 或 是我的持股 
            if is_portfolio or abs(diff_ratio) <= SEARCH_RANGE:
                t_obj = yf.Ticker(ticker)
                e_date = fetch_earnings_date_safe(t_obj, today_date)
                
                earnings_str = "N/A"
                is_near = False
                
                if e_date:
                    earnings_str = e_date.strftime('%Y-%m-%d')
                    # 計算天數差距：0 到 7 天內亮紅燈
                    delta_days = (e_date - today_date).days
                    if 0 <= delta_days <= 7:
                        is_near = True

                passed.append({
                    "Symbol": ticker,
                    "Price": round(float(price), 2),
                    "Diff_Val": float(diff_ratio), 
                    "Diff_Str": f"{diff_ratio*100:+.2f}%",
                    "Earnings": earnings_str,
                    "Warning": is_near,      # 是否亮紅燈
                    "Is_Portfolio": is_portfolio, # 是否置頂
                    "Note": MY_PORTFOLIO.get(ticker, "")
                })
        except: continue

    # --- 排序邏輯修正 ---
    # 優先級 1: 是持股的排前面 (True 會排在 False 前面，所以用 not x['Is_Portfolio'])
    # 優先級 2: 偏離度由高到低
    passed.sort(key=lambda x: (not x['Is_Portfolio'], -x['Diff_Val']))
    
    # --- HTML 生成 ---
    rows = ""
    for x in passed:
        # 如果是持股，強制使用深色標頭；如果是財報週，標頭變紅
        if x['Is_Portfolio']:
            header_class = "bg-dark"
            p_tag = f'<span class="badge bg-warning text-dark ms-2">💰 持有中: {x["Note"]}</span>'
        elif x['Warning']:
            header_class = "bg-danger"
            p_tag = ""
        else:
            header_class = "bg-primary"
            p_tag = ""

        warning_tag = '<span class="badge bg-warning text-dark ms-2">⚠️ 近期財報</span>' if x['Warning'] else ""
        
        rows += f"""
        <div class="card mb-4 shadow border-0">
            <div class="card-header d-flex justify-content-between align-items-center {header_class} text-white">
                <h5 class="mb-0">{x['Symbol']}{p_tag}{warning_tag}</h5>
                <span class="badge bg-light text-dark">下次財報: {x['Earnings']}</span>
            </div>
            <div class="card-body">
                </div>
        </div>"""
    
    # ...寫入 index.html 的代碼保持不變...
