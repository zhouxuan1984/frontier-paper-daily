# 前沿文献日报（Frontier Paper Daily）

每日自动追踪 **生物医药 · 医疗器械 · 可穿戴设备 · 脑机接口** 的全球前沿文献，输出 **今日新发（按期刊影响因子排序）** 与 **近7天高被引（按被引百分位排序）** 两份榜单，并自动发布到 GitHub 仓库（可选邮件推送）。

## 数据来源与指标

| 层 | 来源 | 作用 |
|---|---|---|
| 自动抓取 | OpenAlex（聚合 Crossref/Scopus/PubMed/arXiv 等） | 被引量、被引百分位、期刊来源 |
| 自动抓取 | PubMed (E-utilities) | 生物医学文献补充与 PubMed 入口 |
| 自动抓取 | arXiv (export API) | 预印本（BCI/可穿戴/医学影像等） |
| 交叉校验 | Semantic Scholar | S2 被引数（尽力而为，失败自动跳过） |
| 期刊指标 | 本地 `data/jcr_if.json`（JCR 2024） | 三列指标中的 **JIF** |
| 手动入口 | Web of Science / ResearchGate / WorldCat / Library Genesis | 仅提供检索入口，需订阅/登录或注意版权 |

> **指标说明**：三列指标「被引量」「被引百分位」「JIF」。无数据的指标显示为 `—`。
> 被引量与被引百分位来自 OpenAlex；JIF 来自本地 JCR 2024 映射表。
> Web of Science / ResearchGate / WorldCat / Library Genesis **不参与指标计算**，仅作检索入口：
> WoS 需机构订阅、RG 需登录、WorldCat 为馆藏检索、LibGen 为第三方电子书库请自行注意版权。

## 每条文献的入口链接

- **DOI**（doi.org，最权威）
- **OpenAlex** 条目页
- **PubMed / PMC / Europe PMC**（全文）
- **OA 全文**（Unpaywall 开放获取解析）
- **arXiv**（当为预印本时）
- 手动入口：**Web of Science🔒（需订阅）**、**ResearchGate（需登录）**、**WorldCat（馆藏检索）**、**Library Genesis⚠️（注意版权）**

## 快速开始（本地测试）

```bash
python3 run_daily.py --dry-run                      # 打印日报预览
python3 run_daily.py --date 2026-08-09 --dry-run    # 指定日期
python3 run_daily.py                                # 生成 reports/ 下 .md + .html 并存档
```

纯 Python 标准库实现，无外部依赖。

## GitHub 自主运行

1. 推送到 GitHub 后，Actions 每天 **北京时间 08:00** 自动生成报告，并自动把
   `reports/前沿文献日报_YYYY-MM-DD.md/html` 提交回仓库。
2. 可选邮件推送：在仓库 Settings → Secrets and variables → Actions 添加：

| Secret | 说明 |
|---|---|
| `EMAIL_ADDRESS` | 发件邮箱（如 QQ 邮箱） |
| `EMAIL_AUTH_CODE` | QQ 邮箱 SMTP 授权码（邮箱设置 → 账户 → 开启 SMTP 生成） |
| `RECIPIENT_EMAIL` | 收件邮箱（可多个，逗号分隔） |
| `SMTP_HOST` / `SMTP_PORT` | 可选，默认 smtp.qq.com:465 |

## 目录结构

```
frontier-paper-daily/
├── .github/workflows/daily.yml   # 每日定时任务 + 自动提交
├── data/jcr_if.json              # 期刊影响因子映射表 (JCR 2024)
├── frontier_daily/
│   ├── config.py                 # 四大领域检索规则 + 入口链接定义
│   ├── fetcher.py                # OpenAlex/PubMed/arXiv/S2 抓取、去重、指标
│   ├── reporter.py               # 双榜单 Markdown/HTML 报告
│   └── mailer.py                 # 可选邮件推送
├── run_daily.py                  # 入口脚本
└── reports/                      # 每日产出（自动提交回仓库）
```