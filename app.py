import streamlit as st
import pandas as pd

from src import data, decision, quality as qmod, tolerance as tol, valuation as vmod
from src import config as C

st.set_page_config(page_title="Buffett Lens · 个股建仓判断", page_icon="🐂", layout="centered")

st.title("🐂 巴菲特视角 · 个股建仓判断")
st.caption("输入美股 / A股 / 港股代码，立刻判断「现在能不能建仓」——质量门槛 + 安全边际 + 建议买入价 + 公司介绍。")

SECTOR_CN = {
    "Technology": "科技", "Consumer Defensive": "必需消费", "Consumer Cyclical": "可选消费",
    "Healthcare": "医疗保健", "Financial Services": "金融", "Industrials": "工业",
    "Energy": "能源", "Utilities": "公用事业", "Communication Services": "通信服务",
    "Real Estate": "房地产", "Basic Materials": "基础材料",
}


def sector_cn(name):
    return SECTOR_CN.get(name or "", name or "")


QUOTES = {
    "green": "「用四毛钱的价格买进价值一块钱的东西。」",
    "yellow": "「价格是你付出的，价值是你得到的。」",
    "red": "「以合理的价格买入一家伟大的公司，远胜于以低价买入一家平庸的公司。」",
    "gray": "「宁要模糊的正确，不要精确的错误。」",
}


@st.cache_data(ttl=3600, show_spinner=False)
def cached_fetch(symbol):
    return data.fetch_bundle(symbol)


CCY_SYM = {"USD": "$", "CNY": "¥", "HKD": "HK$", "TWD": "NT$"}


def ccy_sym(ccy):
    return CCY_SYM.get(ccy or "USD", (ccy or "USD") + " ")


def fmt_money(x, ccy="USD"):
    if x is None:
        return "NA"
    s = ccy_sym(ccy)
    if abs(x) >= 1e9:
        return f"{s}{x / 1e9:.1f}B"
    if abs(x) >= 1e6:
        return f"{s}{x / 1e6:.1f}M"
    return f"{s}{x:,.0f}"


def fmt_price(x, ccy="USD"):
    if x is None:
        return "NA"
    return f"{ccy_sym(ccy)}{x:,.2f}"


def status_label(status):
    return {"pass": "通过", "warn": "警示", "fail": "不通过", "na": "跳过"}.get(status, "—")


def _cell_color(label):
    colors = {"通过": "background-color:#1f7a33;color:#fff",
              "警示": "background-color:#b35900;color:#fff",
              "不通过": "background-color:#b32424;color:#fff",
              "跳过": "background-color:#5b5b5b;color:#fff"}
    return colors.get(label, "")


def fmt_value(it):
    if it["sub"] is None:
        return it["value"] if it["value"] is not None else "—"
    if it["unit"] == "%":
        return f"{it['value']:.1%}"
    if it["unit"] == "CV":
        return f"{it['value']:.2f}"
    return str(it["value"])


def render_verdict(d):
    banner = {
        "green": (st.success, "🟢 " + d["verdict"]),
        "yellow": (st.warning, "🟡 " + d["verdict"]),
        "red": (st.error, "🔴 " + d["verdict"]),
        "gray": (st.info, "⚪ " + d["verdict"]),
    }
    fn, msg = banner[d["level"]]
    fn(f"## {msg}\n\n{d['reason']}")
    st.caption(QUOTES.get(d["level"], ""))


def render_quality(q):
    st.subheader("一、公司质量（巴菲特质量门槛）")
    if q["score"] is not None:
        st.progress(min(q["score"] / 100, 1.0))
        st.markdown(f"**质量总分：{q['score']:.0f} / 100**（<60 分不建议建仓）")
    else:
        st.warning("质量数据不足，无法打分。")
    rows = []
    for it in q["items"]:
        if it["weight"] == 0 and it["sub"] is None:
            continue
        rows.append({"指标": it["name"], "数值": fmt_value(it),
                     "判断": status_label(it["status"]),
                     "权重": it["weight"],
                     "说明": it.get("note") or ""})
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df.style.map(_cell_color, subset=["判断"]), hide_index=True,
                     width="stretch", column_config={
                         "说明": st.column_config.TextColumn("说明", width="medium"),
                         "权重": st.column_config.NumberColumn("权重", width="small"),
                     })
    if q["na_notes"]:
        st.caption("数据说明：" + "；".join(set(q["na_notes"])))


def render_valuation(v, bundle):
    st.subheader("二、估值与买点时机（安全边际）")
    d = v.get("dcf") or {}
    ccy = bundle["currency"] or "USD"
    cols = st.columns(3)
    cols[0].metric("现价", fmt_price(bundle["current_price"], ccy))
    if d.get("iv_share"):
        cols[1].metric("内在价值/股", fmt_price(d["iv_share"], ccy))
        cols[2].metric("安全边际", f"{d['mos']:.1%}")
    else:
        cols[1].metric("内在价值/股", "NA")
        cols[2].metric("安全边际", "NA")

    entry = v.get("entry") or {}
    if entry.get("full"):
        cur = bundle["current_price"]
        if cur is not None and cur <= entry.get("good", 0):
            zone = "✅ 当前价已低于更安全买点，处于非常低估区间"
        elif cur is not None and cur <= entry["full"]:
            zone = "✅ 当前价已进入建议建仓区间"
        else:
            zone = "⚠️ 当前价尚未进入建议建仓区间"
        st.markdown(f"**建议建仓价格**：{fmt_price(entry['full'], ccy)}（安全边际 25%）"
                    f"　｜　**更安全买点**：{fmt_price(entry['good'], ccy)}（安全边际 40%）　—　{zone}")

    info = []
    if d:
        info.append(f"**DCF 模型**：FCF₀={fmt_money(d['fcf0'], ccy)}，前5年增速 g₁={d['g1']:.1%}，永续 g₂={C.PERPETUAL_GROWTH:.0%}，折现率 r={d['r']:.0%}")
    ey = v.get("ey")
    if ey:
        info.append(f"**盈利收益率 vs 10年美债**：Earnings Yield={ey['ey']:.2%}，10Y={ey['tnx']:.2%}，利差={ey['spread']:+.2%}（利差<0 视为高估）")
    if v.get("fcf_yield") is not None:
        info.append(f"**FCF 收益率**：{v['fcf_yield']:.2%}（≥8% 视为低估）")
    p = v.get("percentiles") or {}
    if "price_10y" in p:
        info.append(f"**股价位置**：10年区间分位 {p['price_10y']:.0%}，52周分位 {p.get('pct_52w', float('nan')):.0%}" if p.get("pct_52w") is not None else f"**股价位置**：10年区间分位 {p['price_10y']:.0%}")
    if not p.get("insufficient") and "val_pct" in p:
        info.append(f"**估值分位**（相对自身历史，越高越贵）：{p['val_pct']:.0%}（样本 N≈{p.get('val_sample_n')} 类倍数）")
    else:
        info.append("**估值分位**：数据不足（Yahoo 免费接口仅约 4-5 年年报），未虚构。")
    if v.get("score") is not None:
        info.append(f"**估值评分：{v['score']:.0f} / 100**（≥65 分视为有吸引力的买点）")
    for line in info:
        st.markdown(line)


def render_company(bundle):
    st.subheader("三、公司简介")
    bus = bundle.get("long_business_summary")
    if bus:
        st.write(bus[:600] + ("…" if len(bus) > 600 else ""))
        if len(bus) > 600:
            with st.expander("展开完整公司介绍（英文原文）"):
                st.write(bus)
    else:
        parts = [bundle["name"]]
        if bundle.get("sector"):
            parts.append(f"所属行业：{sector_cn(bundle['sector'])}")
        if bundle.get("industry"):
            parts.append(f"细分行业：{bundle['industry']}")
        if bundle.get("market"):
            parts.append(f"市场：{bundle['market']}")
        st.write("，".join(parts) + "。")
        st.caption("Yahoo 未收录该公司的详细简介，以上为基本信息。")
    meta = []
    if bundle.get("website"):
        meta.append(f"[官网]({bundle['website']})")
    if bundle.get("city"):
        meta.append(f"总部：{bundle['city']}{'，' + bundle['country'] if bundle.get('country') else ''}")
    if meta:
        st.caption(" · ".join(meta))


def main():
    sym = st.text_input("输入股票代码（如 AAPL / 600519.SS / 0700.HK）", "AAPL").strip().upper()
    if st.button("判断现在能否建仓", type="primary"):
        if not sym:
            st.warning("请输入股票代码。")
            return
        try:
            with st.spinner("正在抓取财务数据（约几秒）…"):
                bundle = cached_fetch(sym)
        except Exception as e:
            st.error(f"抓取失败：{e}")
            return
        ok, msg = tol.validate(bundle)
        if not ok:
            st.error(msg)
            return

        q = qmod.analyze_quality(bundle)
        v = vmod.analyze_valuation(bundle, q["score"])
        d = decision.decide(q, v)

        st.divider()
        st.markdown(f"### {bundle['name']}（{bundle['symbol']}）")
        meta_parts = [f"市场：{bundle['market']}", f"货币：{bundle['currency']}"]
        if bundle.get("sector"):
            meta_parts.append(f"行业：{sector_cn(bundle['sector'])}")
        if bundle.get("industry"):
            meta_parts.append(f"细分行业：{bundle['industry']}")
        st.caption(" · ".join(meta_parts))
        render_verdict(d)
        st.divider()
        render_quality(q)
        st.divider()
        render_valuation(v, bundle)
        st.divider()
        render_company(bundle)
        st.divider()
        st.caption("数据来源：Yahoo Finance（yfinance）。本工具为巴菲特式定量参考，不构成投资建议；公司护城河、管理层等定性因素需另行判断。")


with st.sidebar:
    st.markdown("### 方法说明")
    st.markdown("**质量门（Gate 1）**：ROE、毛利率、盈利一致性、负债、自由现金流、股本稀释。任一红线或总分 <60 → 不建议建仓。")
    st.markdown("**估值门（Gate 2）**：owner earnings 两阶段 DCF、Earnings yield vs 10年美债、相对自身历史的估值分位。")
    st.markdown("**结论**：质量达标且安全边际 ≥25% → 建议建仓；10%-25% → 半仓/分批；否则观望。")
    st.markdown("---")
    st.caption("注意：Yahoo 免费接口财报约 4-5 年，估值分位已诚实标注样本量，不作十年外推。")

main()
