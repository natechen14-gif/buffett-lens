"""容错：无效代码、ETF、金融股识别，保证工具不崩溃、不误导。"""

from . import config as C


def is_financial(bundle):
    s = bundle.get("sector") or ""
    return any(k in s for k in C.FINANCIAL_SECTORS)


def validate(bundle):
    qt = bundle.get("quote_type")
    if qt and qt != "EQUITY":
        return False, f"该代码类型为 {qt}，本工具仅适用于股票（如 AAPL / 600519 / 0700）。"
    close = bundle.get("close")
    has_price = bundle.get("current_price") is not None
    has_fin = any(bundle.get(k) for k in ("revenue", "net_income", "equity", "fcf"))
    if not has_price and (close is None or len(close) == 0) and not has_fin:
        return False, "无法获取该代码的数据，请检查代码格式（如 AAPL / 600519.SS / 0700.HK）。"
    if not has_price:
        return False, "无法获取当前价格，请稍后重试。"
    return True, ""
