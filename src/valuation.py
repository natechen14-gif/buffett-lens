"""估值门（Gate 2）：owner earnings DCF、Earnings yield vs 10Y、历史估值分位。"""

import pandas as pd

from . import config as C
from .data import price_at_date


def _to_map(series):
    return {pd.Timestamp(d): v for d, v in series}


def _net_cash(bundle):
    cash_map = _to_map(bundle["cash"])
    td_map = _to_map(bundle["total_debt"])
    cash = cash_map[max(cash_map.keys())] if cash_map else None
    td = td_map[max(td_map.keys())] if td_map else None
    if cash is None and td is None:
        return 0.0
    return max(0.0, (cash or 0) - (td or 0))


def analyze_valuation(bundle, quality_score):
    price = bundle["current_price"]
    shares = bundle["shares_outstanding"]
    result = {"dcf": None, "ey": None, "fcf_yield": None, "percentiles": {}, "score": None}
    if not price or not shares:
        return result

    # ---- 基础 FCF0 ----
    fcf0 = bundle["ttm_fcf"]
    if fcf0 is None or fcf0 <= 0:
        pos_vals = [v for _, v in _to_map(bundle["fcf"]).items() if v and v > 0][:3]
        fcf0 = sum(pos_vals) / len(pos_vals) if pos_vals else None

    # ---- DCF（owner earnings 两阶段）----
    if fcf0 and shares:
        fcf_map = _to_map(bundle["fcf"])
        fvals = [v for _, v in sorted(fcf_map.items(), key=lambda t: t[0], reverse=True)][:5]
        if len(fvals) >= 2 and fvals[0] > 0 and fvals[-1] > 0:
            g1 = (fvals[0] / fvals[-1]) ** (1 / (len(fvals) - 1)) - 1
        else:
            g1 = 0.02
        g1 = max(0.0, min(C.MAX_GROWTH, g1))
        r = C.DISCOUNT_RATE["high_quality"] if quality_score is not None and quality_score >= 80 \
            else C.DISCOUNT_RATE["normal"]
        g2 = C.PERPETUAL_GROWTH
        if r <= g2:
            r = g2 + 0.05
        pv = sum(fcf0 * (1 + g1) ** t / (1 + r) ** t for t in range(1, 6))
        fcf5 = fcf0 * (1 + g1) ** 5
        tv = fcf5 * (1 + g2) / (r - g2)
        ev = pv + tv / (1 + r) ** 5
        iv_share = (ev + _net_cash(bundle)) / shares
        mos = iv_share / price - 1
        result["dcf"] = {"iv_share": iv_share, "mos": mos, "fcf0": fcf0,
                         "g1": g1, "r": r, "net_cash": _net_cash(bundle)}

    # ---- Earnings yield vs 10Y ----
    eps = bundle["trailing_eps"]
    tnx = bundle.get("tnx_yield") or 0.045
    if eps and eps > 0:
        ey = eps / price
        result["ey"] = {"ey": ey, "spread": ey - tnx, "tnx": tnx}

    # ---- FCF yield ----
    if fcf0 and bundle["market_cap"]:
        result["fcf_yield"] = fcf0 / bundle["market_cap"]

    # ---- 价格分位 ----
    close = bundle["close"]
    if close is not None and len(close):
        mn, mx = float(close.min()), float(close.max())
        if mx > mn:
            result["percentiles"]["price_10y"] = (price - mn) / (mx - mn)
        hi, lo = bundle["fifty_two_week_high"], bundle["fifty_two_week_low"]
        if hi and lo and hi > lo:
            result["percentiles"]["pct_52w"] = (price - lo) / (hi - lo)

    # ---- 估值分位（年报样本）----
    eps_map = _to_map(bundle["diluted_eps"])
    eq_map = _to_map(bundle["equity"])
    fcf_map = _to_map(bundle["fcf"])
    dsh_map = _to_map(bundle["diluted_shares"])
    hist_groups = {}
    for d in sorted(eps_map.keys(), reverse=True)[:6]:
        p = price_at_date(close, d)
        if p is None or p <= 0:
            continue
        eps_i = eps_map.get(d)
        if eps_i and eps_i > 0:
            hist_groups.setdefault("PE", []).append(p / eps_i)
        sh_i = dsh_map.get(d) or shares
        eq_i = eq_map.get(d)
        if eq_i and sh_i and eq_i > 0:
            hist_groups.setdefault("PB", []).append(p / (eq_i / sh_i))
        f_i = fcf_map.get(d)
        if f_i and f_i > 0 and sh_i:
            hist_groups.setdefault("PFCF", []).append(p / (f_i / sh_i))

    cur_multiples = {}
    if eps and eps > 0:
        cur_multiples["PE"] = price / eps
    eq_latest = eq_map[max(eq_map.keys())] if eq_map else None
    if eq_latest and eq_latest > 0:
        cur_multiples["PB"] = price / (eq_latest / shares)
    if fcf0:
        cur_multiples["PFCF"] = price / (fcf0 / shares)

    ranks = []
    for kind, hist_vals in hist_groups.items():
        if kind in cur_multiples:
            ranks.append(sum(1 for v in hist_vals if v <= cur_multiples[kind]) / len(hist_vals))
    if ranks:
        result["percentiles"]["val_pct"] = sum(ranks) / len(ranks)
        result["percentiles"]["val_sample_n"] = len(hist_groups)
        result["percentiles"]["insufficient"] = False
    else:
        result["percentiles"]["insufficient"] = True

    # ---- 估值评分 ----
    comps, ws = [], []
    if result["dcf"] and result["dcf"]["mos"] is not None:
        comps.append(max(0.0, min(1.0, result["dcf"]["mos"] / C.DCF_DISCOUNT_NORM)))
        ws.append(0.40)
    if result["ey"] and result["ey"]["spread"] is not None:
        comps.append(max(0.0, min(1.0, result["ey"]["spread"] / C.EY_ATTRACTIVE_SPREAD)))
        ws.append(0.25)
    if not result["percentiles"].get("insufficient"):
        vp = result["percentiles"].get("val_pct")
        if vp is not None:
            comps.append(max(0.0, min(1.0, 1 - vp)))
            ws.append(0.20)
    if result["fcf_yield"] is not None:
        comps.append(max(0.0, min(1.0, result["fcf_yield"] / C.FCF_YIELD_TARGET)))
        ws.append(0.15)
    if ws:
        result["score"] = 100 * sum(c * w for c, w in zip(comps, ws)) / sum(ws)

    return result
