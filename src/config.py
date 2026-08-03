"""全部阈值集中于此，按 2026 年市场口径调整。"""

# ---------- 质量门（Gate 1）----------
ROE = {
    "excellent": 0.20,   # ≥20% 满分
    "good": 0.15,        # 15-20% 良好
    "veto": 0.10,        # <10% 硬性否决
    "weight": 20,
}
ROE_STABILITY_WEIGHT = 10          # CV<0.5 良好，score = max(0, 1-CV)
NET_MARGIN = {"strong": 0.15, "weak": 0.05, "weight": 15}
GROSS_MARGIN = {"strong": 0.40, "weak": 0.20, "weight": 10}
EPS_CONSISTENCY_WEIGHT = 15
EPS_VETO_LOSS_YEARS = 2            # ≥2 个亏损年硬性否决
DEBT = {
    "good_de": 0.50,               # D/E ≤0.5 优
    "veto_de": 2.50,               # D/E>2.5 且 ICR<2 硬性否决
    "good_icr": 3.0,               # 利息覆盖 >3 良好
    "veto_icr": 2.0,               # <2 否决
    "weight": 10,
}
FCF_WEIGHT = 15
FCF_MIN_POSITIVE_YEARS = 4         # 5 年中 ≥4 年为正
DILUTION_WEIGHT = 5
DILUTION_VETO = 0.40               # 股本扩张 >40% 硬性否决

QUALITY_PASS_SCORE = 60            # 低于 60 直接不建议建仓
FISCAL_YEARS = 5                   # 用于质量检查的年数

# ---------- 估值门（Gate 2）----------
DISCOUNT_RATE = {"high_quality": 0.10, "normal": 0.12}
PERPETUAL_GROWTH = 0.03
MAX_GROWTH = 0.10                  # g1 保守增速上限
MOF = {"full": 0.25, "partial": 0.10}   # 安全边际 25% 充分 / 10% 有限
VALUE_PASS_SCORE = 65
VALUE_PARTIAL_SCORE = 55
EY_ATTRACTIVE_SPREAD = 0.03        # EY 高于 10Y 3pp 为有吸引力
FCF_YIELD_TARGET = 0.08            # FCF yield 8% 打满
DCF_DISCOUNT_NORM = 0.40           # 40% MoS 打满

# ---------- 容错 ----------
FINANCIAL_SECTORS = ("Financial Services", "Insurance")
