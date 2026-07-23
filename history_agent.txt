"""Background agent: fetches S&P500 tickers, computes MTD and YTD returns,
selects top-10 MTD performers, fetches additional metadata, and writes a cache JSON.

Run: python agent.py --interval 60
"""
import argparse
import json
import time
from datetime import datetime, timedelta, date
import math
import os
import logging

import pandas as pd
import requests
import yfinance as yf
import logging
import numpy as np
from io import StringIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache.json")


def get_sp500_tickers():
    """Read S&P 500 tickers from Wikipedia table."""
    logging.info("Fetching S&P 500 tickers from Wikipedia")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    # Use requests with a User-Agent header to avoid HTTP 403 from some hosts
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]
    except Exception:
        # Fallback to direct pandas reader if requests approach fails
        tables = pd.read_html(url)
        df = tables[0]
    symbols = df['Symbol'].tolist()
    # Some symbols contain dots (BRK.B) — yfinance expects BRK-B
    symbols = [s.replace('.', '-') for s in symbols]
    # Create dict symbol -> info
    ticker_info = {}
    for _, row in df.iterrows():
        sym = row['Symbol'].replace('.', '-')
        ticker_info[sym] = {
            'name': row['Security'],
            'sector': row['GICS Sector']
        }
    logging.info(f"Found {len(symbols)} tickers")
    return symbols, ticker_info


def get_dow_tickers():
    """Read DOW 30 tickers from Wikipedia table."""
    logging.info("Fetching DOW 30 tickers from Wikipedia")
    url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[1]  # The table with components
    except Exception:
        tables = pd.read_html(url)
        df = tables[1]
    symbols = df['Symbol'].tolist()
    symbols = [s.replace('.', '-') for s in symbols]
    logging.info(f"Found {len(symbols)} DOW tickers")
    return symbols


def get_nasdaq_tickers():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        tables = pd.read_html(url)
        # Find the table that contains ticker/symbol info dynamically
        df = None
        for table in tables:
            # Flatten columns if MultiIndex
            if isinstance(table.columns, pd.MultiIndex):
                table.columns = table.columns.get_level_values(-1)
            
            # Check for possible column names
            for col in ['Ticker', 'Symbol', 'Ticker symbol']:
                if col in table.columns:
                    df = table
                    ticker_col = col
                    break
            if df is not None:
                break

        if df is not None:
            symbols = df[ticker_col].tolist()
            symbols = [str(s).replace('.', '-') for s in symbols]
            logging.info(f"Found {len(symbols)} Nasdaq tickers")
            return symbols
        else:
            raise ValueError("Could not find Ticker/Symbol column in Wikipedia tables")

    except Exception as e:
        logging.error(f"Error fetching Nasdaq tickers: {e}")
        return []

def nearest_price_series(series, target_date):
    # series: pd.Series with datetime index
    # find first index >= target_date; if none, use earliest available
    idx = series.index
    later = idx[idx >= pd.to_datetime(target_date)]
    if len(later) > 0:
        return series.loc[later[0]]
    else:
        # If the target date is beyond the last available bar (e.g. Jan 1 holiday
        # before the first trading day), fall back to the most recent available
        # price rather than the earliest historical point.
        return series.iloc[-1]


def previous_price_series(series, target_date):
    idx = series.index
    earlier = idx[idx < pd.to_datetime(target_date)]
    if len(earlier) > 0:
        return series.loc[earlier[-1]]
    else:
        return series.iloc[0]


def _add_months(year, month, delta_months):
    m = (year * 12 + (month - 1)) + delta_months
    y2 = m // 12
    m2 = (m % 12) + 1
    return y2, m2


def compute_returns_for_tickers(tickers, history_days=400):
    """Download historical prices and compute last price, MTD and YTD returns, and 52-week high.
    Returns dict ticker->(last_price, mtd, qtd, ytd, week52_high)
    """
    logging.info("Downloading historical prices (this may take a bit)")
    # Use yfinance.multiticker download in batches to be efficient
    batch_size = 100
    results = {}
    end = None
    period = f'{history_days}d'
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        logging.info(f"Downloading batch {i}..{i+len(batch)}")
        try:
            data = yf.download(
                batch,
                period=period,
                interval='1d',
                group_by='ticker',
                threads=True,
                progress=False,
                auto_adjust=False,
            )
        except Exception as e:
            logging.warning(f"Download failed for batch: {e}")
            continue
        # data may be a multi-index or single ticker
        for t in batch:
            try:
                # yfinance returns a MultiIndex columns DataFrame when multiple tickers
                # are requested, and may also do so even when a single ticker is passed.
                if isinstance(getattr(data, 'columns', None), pd.MultiIndex):
                    try:
                        df = data.xs(t, axis=1, level=0, drop_level=True).copy()
                    except Exception:
                        df = data[t].copy() if t in data.columns.get_level_values(0) else pd.DataFrame()
                else:
                    df = data.copy()
                if df.empty:
                    continue
                close = df['Close'].dropna()
                if close.empty:
                    continue
                last_price = float(close.iloc[-1])
                vol = df['Volume'].dropna() if 'Volume' in df.columns else pd.Series(dtype=float)
                last_volume = None
                avg_volume_20d = None
                rel_volume_20d = None
                dollar_volume = None
                vol_z_60d = None
                if not vol.empty:
                    try:
                        last_volume = float(vol.iloc[-1])
                        dollar_volume = float(last_volume * last_price)
                        if len(vol) >= 2:
                            prior_vol = vol.iloc[:-1]
                            avg_volume_20d = float(prior_vol.tail(20).mean()) if len(prior_vol) else None
                            rel_volume_20d = (float(last_volume) / float(avg_volume_20d)) if avg_volume_20d and avg_volume_20d > 0 else None
                            v60 = prior_vol.tail(60) if len(prior_vol) >= 1 else prior_vol
                            v60_mean = float(v60.mean()) if len(v60) else None
                            v60_std = float(v60.std()) if len(v60) else None
                            vol_z_60d = ((float(last_volume) - float(v60_mean)) / float(v60_std)) if v60_mean is not None and v60_std and v60_std > 0 else None
                    except Exception:
                        last_volume = None
                        avg_volume_20d = None
                        rel_volume_20d = None
                        dollar_volume = None
                        vol_z_60d = None
                if len(close) >= 2:
                    lookback = close.tail(253) if len(close) >= 253 else close
                    prior = lookback.iloc[:-1]
                    week52_high = float(prior.tail(252).max()) if len(prior) >= 1 else None
                else:
                    week52_high = None

                today = pd.Timestamp(datetime.utcnow().date())
                first_of_month = pd.Timestamp(date(today.year, today.month, 1))
                quarter_start_month = ((today.month - 1) // 3) * 3 + 1
                first_of_quarter = pd.Timestamp(date(today.year, quarter_start_month, 1))
                jan_first = pd.Timestamp(date(today.year, 1, 1))

                if today.month == 1:
                    last_month_year = today.year - 1
                    last_month_month = 12
                else:
                    last_month_year = today.year
                    last_month_month = today.month - 1
                first_of_last_month = pd.Timestamp(date(last_month_year, last_month_month, 1))

                two_months_ago_year, two_months_ago_month = _add_months(last_month_year, last_month_month, -1)
                first_of_two_months_ago = pd.Timestamp(date(two_months_ago_year, two_months_ago_month, 1))
                
                three_months_ago_year, three_months_ago_month = _add_months(two_months_ago_year, two_months_ago_month, -1)
                first_of_three_months_ago = pd.Timestamp(date(three_months_ago_year, three_months_ago_month, 1))

                # Use the last available close BEFORE the period start date as the baseline.
                # This matches common market conventions for MTD/YTD when the first day of
                # the period is a holiday/weekend.
                price_mtd_start = previous_price_series(close, first_of_month)
                price_qtd_start = previous_price_series(close, first_of_quarter)
                price_ytd_start = previous_price_series(close, jan_first)

                price_last_month_start = previous_price_series(close, first_of_last_month)
                price_last_month_end = previous_price_series(close, first_of_month)

                price_two_months_ago_start = previous_price_series(close, first_of_two_months_ago)
                price_two_months_ago_end = previous_price_series(close, first_of_last_month)
                
                price_three_months_ago_start = previous_price_series(close, first_of_three_months_ago)
                price_three_months_ago_end = previous_price_series(close, first_of_two_months_ago)

                mtd = (last_price / float(price_mtd_start) - 1.0) if float(price_mtd_start) != 0 else None
                qtd = (last_price / float(price_qtd_start) - 1.0) if float(price_qtd_start) != 0 else None
                ytd = (last_price / float(price_ytd_start) - 1.0) if float(price_ytd_start) != 0 else None
                last_month = (float(price_last_month_end) / float(price_last_month_start) - 1.0) if float(price_last_month_start) != 0 else None
                two_months_ago = (float(price_two_months_ago_end) / float(price_two_months_ago_start) - 1.0) if float(price_two_months_ago_start) != 0 else None
                three_months_ago = (float(price_three_months_ago_end) / float(price_three_months_ago_start) - 1.0) if float(price_three_months_ago_start) != 0 else None

                # compute recent daily log-returns stats (use last 60 trading days when available)
                daily_ret = close.pct_change().dropna()
                if len(daily_ret) >= 10:
                    logr = np.log1p(daily_ret.tail(60))
                    mu = float(logr.mean())
                    sigma = float(logr.std())
                else:
                    mu = None
                    sigma = None

                results[t] = {
                    'last_price': last_price,
                    'mtd': None if mtd is None else float(mtd),
                    'qtd': None if qtd is None else float(qtd),
                    'ytd': None if ytd is None else float(ytd),
                    'last_month': None if last_month is None else float(last_month),
                    'two_months_ago': None if two_months_ago is None else float(two_months_ago),
                    'three_months_ago': None if three_months_ago is None else float(three_months_ago),
                    'week52_high': week52_high,
                    'mu': mu,
                    'sigma': sigma,
                    'volume': last_volume,
                    'avg_volume_20d': avg_volume_20d,
                    'rel_volume_20d': rel_volume_20d,
                    'dollar_volume': dollar_volume,
                    'vol_z_60d': vol_z_60d
                }
            except Exception as e:
                logging.debug(f"Error processing {t}: {e}")
                continue
    return results


def enrich_top10(top_tickers, ticker_info):
    """Fetch Ticker.info for top tickers to get sector and company info."""
    enriched = []
    for t in top_tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
        except Exception as e:
            logging.warning(f"Failed to fetch info for {t}: {e}")
            info = {}

        # Get name and sector from Wikipedia data
        wiki_info = ticker_info.get(t, {})
        long_name = wiki_info.get('name') or info.get('longName') or info.get('shortName') or t
        sector = wiki_info.get('sector') or info.get('sector')

        # collect useful financial fields safely
        financials = {
            'trailingPE': info.get('trailingPE'),
            'forwardPE': info.get('forwardPE'),
            'enterpriseValue': info.get('enterpriseValue'),
            'ebitda': info.get('ebitda'),
            'profitMargins': info.get('profitMargins'),
            'grossMargins': info.get('grossMargins'),
            'totalRevenue': info.get('totalRevenue') or info.get('revenue'),
            'earningsQuarterlyGrowth': info.get('earningsQuarterlyGrowth'),
            'beta': info.get('beta'),
            'dividendYield': info.get('dividendYield') or info.get('dividendRate'),
            'targetMeanPrice': info.get('targetMeanPrice')
        }

        entry = {
            'symbol': t,
            'longName': long_name,
            'sector': sector,
            'industry': info.get('industry'),
            # 'marketCap' intentionally omitted (not collected/displayed)
            'website': info.get('website'),
            'summary': info.get('longBusinessSummary'),
            'financials': financials,
            'info': info
        }
        enriched.append(entry)
    return enriched


def project_price(last_price, mu, sigma, days, z=1.2816):
    """Return median, low(10th) and high(90th) projected pct changes for horizon in trading days.
    Uses geometric Brownian motion log-return approximation: log-return ~ N(mu*days, sigma*sqrt(days)).
    Returns dict with pct values (e.g., 0.05 = +5%)."""
    if mu is None or sigma is None:
        return {'med_pct': None, 'low_pct': None, 'high_pct': None, 'med_price': None, 'low_price': None, 'high_price': None}
    mu_d = mu * days
    sd_d = sigma * (days ** 0.5)
    med_factor = math.exp(mu_d)
    low_factor = math.exp(mu_d - z * sd_d)
    high_factor = math.exp(mu_d + z * sd_d)
    med_price = last_price * med_factor
    low_price = last_price * low_factor
    high_price = last_price * high_factor
    return {
        'med_pct': med_price / last_price - 1.0,
        'low_pct': low_price / last_price - 1.0,
        'high_pct': high_price / last_price - 1.0,
        'med_price': med_price,
        'low_price': low_price,
        'high_price': high_price
    }


def compute_sector_favor(returns_dict, ticker_info):
    """Compute average MTD per sector across available tickers and return mapping sector->in_favor boolean.
    A sector is 'in favor' if its average MTD is greater than the median sector MTD."""
    sector_map = {}
    for t, vals in returns_dict.items():
        sector = ticker_info.get(t, {}).get('sector')
        if not sector:
            continue
        mtd = vals.get('mtd')
        if mtd is None or mtd != mtd:
            continue
        sector_map.setdefault(sector, []).append(mtd)
    sector_avg = {s: (float(np.mean(v)) if len(v) else 0.0) for s, v in sector_map.items()}
    if not sector_avg:
        return {}
    med = float(np.median(list(sector_avg.values())))
    return {s: {'avg_mtd': avg, 'in_favor': (avg > med)} for s, avg in sector_avg.items()}


def compute_sector_performance(returns_dict, ticker_info):
    """Compute avg MTD/QTD/YTD per sector across all available tickers."""
    bucket = {}
    for t, vals in returns_dict.items():
        sector = ticker_info.get(t, {}).get('sector')
        if not sector:
            continue

        rec = bucket.setdefault(sector, {'mtd': [], 'qtd': [], 'ytd': []})
        for k in ['mtd', 'qtd', 'ytd']:
            v = vals.get(k)
            if v is None:
                continue
            try:
                fv = float(v)
                if fv != fv:
                    continue
                rec[k].append(fv)
            except Exception:
                continue

    out = []
    for sector, vals in bucket.items():
        m = vals.get('mtd', [])
        q = vals.get('qtd', [])
        y = vals.get('ytd', [])
        out.append({
            'sector': sector,
            'avg_mtd': float(np.mean(m)) if len(m) else None,
            'avg_qtd': float(np.mean(q)) if len(q) else None,
            'avg_ytd': float(np.mean(y)) if len(y) else None,
            'count': int(max(len(m), len(q), len(y)))
        })
    out.sort(key=lambda r: (r['avg_mtd'] if r.get('avg_mtd') is not None else -1e9), reverse=True)
    return out


def compute_breakouts(returns_dict, top_n=10):
    """Compute top breakouts: stocks where last_price > 52_week_high, sorted by breakout pct desc."""
    breakouts = []
    for t, vals in returns_dict.items():
        last_price = vals.get('last_price')
        week52_high = vals.get('week52_high')
        if last_price is None or week52_high is None:
            continue
        if week52_high and last_price >= week52_high:
            breakout_pct = (last_price / week52_high) - 1.0
            breakouts.append({
                'symbol': t,
                'breakout_pct': breakout_pct,
                'last_price': last_price,
                'week52_high': week52_high,
                'volume': vals.get('volume'),
                'avg_volume_20d': vals.get('avg_volume_20d'),
                'rel_volume_20d': vals.get('rel_volume_20d'),
                'dollar_volume': vals.get('dollar_volume'),
                'vol_z_60d': vals.get('vol_z_60d')
            })
    # sort by breakout_pct desc
    breakouts.sort(key=lambda x: x['breakout_pct'], reverse=True)
    return breakouts[:top_n]


def enrich_breakouts(breakout_list, sector_map=None, ticker_info=None):
    """Fetch Ticker.info for breakout tickers to get sector and company info."""
    enriched = []
    for item in breakout_list:
        t = item['symbol']
        wiki_info = ticker_info.get(t, {}) if ticker_info else {}
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
        except Exception as e:
            logging.warning(f"Failed to fetch info for {t}: {e}")
            info = {}

        long_name = wiki_info.get('name') or info.get('longName') or info.get('shortName') or t
        sector = wiki_info.get('sector') or info.get('sector')

        enriched_item = item.copy()
        enriched_item.update({
            'longName': long_name,
            'sector': sector,
            'industry': info.get('industry'),
            'sector_in_favor': sector_map.get(sector, {}).get('in_favor', False) if sector_map and sector else False
        })
        enriched.append(enriched_item)
    return enriched


def write_cache(
    data,
    breakouts_sp500,
    breakouts_dow,
    breakouts_nasdaq,
    sector_performance=None,
    last_month_top10=None,
    last_month_year=None,
    last_month_month=None,
    two_months_ago_top10=None,
    two_months_ago_year=None,
    two_months_ago_month=None,
    three_months_ago_top10=None,
    three_months_ago_year=None,
    three_months_ago_month=None,
):
    payload = {
        'last_updated_utc': datetime.utcnow().isoformat() + 'Z',
        'data': data,
        'breakouts': {
            'sp500': breakouts_sp500,
            'dow': breakouts_dow,
            'nasdaq': breakouts_nasdaq
        },
        'sector_performance': sector_performance or [],
        'last_month_top10': last_month_top10 or [],
        'last_month_year': last_month_year,
        'last_month_month': last_month_month,
        'two_months_ago_top10': two_months_ago_top10 or [],
        'two_months_ago_year': two_months_ago_year,
        'two_months_ago_month': two_months_ago_month,
        'three_months_ago_top10': three_months_ago_top10 or [],
        'three_months_ago_year': three_months_ago_year,
        'three_months_ago_month': three_months_ago_month
    }
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    logging.info(f"Wrote cache to {CACHE_FILE}")


def run_loop(interval_seconds=60):
    sp500_tickers, ticker_info = get_sp500_tickers()
    dow_tickers = get_dow_tickers()
    nasdaq_tickers = get_nasdaq_tickers()
    while True:
        try:
            returns_sp500 = compute_returns_for_tickers(sp500_tickers)
            returns_dow = compute_returns_for_tickers(dow_tickers)
            returns_nasdaq = compute_returns_for_tickers(nasdaq_tickers)
            
            # Filter only tickers with mtd value for top10
            filtered = {t: v for t, v in returns_sp500.items() if v.get('mtd') is not None and not math.isnan(v.get('mtd'))}
            # sort by mtd desc
            sorted_by_mtd = sorted(filtered.items(), key=lambda kv: kv[1]['mtd'], reverse=True)
            top10 = sorted_by_mtd[:10]
            top10_symbols = [t for t, v in top10]
            # compute sector favor across available tickers
            sector_map = compute_sector_favor(returns_sp500, ticker_info)
            sector_performance = compute_sector_performance(returns_sp500, ticker_info)
            enriched = enrich_top10(top10_symbols, ticker_info)
            # prepare final list with financials and projections
            final = []
            for (t, vals), meta in zip(top10, enriched):
                mu = vals.get('mu')
                sigma = vals.get('sigma')
                last_price = vals.get('last_price')
                proj_1m = project_price(last_price, mu, sigma, 21)
                proj_3m = project_price(last_price, mu, sigma, 63)
                proj_6m = project_price(last_price, mu, sigma, 126)

                fin = meta.get('financials', {})

                entry = {
                    'symbol': t,
                    'last_price': last_price,
                    'mtd': vals['mtd'],
                    'qtd': vals.get('qtd'),
                    'ytd': vals['ytd'],
                    'mu': mu,
                    'sigma': sigma,
                    'volume': vals.get('volume'),
                    'avg_volume_20d': vals.get('avg_volume_20d'),
                    'rel_volume_20d': vals.get('rel_volume_20d'),
                    'dollar_volume': vals.get('dollar_volume'),
                    'vol_z_60d': vals.get('vol_z_60d'),
                    'longName': meta.get('longName'),
                    'sector': meta.get('sector'),
                    'industry': meta.get('industry'),
                    # 'marketCap' removed per request
                    'website': meta.get('website'),
                    'summary': (meta.get('summary')[:500] + '...') if meta.get('summary') else None,
                    # common financials
                    'trailingPE': fin.get('trailingPE'),
                    'forwardPE': fin.get('forwardPE'),
                    'enterpriseValue': fin.get('enterpriseValue'),
                    'ebitda': fin.get('ebitda'),
                    'totalRevenue': fin.get('totalRevenue'),
                    'profitMargins': fin.get('profitMargins'),
                    'grossMargins': fin.get('grossMargins'),
                    'earningsQuarterlyGrowth': fin.get('earningsQuarterlyGrowth'),
                    'beta': fin.get('beta'),
                    'dividendYield': fin.get('dividendYield'),
                    'targetMeanPrice': fin.get('targetMeanPrice'),
                    # projections
                    'proj_1m_med_pct': proj_1m['med_pct'],
                    'proj_1m_low_pct': proj_1m['low_pct'],
                    'proj_1m_high_pct': proj_1m['high_pct'],
                    'proj_3m_med_pct': proj_3m['med_pct'],
                    'proj_3m_low_pct': proj_3m['low_pct'],
                    'proj_3m_high_pct': proj_3m['high_pct'],
                    'proj_6m_med_pct': proj_6m['med_pct'],
                    'proj_6m_low_pct': proj_6m['low_pct'],
                    'proj_6m_high_pct': proj_6m['high_pct'],
                    # buy/sell suggestions (buy at 1-month low, sell at 6-month high for max gain)
                    'buy_price': proj_1m.get('low_price'),
                    'sell_price': proj_6m.get('high_price'),
                    'expected_gain_pct': None if proj_1m.get('low_price') is None or proj_6m.get('high_price') is None else (proj_6m.get('high_price') / proj_1m.get('low_price') - 1.0),
                    # sector favor
                    'sector_in_favor': sector_map.get(meta.get('sector'), {}).get('in_favor', False),
                    'sector_avg_mtd': sector_map.get(meta.get('sector'), {}).get('avg_mtd') if meta.get('sector') else None
                }
                final.append(entry)

            filtered_lm = {t: v for t, v in returns_sp500.items() if v.get('last_month') is not None and not math.isnan(v.get('last_month'))}
            sorted_by_lm = sorted(filtered_lm.items(), key=lambda kv: kv[1]['last_month'], reverse=True)
            top10_lm = sorted_by_lm[:10]
            top10_lm_symbols = [t for t, _ in top10_lm]
            enriched_lm = enrich_top10(top10_lm_symbols, ticker_info)
            last_month_top10 = []
            for (t, vals), meta in zip(top10_lm, enriched_lm):
                last_month_top10.append({
                    'symbol': t,
                    'longName': meta.get('longName'),
                    'sector': meta.get('sector'),
                    'industry': meta.get('industry'),
                    'last_price': vals.get('last_price'),
                    'last_month': vals.get('last_month'),
                    'mtd': vals.get('mtd'),
                    'ytd': vals.get('ytd'),
                    'volume': vals.get('volume'),
                    'avg_volume_20d': vals.get('avg_volume_20d'),
                    'rel_volume_20d': vals.get('rel_volume_20d'),
                    'dollar_volume': vals.get('dollar_volume'),
                    'vol_z_60d': vals.get('vol_z_60d')
                })

            filtered_2m = {t: v for t, v in returns_sp500.items() if v.get('two_months_ago') is not None and not math.isnan(v.get('two_months_ago'))}
            sorted_by_2m = sorted(filtered_2m.items(), key=lambda kv: kv[1]['two_months_ago'], reverse=True)
            top10_2m = sorted_by_2m[:10]
            top10_2m_symbols = [t for t, _ in top10_2m]
            enriched_2m = enrich_top10(top10_2m_symbols, ticker_info)
            two_months_ago_top10 = []
            for (t, vals), meta in zip(top10_2m, enriched_2m):
                two_months_ago_top10.append({
                    'symbol': t,
                    'longName': meta.get('longName'),
                    'sector': meta.get('sector'),
                    'industry': meta.get('industry'),
                    'last_price': vals.get('last_price'),
                    'two_months_ago': vals.get('two_months_ago'),
                    'last_month': vals.get('last_month'),
                    'mtd': vals.get('mtd'),
                    'ytd': vals.get('ytd'),
                    'volume': vals.get('volume'),
                    'avg_volume_20d': vals.get('avg_volume_20d'),
                    'rel_volume_20d': vals.get('rel_volume_20d'),
                    'dollar_volume': vals.get('dollar_volume'),
                    'vol_z_60d': vals.get('vol_z_60d')
                })

            filtered_3m = {t: v for t, v in returns_sp500.items() if v.get('three_months_ago') is not None and not math.isnan(v.get('three_months_ago'))}
            sorted_by_3m = sorted(filtered_3m.items(), key=lambda kv: kv[1]['three_months_ago'], reverse=True)
            top10_3m = sorted_by_3m[:10]
            top10_3m_symbols = [t for t, _ in top10_3m]
            enriched_3m = enrich_top10(top10_3m_symbols, ticker_info)
            three_months_ago_top10 = []
            for (t, vals), meta in zip(top10_3m, enriched_3m):
                three_months_ago_top10.append({
                    'symbol': t,
                    'longName': meta.get('longName'),
                    'sector': meta.get('sector'),
                    'industry': meta.get('industry'),
                    'last_price': vals.get('last_price'),
                    'three_months_ago': vals.get('three_months_ago'),
                    'last_month': vals.get('last_month'),
                    'mtd': vals.get('mtd'),
                    'ytd': vals.get('ytd'),
                    'volume': vals.get('volume'),
                    'avg_volume_20d': vals.get('avg_volume_20d'),
                    'rel_volume_20d': vals.get('rel_volume_20d'),
                    'dollar_volume': vals.get('dollar_volume'),
                    'vol_z_60d': vals.get('vol_z_60d')
                })
            
            # Compute breakouts
            breakouts_sp500 = compute_breakouts(returns_sp500)
            breakouts_dow = compute_breakouts(returns_dow)
            breakouts_nasdaq = compute_breakouts(returns_nasdaq)
            
            # Enrich breakouts with metadata
            breakouts_sp500 = enrich_breakouts(breakouts_sp500, sector_map, ticker_info)
            breakouts_dow = enrich_breakouts(breakouts_dow, sector_map, ticker_info)
            breakouts_nasdaq = enrich_breakouts(breakouts_nasdaq, sector_map, ticker_info)
            
            today = datetime.utcnow().date()
            if today.month == 1:
                last_month_year = today.year - 1
                last_month_month = 12
            else:
                last_month_year = today.year
                last_month_month = today.month - 1
            two_months_ago_year, two_months_ago_month = _add_months(last_month_year, last_month_month, -1)
            three_months_ago_year, three_months_ago_month = _add_months(two_months_ago_year, two_months_ago_month, -1)

            write_cache(
                final,
                breakouts_sp500,
                breakouts_dow,
                breakouts_nasdaq,
                sector_performance=sector_performance,
                last_month_top10=last_month_top10,
                last_month_year=last_month_year,
                last_month_month=last_month_month,
                two_months_ago_top10=two_months_ago_top10,
                two_months_ago_year=two_months_ago_year,
                two_months_ago_month=two_months_ago_month,
                three_months_ago_top10=three_months_ago_top10,
                three_months_ago_year=three_months_ago_year,
                three_months_ago_month=three_months_ago_month,
            )
        except Exception as e:
            logging.exception(f"Error in update loop: {e}")
        logging.info(f"Sleeping {interval_seconds} seconds until next update")
        time.sleep(interval_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=60, help='Update interval in seconds')
    args = parser.parse_args()
    logging.info("Starting S&P top10 agent")
    run_loop(args.interval)
