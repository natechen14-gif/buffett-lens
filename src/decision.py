"""综合结论：质量门 + 估值门 → 建仓判断。"""

from . import config as C


def decide(quality, valuation):
    vetoes = quality["vetoes"]
    if vetoes:
        return {"verdict": "不建议建仓", "level": "red",
                "reason": "质量红线：" + "；".join(vetoes)}
    if quality["score"] is None:
        return {"verdict": "数据不足", "level": "gray",
                "reason": "关键财务数据缺失，无法给出建仓判断。"}
    if quality["score"] < C.QUALITY_PASS_SCORE:
        return {"verdict": "不建议建仓", "level": "red",
                "reason": f"质量平庸（{quality['score']:.0f}分），未达到贤哥视角的质量标准。"}

    mos = (valuation.get("dcf") or {}).get("mos")
    val_score = valuation.get("score")
    price_pct = (valuation.get("percentiles") or {}).get("price_10y")

    if mos is not None and val_score is not None and mos >= C.MOF["full"] and val_score >= C.VALUE_PASS_SCORE:
        if price_pct is not None and price_pct > 0.90:
            return {"verdict": "可分批建仓", "level": "green",
                    "reason": "有充分安全边际，但股价处于10年高位，建议分批而非一次买入。"}
        return {"verdict": "建议建仓", "level": "green",
                "reason": "质量达标且安全边际充分（≥25%），符合贤哥视角的建仓标准。"}

    if mos is not None and val_score is not None and mos >= C.MOF["partial"] and val_score >= C.VALUE_PARTIAL_SCORE:
        return {"verdict": "可分批/半仓建仓", "level": "yellow",
                "reason": "安全边际有限（10%-25%），建议半仓或分批买入、留足余地。"}

    return {"verdict": "观望", "level": "yellow",
            "reason": "公司质量尚可，但当前价格缺乏足够安全边际 / 买入时机不佳。"}
