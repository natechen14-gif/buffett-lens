"""yfinance 抓取层：字段别名回退、判空降级、打包为统一数据结构。"""

import pandas as pd
import yfinance as yf


def safe_get(df, aliases, col=0):
    if df is None or df.empty:
        return None
    for a in aliases:
        if a in df.index:
            v = df.iloc[df.index.get_loc(a), col]
            if pd.notna(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
    return None


def series_from_df(df, aliases, n=6):
    """返回 [(财年截止日, 数值)]，最新财年在前。"""
    if df is None or df.empty:
        return []
    for a in aliases:
        if a in df.index:
            items = []
            for col in df.columns:
                v = df.loc[a, col]
                if pd.notna(v):
                    try:
                        items.append((pd.Timestamp(col), float(v)))
                    except (TypeError, ValueError):
                        continue
            items.sort(key=lambda t: t[0], reverse=True)
            return items[:n]
    return []


def price_at_date(close, d):
    if close is None or len(close) == 0:
        return None
    d = pd.Timestamp(d)
    idx = close.index
    ci = idx.tz_localize(None).normalize() if getattr(idx, "tz", None) is not None else idx.normalize()
    pos = ci.searchsorted(d, side="right") - 1
    if pos < 0:
        return None
    return float(close.iloc[pos])


def _safe_df(fn):
    try:
        df = fn()
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    return pd.DataFrame()


def fetch_tnx_yield():
    """^TNX 收益率。Yahoo 新格式直接给百分数，旧格式为 ×10，做判别。失败回退 4.5%。"""
    try:
        h = yf.Ticker("^TNX").history(period="5d")
        raw = float(h["Close"].dropna().iloc[-1])
        pct = raw / 10 if raw > 10 else raw
        return pct / 100
    except Exception:
        return 0.045


def _combine_debt(bundle):
    td = bundle["total_debt"]
    if td:
        return td
    ltd = {pd.Timestamp(d): v for d, v in bundle["long_term_debt"]}
    cd = {pd.Timestamp(d): v for d, v in bundle["current_debt"]}
    dates = sorted(set(ltd) | set(cd), reverse=True)
    out = []
    for d in dates:
        v = (ltd.get(d) or 0) + (cd.get(d) or 0)
        if v:
            out.append((d, v))
    return out


def fetch_bundle(symbol):
    symbol = str(symbol).strip().upper()
    tk = yf.Ticker(symbol)

    info = {}
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    hist = _safe_df(lambda: tk.history(period="10y", auto_adjust=True))
    if hist.empty:
        hist = _safe_df(lambda: tk.history(period="5y", auto_adjust=True))
    close = hist["Close"] if not hist.empty else None

    income = _safe_df(lambda: tk.income_stmt)
    balance = _safe_df(lambda: tk.balance_sheet)
    cashflow = _safe_df(lambda: tk.cashflow)
    ttm_cf = _safe_df(lambda: tk.ttm_cashflow)
    ttm_income = _safe_df(lambda: tk.ttm_income_stmt)

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not current_price:
        try:
            current_price = tk.fast_info["last_price"]
        except Exception:
            current_price = None
    if not current_price and close is not None and len(close):
        current_price = float(close.iloc[-1])

    shares = info.get("sharesOutstanding")
    if not shares:
        try:
            shares = tk.fast_info.get("shares")
        except Exception:
            shares = None

    equity = series_from_df(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                      "Total Stockholder Equity", "Common Stock Equity"])

    bundle = {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"),
        "quote_type": info.get("quoteType"),
        "current_price": current_price,
        "market_cap": info.get("marketCap"),
        "shares_outstanding": shares,
        "trailing_eps": info.get("trailingEps"),
        "trailing_pe": info.get("trailingPE"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "close": close,
        "tnx_yield": fetch_tnx_yield(),
        "revenue": series_from_df(income, ["Total Revenue", "Operating Revenue"]),
        "gross_profit": series_from_df(income, ["Gross Profit"]),
        "operating_income": series_from_df(income, ["Operating Income", "EBIT"]),
        "net_income": series_from_df(income, ["Net Income", "Net Income Common Stockholders"]),
        "interest_expense": series_from_df(income, ["Interest Expense", "Interest Expense Non Operating"]),
        "diluted_eps": series_from_df(income, ["Diluted EPS", "Basic EPS"]),
        "diluted_shares": series_from_df(income, ["Diluted Average Shares",
                                                  "Diluted Weighted Average Shares", "Basic Average Shares"]),
        "equity": equity,
        "total_debt": series_from_df(balance, ["Total Debt"]),
        "long_term_debt": series_from_df(balance, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]),
        "current_debt": series_from_df(balance, ["Current Debt", "Current Debt And Capital Lease Obligation"]),
        "cash": series_from_df(balance, ["Cash And Cash Equivalents",
                                         "Cash Cash Equivalents And Short Term Investments"]),
        "ocf": series_from_df(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
        "capex": series_from_df(cashflow, ["Capital Expenditure", "Capital Expenditures"]),
        "fcf": series_from_df(cashflow, ["Free Cash Flow"]),
        "ttm_fcf": safe_get(ttm_cf, ["Free Cash Flow"]),
    }

    bundle["total_debt"] = _combine_debt(bundle)

    # 若 FCF 行缺失，用 OCF - capex 补算（capEx 在 Yahoo 为负值）
    if not bundle["fcf"] and bundle["ocf"] and bundle["capex"]:
        ocf = dict(bundle["ocf"])
        cap = dict(bundle["capex"])
        dates = sorted(set(ocf) & set(cap), reverse=True)
        bundle["fcf"] = [(d, ocf[d] + cap[d]) for d in dates]
    if bundle["ttm_fcf"] is None:
        ocf_t = safe_get(ttm_cf, ["Operating Cash Flow"])
        cap_t = safe_get(ttm_cf, ["Capital Expenditure"])
        if ocf_t is not None and cap_t is not None:
            bundle["ttm_fcf"] = ocf_t + cap_t

    return bundle
