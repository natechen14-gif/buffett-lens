"""质量门（Gate 1）：巴菲特式盈利能力、稳健性、财务健康检查。"""

import statistics

import pandas as pd

from . import config as C
from . import tolerance as tol


def _to_map(series):
    return {pd.Timestamp(d): v for d, v in series}


def _linear(x, low, high):
    if x is None:
        return None
    if x >= high:
        return 1.0
    if x <= low:
        return 0.0
    return (x - low) / (high - low)


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _cv(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    m = _mean(vals)
    if not m:
        return None
    return statistics.stdev(vals) / m


def analyze_quality(bundle):
    vetoes = []
    items = []
    na_notes = []

    def add(name, value, sub, weight, unit="", note=""):
        status = "na" if sub is None else ("pass" if sub >= 0.7 else ("warn" if sub >= 0.4 else "fail"))
        items.append({"name": name, "value": value, "sub": sub, "weight": weight,
                      "unit": unit, "status": status, "note": note})

    # ---- ROE 水平 ----
    eq_map = _to_map(bundle["equity"])
    ni_map = _to_map(bundle["net_income"])
    eq_dates = sorted(eq_map.keys(), reverse=True)
    roes = []
    for i in range(len(eq_dates) - 1):
        d, prev = eq_dates[i], eq_dates[i + 1]
        ni = ni_map.get(d)
        eq_now, eq_prev = eq_map[d], eq_map[prev]
        if ni is None or eq_now is None or eq_prev is None:
            continue
        avg_eq = (eq_now + eq_prev) / 2
        if avg_eq > 0:
            roes.append(ni / avg_eq)
    avg_roe = _mean(roes)
    if avg_roe is None:
        add("ROE（平均权益）", None, None, C.ROE["weight"])
        na_notes.append("无足够权益/净利数据计算 ROE")
    else:
        if avg_roe < C.ROE["veto"]:
            vetoes.append(f"近5年平均 ROE {avg_roe:.1%} < 10%（质量红线）")
        note = "大规模回购会推高 ROE，需结合负债与稀释指标看" if avg_roe > 0.50 else ""
        add("ROE（平均权益）", avg_roe, _linear(avg_roe, C.ROE["veto"], C.ROE["excellent"]), C.ROE["weight"], "%", note)

    # ---- ROE 稳定性 ----
    if avg_roe is None or avg_roe <= 0:
        add("ROE 稳定性", None, None, C.ROE_STABILITY_WEIGHT)
        if avg_roe is not None and avg_roe <= 0:
            na_notes.append("亏损期 ROE 波动不具统计意义，已跳过稳定性项")
    else:
        cv_roe = _cv(roes)
        sub = min(1.0, max(0.0, 1 - cv_roe)) if cv_roe is not None else None
        add("ROE 稳定性", cv_roe, sub, C.ROE_STABILITY_WEIGHT, "CV")

    # ---- 净利率 ----
    rev_map = _to_map(bundle["revenue"])
    nm = [ni_map[d] / rev_map[d] for d in rev_map
          if rev_map[d] and ni_map.get(d) is not None and rev_map[d] != 0]
    mean_nm = _mean(nm)
    if mean_nm is None:
        add("净利率", None, None, C.NET_MARGIN["weight"])
        na_notes.append("无营收/净利数据计算净利率")
    else:
        add("净利率", mean_nm, _linear(mean_nm, C.NET_MARGIN["weak"], C.NET_MARGIN["strong"]),
            C.NET_MARGIN["weight"], "%")

    # ---- 毛利率 ----
    gp_map = _to_map(bundle["gross_profit"])
    gm = [gp_map[d] / rev_map[d] for d in rev_map
          if rev_map[d] and gp_map.get(d) is not None and rev_map[d] != 0]
    mean_gm = _mean(gm)
    if mean_gm is None:
        add("毛利率", None, None, C.GROSS_MARGIN["weight"])
        na_notes.append("无毛利率数据")
    else:
        add("毛利率", mean_gm, _linear(mean_gm, C.GROSS_MARGIN["weak"], C.GROSS_MARGIN["strong"]),
            C.GROSS_MARGIN["weight"], "%")

    # ---- EPS 一致性 ----
    eps_vals = [v for _, v in bundle["diluted_eps"]][:C.FISCAL_YEARS]
    if eps_vals:
        loss_years = sum(1 for v in eps_vals if v < 0)
        if loss_years >= C.EPS_VETO_LOSS_YEARS:
            vetoes.append(f"近{len(eps_vals)}年有 {loss_years} 个亏损年（质量红线）")
        sub = (len(eps_vals) - loss_years) / len(eps_vals)
        add("EPS 盈利一致性", f"{len(eps_vals)}年中{len(eps_vals) - loss_years}年盈利",
            sub, C.EPS_CONSISTENCY_WEIGHT)
    else:
        add("EPS 盈利一致性", None, None, C.EPS_CONSISTENCY_WEIGHT)
        na_notes.append("无 EPS 数据")

    # ---- 负债与利息覆盖 ----
    if tol.is_financial(bundle):
        add("负债水平 D/E", "跳过", None, C.DEBT["weight"], note="金融股资产负债表口径不同，负债类指标不适用")
        add("利息覆盖", "跳过", None, 0)
        na_notes.append("金融股：已跳过负债类指标")
    else:
        td_map = _to_map(bundle["total_debt"])
        td_latest = td_map[max(td_map.keys())] if td_map else None
        eq_latest = eq_map[max(eq_map.keys())] if eq_map else None
        de = td_latest / eq_latest if (td_latest is not None and eq_latest) else None
        oi_map = _to_map(bundle["operating_income"])
        ie_map = _to_map(bundle["interest_expense"])
        oi_latest = oi_map[max(oi_map.keys())] if oi_map else None
        ie_latest = ie_map[max(ie_map.keys())] if ie_map else None
        icr = oi_latest / ie_latest if (oi_latest is not None and ie_latest and ie_latest > 0) else None

        if de is not None and icr is not None and de > C.DEBT["veto_de"] and icr < C.DEBT["veto_icr"]:
            vetoes.append(f"D/E {de:.2f} 且利息覆盖 {icr:.1f}x，杠杆风险过高（质量红线）")
        de_sub = _linear(-de, -C.DEBT["veto_de"], -C.DEBT["good_de"]) if de is not None else None
        icr_sub = _linear(icr, C.DEBT["veto_icr"], C.DEBT["good_icr"]) if icr is not None else None
        if icr is None and ie_latest == 0:
            icr_sub = 1.0
        sub = None if (de_sub is None and icr_sub is None) else (_mean([de_sub, icr_sub]) or 0)
        de_disp = f"{de:.2f}" if de is not None else "NA"
        icr_disp = f"{icr:.1f}x" if icr is not None else "无利息"
        add("负债水平 D/E", de_disp, de_sub, C.DEBT["weight"])
        add("利息覆盖", icr_disp, icr_sub, 0)

    # ---- FCF 质量 ----
    if tol.is_financial(bundle):
        add("自由现金流", "跳过", None, C.FCF_WEIGHT, note="金融股现金流口径不同，不适用")
        na_notes.append("金融股：已跳过自由现金流指标")
    else:
        fcf_map = _to_map(bundle["fcf"])
        fcf_vals = sorted(fcf_map.items(), key=lambda t: t[0], reverse=True)[:C.FISCAL_YEARS]
        if fcf_vals:
            pos = sum(1 for _, v in fcf_vals if v > 0)
            latest_fcf = fcf_vals[0][1]
            mean5 = _mean([v for _, v in fcf_vals]) or 0
            if latest_fcf <= 0 and mean5 <= 0:
                vetoes.append("自由现金流持续为负（质量红线）")
            sub = pos / len(fcf_vals)
            add("自由现金流", f"{len(fcf_vals)}年中{pos}年为正", sub, C.FCF_WEIGHT)
        else:
            add("自由现金流", None, None, C.FCF_WEIGHT)
            na_notes.append("无自由现金流数据")

    # ---- 股本稀释 ----
    dsh = [v for _, v in bundle["diluted_shares"]][:C.FISCAL_YEARS]
    if len(dsh) >= 2 and dsh[0]:
        dilution = dsh[0] / dsh[-1] - 1
        if dilution > C.DILUTION_VETO:
            vetoes.append(f"股本近{len(dsh)}年扩张 {dilution:.1%} > 40%（质量红线）")
        sub = _linear(-dilution, -C.DILUTION_VETO, 0.0)
        add("股本稀释（回购为优）", f"{dilution:+.1%}", sub, C.DILUTION_WEIGHT)
    else:
        add("股本稀释", None, None, C.DILUTION_WEIGHT)
        na_notes.append("无股本历史数据")

    # ---- 加权汇总 ----
    wsum = sum(it["weight"] for it in items if it["sub"] is not None and it["weight"] > 0)
    score = None
    if wsum > 0:
        score = 100 * sum(it["sub"] * it["weight"] for it in items
                          if it["sub"] is not None and it["weight"] > 0) / wsum

    return {"score": score, "items": items, "vetoes": vetoes, "na_notes": na_notes}
