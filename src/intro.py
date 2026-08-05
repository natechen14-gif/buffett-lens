"""公司简介：优先用 DeepSeek 生成中文简介，未配置或失败时用结构化中文兜底。"""

import os


SECTOR_CN = {
    "Technology": "科技",
    "Consumer Defensive": "必需消费",
    "Consumer Cyclical": "可选消费",
    "Healthcare": "医疗保健",
    "Financial Services": "金融",
    "Industrials": "工业",
    "Energy": "能源",
    "Utilities": "公用事业",
    "Communication Services": "通信服务",
    "Real Estate": "房地产",
    "Basic Materials": "基础材料",
}

DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _load_env_if_exists(path=".env"):
    """可选加载本目录 .env，避免把 API Key 写进代码或仓库。"""
    if not os.path.exists(path):
        return
    try:
        for raw in open(path, encoding="utf-8"):
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip().strip("'\"")
            if name == "DEEPSEEK_API_KEY":
                os.environ.setdefault(name, value)
    except OSError:
        pass


def _fallback(bundle):
    parts = [bundle.get("name") or bundle.get("symbol")]
    sector = bundle.get("sector")
    if sector:
        parts.append(f"属于{SECTOR_CN.get(sector, sector)}行业")
    market = bundle.get("market")
    if market:
        parts.append(f"在{market}上市")
    ccy = bundle.get("currency")
    if ccy:
        parts.append(f"以{ccy}计价")
    loc = "，".join(x for x in (bundle.get("city"), bundle.get("country")) if x)
    if loc:
        parts.append(f"总部位于{loc}")
    return "；".join(parts) + "。"


def generate_chinese_intro(bundle):
    """返回 {"text": 中文简介, "source": "deepseek" | "fallback"}。"""
    _load_env_if_exists()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    summary = (bundle.get("long_business_summary") or "").strip()
    if key and summary:
        try:
            import requests

            r = requests.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是公司简介的中文改写助手。只输出 120-180 字的中文公司简介正文，不输出任何其他内容。",
                        },
                        {
                            "role": "user",
                            "content": (
                                f"公司：{bundle.get('name')}（{bundle.get('symbol')}）\n"
                                f"行业：{bundle.get('sector')} / {bundle.get('industry')}\n"
                                f"市场：{bundle.get('market')}，货币：{bundle.get('currency')}\n"
                                f"英文简介：\n{summary}"
                            ),
                        },
                    ],
                    "max_tokens": 320,
                    "temperature": 0.3,
                },
                timeout=25,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if text:
                return {"text": text, "source": "deepseek"}
        except Exception:
            pass
    return {"text": _fallback(bundle), "source": "fallback"}
