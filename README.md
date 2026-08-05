# Buffett Lens · 贤哥视角个股建仓判断

输入美股 / A股 / 港股代码（无需写后缀，自动识别），立刻判断「现在能不能建仓」。核心逻辑：**质量门槛 + 内在价值安全边际 + 建议买入价 + 中文公司简介**。

功能：
- **质量门**：ROE、毛利率、盈利一致性、负债、自由现金流、股本稀释
- **估值**：owner earnings DCF → 内在价值与安全边际，Earnings yield vs 10年美债，历史估值分位
- **建议建仓价格**：由内在价值反推安全边际 25%（建议建仓）与 40%（更安全买点）对应价格
- **完整信息**：市场/货币/行业（中文名）+ 中文公司简介 + 官网/总部

## 快速开始

```bash
cd buffett_lens
# 首次使用
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
# 启动网页应用
./.venv/bin/streamlit run app.py
```

浏览器打开 `http://localhost:8501`，输入代码 → 点击「判断现在能否建仓」。

代码格式：美股 `AAPL`；沪市A股 `600519`；深市A股 `000858`；港股 `0700`（腾讯）。

后缀可写可不写：`600519` 与 `600519.SS` 等价，工具会自动识别（纯数字 6 位且 6 开头 → 沪市，0/3 开头 → 深市，5 位以内 → 港股，其余按美股）。也可以在界面的「市场」下拉框里手动指定，避免歧义。

## 部署上线（朋友也能访问）

用免费平台 **Streamlit Community Cloud**（海外服务器，大陆访问可能偏慢）：

1. 注册 GitHub 账号 → 注册后登录 share.streamlit.io
2. 把本仓库代码推到 GitHub（见下方 git 命令）
3. 在 share.streamlit.io 点 **New app** → 选择你的仓库 → 分支 `main` → 主文件 `app.py`
4. 点 **Advanced settings** → Python 版本选 `3.12` → **Deploy**
5. 等 1-2 分钟构建完成，把得到的 `xxx.streamlit.app` 网址发给朋友即可

```bash
cd buffett_lens
git init
git add .
git commit -m "Buffett Lens 巴菲特视角个股建仓判断工具"
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

说明：免费实例闲置约一小时后进入休眠，朋友再访问时首次需等 30-60 秒冷启动；`requirements.txt` 与 `.python-version` 已配置好，云平台会自动识别。

## 判断框架

**一、质量门（Gate 1）**——公司值不值得买：
- ROE（平均权益）、净利率、毛利率、EPS 盈利一致性、负债与利息覆盖、自由现金流、股本稀释
- 任一红线（ROE<10% / ≥2个亏损年 / 杠杆过高 / 现金流持续为负 / 股本扩张>40%）或总分 <60 → 不建议建仓

**二、估值门（Gate 2）**——现在是不是好买点：
- owner earnings 两阶段 DCF → 每股内在价值 → 安全边际
- Earnings yield vs 10年美债利差
- 相对自身历史的 P/E、P/B、P/FCF 分位（诚实标注 Yahoo 免费接口仅约 4-5 年年报）

**三、综合结论**：
| 条件 | 结论 |
|---|---|
| 质量达标且安全边际 ≥25% | 🟢 建议建仓 |
| 安全边际 10%-25% | 🟡 分批/半仓 |
| 质量达标但无安全边际 | 🟡 观望 |
| 质量红线 / <60 分 | 🔴 不建议建仓 |

## 项目结构

```
buffett_lens/
  app.py              # Streamlit 界面
  requirements.txt
  src/
    config.py         # 全部阈值（2026 年市场口径）
    data.py           # yfinance 抓取 + 字段别名回退
    quality.py        # 质量门
    valuation.py      # DCF / 估值分位
    decision.py       # 综合结论
    tolerance.py      # 容错（无效代码/ETF/金融股/亏损股）
```

## 说明与局限

- 数据来自 Yahoo Finance（yfinance），免费接口财报约 4-5 年，估值分位不做十年外推。
- 金融股自动跳过负债与现金流类指标（口径不同）；亏损股相关指标标记 NA。
- A股/港股数据齐全时正常计算；个别代码 Yahoo 数据缺失会诚实标注"数据不足"。
- 本工具为贤哥视角的定量参考，不构成投资建议；护城河、管理层等定性因素需自行判断。

## 中文公司简介

- 默认情况：工具根据行业、市场、币种、总部等字段生成结构化中文简介，英文原文放在折叠区供对照。
- 可选增强：在 `buffett_lens/.env` 里写入 `DEEPSEEK_API_KEY=你的密钥`，工具会调用 DeepSeek 生成约 120-180 字的中文简介（调用失败会自动回退到结构化简介）。密钥只存在本地 `.env`，已被 git 忽略，不会上传 GitHub。
