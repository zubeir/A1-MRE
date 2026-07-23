"""Run a single agent update and write cache.json once.
This is useful for quick verification without running the continuous agent loop.
"""
from datetime import datetime, date
import json
import math
import os

from agent import get_sp500_tickers, get_dow_tickers, get_nasdaq_tickers, compute_returns_for_tickers, enrich_top10, write_cache, compute_sector_favor, compute_sector_performance, project_price, compute_breakouts, enrich_breakouts


def _add_months(year, month, delta_months):
    m = (year * 12 + (month - 1)) + delta_months
    y2 = m // 12
    m2 = (m % 12) + 1
    return y2, m2

if __name__ == '__main__':
    print('Starting one-shot update')
    sp500_ticks, ticker_info = get_sp500_tickers()
    dow_ticks = get_dow_tickers()
    nasdaq_ticks = get_nasdaq_tickers()
    returns_sp500 = compute_returns_for_tickers(sp500_ticks)
    returns_dow = compute_returns_for_tickers(dow_ticks)
    returns_nasdaq = compute_returns_for_tickers(nasdaq_ticks)
    filtered = {t: v for t, v in returns_sp500.items() if v.get('mtd') is not None and not math.isnan(v.get('mtd'))}
    sorted_by_mtd = sorted(filtered.items(), key=lambda kv: kv[1]['mtd'], reverse=True)
    top10 = sorted_by_mtd[:10]
    top10_symbols = [t for t, v in top10]
    # compute sector favor across available returns
    sector_map = compute_sector_favor(returns_sp500, ticker_info)
    sector_performance = compute_sector_performance(returns_sp500, ticker_info)
    enriched = enrich_top10(top10_symbols, ticker_info)
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
            'last_month': vals.get('last_month'),
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
            'proj_1m_med_pct': proj_1m['med_pct'],
            'proj_1m_low_pct': proj_1m['low_pct'],
            'proj_1m_high_pct': proj_1m['high_pct'],
            'proj_3m_med_pct': proj_3m['med_pct'],
            'proj_3m_low_pct': proj_3m['low_pct'],
            'proj_3m_high_pct': proj_3m['high_pct'],
            'proj_6m_med_pct': proj_6m['med_pct'],
            'proj_6m_low_pct': proj_6m['low_pct'],
            'proj_6m_high_pct': proj_6m['high_pct'],
            'buy_price': proj_1m.get('low_price'),
            'sell_price': proj_6m.get('high_price'),
            'expected_gain_pct': None if proj_1m.get('low_price') is None or proj_6m.get('high_price') is None else (proj_6m.get('high_price') / proj_1m.get('low_price') - 1.0),
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
    
    # Enrich breakouts
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
    print('One-shot update completed, cache written.')
