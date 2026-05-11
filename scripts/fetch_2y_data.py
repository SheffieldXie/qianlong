"""获取过去2年 XAUUSD 日线数据"""
import yfinance as yf
import pandas as pd
import os

cache_dir = os.path.join(os.path.dirname(__file__), "../data/cache")
os.makedirs(cache_dir, exist_ok=True)

for ticker in ["GC=F", "XAUUSD=X"]:
    try:
        gold = yf.Ticker(ticker)
        df = gold.history(period="2y", interval="1d")
        if df is not None and not df.empty and len(df) > 200:
            df = df.reset_index()
            df.columns = [c.lower().replace(' ', '_') for c in df.columns]
            if 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'date'})
            elif 'date' not in df.columns:
                df = df.rename(columns={df.columns[0]: 'date'})

            col_map = {}
            for c in df.columns:
                cl = c.lower()
                if 'open' in cl: col_map[c] = 'open'
                elif 'high' in cl: col_map[c] = 'high'
                elif 'low' in cl: col_map[c] = 'low'
                elif 'close' in cl: col_map[c] = 'close'
                elif 'volume' in cl: col_map[c] = 'volume'
                elif 'date' in cl or 'time' in cl: col_map[c] = 'date'

            df = df.rename(columns=col_map)
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)

            cache_path = os.path.join(cache_dir, "xauusd_2y_1d.pkl")
            df.to_pickle(cache_path)

            print(f"OK: {len(df)} daily bars from {ticker}")
            print(f"Range: {df.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
            print(f"Price: ${df['close'].min():.2f} ~ ${df['close'].max():.2f}")
            break
    except Exception as e:
        print(f"{ticker} failed: {e}")
        continue
