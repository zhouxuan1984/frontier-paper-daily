"""前沿文献日报 · 报告生成（Markdown + HTML）
结构：概览 / 今日新发(按 JIF 影响力) / 近7天高被引(按被引百分位)，每领域分节。
"""

from datetime import date, timedelta
import re

from .config import REPORT_TITLE, SCOPE, SOURCES_NOTE

FRESH_TOP = 8
HOT_TOP = 8

DOMAIN_EMOJI = {
    "生物医药": "💊", "医疗器械": "🩺", "可穿戴设备": "⌚", "脑机接口": "🧠",
    "arXiv": "📄",
}


# ── 文本 helper ──────────────────────────────────────────────────────

def _pct_str(p):
    v = p.get("cited_percentile")
    return "—" if v is None else str(int(v))


def _cited_str(p):
    v = p.get("cited_by_count")
    return "—" if v is None else str(v)


def _if_str(p):
    v = p.get("impact_factor")
    return "—" if v is None else f"{v:g}"


def _san(t):
    return (t or "").replace("_", r"\_").replace("|", r"\|")


def _abstract_str(p):
    return re.sub(r"\s+", " ", p.get("abstract") or "").strip()


def _markdown_links(p):
    links = p.get("links", {})
    order = ["DOI", "OpenAlex", "PubMed", "PMC", "EuropePMC", "arXiv", "OA全文"]
    parts = [f"[{k}]({links[k]})" for k in order if k in links]
    manual = p.get("manual_links", {})
    if manual.get("Web of Science"):
        parts.append("[WoS🔒](https://www.webofscience.com/)")
    if manual.get("ResearchGate"):
        parts.append(f"[RG]({manual['ResearchGate']})")
    if manual.get("WorldCat"):
        parts.append(f"[WorldCat]({manual['WorldCat']})")
    if manual.get("LibGen"):
        parts.append(f"[LibGen⚠️]({manual['LibGen']})")
    return "　".join(parts) if parts else "无"


def _publish_day(p):
    return (p.get("publication_date") or "")[:10]


# ── 分榜 ────────────────────────────────────────────────────────────

def _split_blocks(papers, date_from, fresh_top=FRESH_TOP, hot_top=HOT_TOP):
    """按领域分节，每节返回 fresh(今日新发=最近完整发表日往前1天,按IF) 与 hot(窗口内,按百分位)。"""
    full_days = []
    for p in papers:
        d = (p.get("publication_date") or "")
        if len(d) == 10:
            full_days.append(d)
    latest_day = max(full_days) if full_days else date_from
    fresh_cutoff = (date.fromisoformat(latest_day) - timedelta(days=1)).isoformat()

    per_domain = {}
    for p in papers:
        d = p.get("domain") or "其他"
        per_domain.setdefault(d, []).append(p)

    blocks = []
    for d, items in per_domain.items():
        fresh = [p for p in items if len(_publish_day(p)) == 10
                 and _publish_day(p) >= fresh_cutoff]
        fresh.sort(key=lambda x: (x.get("impact_factor") is None,
                                  -(x.get("impact_factor") or 0.0),
                                  x.get("publication_date") or ""))
        hot = sorted(items, key=lambda x: (x.get("cited_percentile") is None,
                                           -(x.get("cited_percentile") or 0),
                                           -(x.get("cited_by_count") or 0)))
        blocks.append({
            "domain": d,
            "fresh": fresh[:fresh_top],
            "hot": hot[:hot_top],
            "total": len(items),
        })
    blocks.sort(key=lambda b: list(DOMAIN_EMOJI.keys()).index(b["domain"])
                if b["domain"] in DOMAIN_EMOJI else 99)
    return blocks


# ── Markdown ──────────────────────────────────────────────────────────

def build_markdown(papers, date_to, date_from):
    L = []
    L.append(f"# 📰 {REPORT_TITLE} — {date_to}")
    L.append("")
    L.append(f"> 领域：{SCOPE} ｜ 数据窗口：{date_from} ~ {date_to} ｜ 收录 {len(papers)} 篇")
    L.append("")
    L.append("## 📊 概览")
    L.append("")
    L.append("| 领域 | 篇数 |")
    L.append("|---|---|")

    blocks = _split_blocks(papers, date_from)
    per_domain_total = {}
    for b in blocks:
        per_domain_total[b["domain"]] = b["total"]
    for d, n in per_domain_total.items():
        L.append(f"| {DOMAIN_EMOJI.get(d,'📚')} {d} | {n} |")
    L.append("")

    for b in blocks:
        emoji = DOMAIN_EMOJI.get(b["domain"], "📚")
        L.append(f"## {emoji} {b['domain']}（窗口内 {b['total']} 篇）")
        L.append("")

        L.append("### 🆕 今日新发｜按期刊影响因子排序")
        L.append("")
        if not b["fresh"]:
            L.append("（今日暂无新发表条目）")
            L.append("")
        for i, p in enumerate(b["fresh"], 1):
            L.append(f"{i}. **{_san(p['title'])}**")
            L.append(f"   - 期刊 {p.get('journal') or '—'}（IF {_if_str(p)}）｜"
                     f"发表 {_publish_day(p) or '—'}｜来源 {p.get('source') or '—'}")
            L.append(f"   - 被引量 {_cited_str(p)}　被引百分位 {_pct_str(p)}")
            L.append(f"   - 入口 {_markdown_links(p)}")
            ab = _abstract_str(p)
            if ab:
                L.append(f"   - 📄 摘要：{ab}")
            L.append("")

        L.append("### 🔥 近7天高被引｜按被引百分位排序")
        L.append("")
        if not b["hot"]:
            L.append("（暂无数据）")
            L.append("")
        for i, p in enumerate(b["hot"], 1):
            L.append(f"{i}. **{_san(p['title'])}**")
            L.append(f"   - 被引百分位 **{_pct_str(p)}**　被引 {_cited_str(p)}｜"
                     f"期刊 {p.get('journal') or '—'}（IF {_if_str(p)}）")
            L.append(f"   - 发表 {_publish_day(p)} ｜ 来源 {p.get('source') or '—'}")
            L.append(f"   - 入口：{_markdown_links(p)}")
            ab = _abstract_str(p)
            if ab:
                L.append(f"   - 📄 摘要：{ab}")
            L.append("")

    L.append("---")
    L.append(f"*{SOURCES_NOTE}*")
    return "\n".join(L)


# ── HTML ────────────────────────────────────────────────────────────

def _html_links(p):
    badge = (
        '<a class="lnk" href="{}" target="_blank" rel="noopener">{}</a>'
    )
    manual_badge = (
        '<a class="lnk lnk-manual" href="{}" target="_blank" rel="noopener" '
        'title="需要订阅/登录或注意版权">{}</a>'
    )
    links = p.get("links", {})
    order = ["DOI", "OpenAlex", "PubMed", "PMC", "EuropePMC", "arXiv", "OA全文"]
    html = "".join(badge.format(links[k], k) for k in order if k in links)
    m = p.get("manual_links", {})
    manual_items = [
        ("ResearchGate", "RG", "需要登录"),
        ("WorldCat", "WorldCat", "馆藏检索"),
        ("LibGen", "LibGen", "注意版权"),
        ("Web of Science", "WoS", "需订阅"),
    ]
    for key, label, tip in manual_items:
        url = m.get(key)
        if url:
            html += manual_badge.format(url, label)
    return html


def build_html(papers, date_to, date_from):
    blocks = _split_blocks(papers, date_from)
    total_dom = {b["domain"]: b["total"] for b in blocks}

    rows_domain = "".join(
        f"<tr><td>{DOMAIN_EMOJI.get(d,'📚')} {d}</td><th style='text-align:right'>{n}</th></tr>"
        for d, n in total_dom.items())

    section_html = []
    for b in blocks:
        emoji = DOMAIN_EMOJI.get(b["domain"], "📚")
        sec = [f"<h2>{emoji} {b['domain']} <span class='subn'>{b['total']} 篇</span></h2>"]

        sec.append("<h3>🆕 今日新发 · 按期刊影响因子排序</h3>")
        if not b["fresh"]:
            sec.append("<p class='muted'>(暂无)</p>")
        sec.append('<table class="tbl">')
        sec.append("<tr><th>#</th><th>标题 / 期刊 / 摘要</th><th>被引</th>"
                   "<th>百分位</th><th>入口</th></tr>")
        for i, p in enumerate(b["fresh"], 1):
            ab = _esc(_abstract_str(p))
            sec.append(
                f'<tr><td>{i}</td>'
                f'<td><b>{_esc(p.get("title",""))}</b>'
                f'<div class="no">{_esc(p.get("journal") or "—")} · IF {_if_str(p)}'
                f' · {_esc(_publish_day(p))} · {_esc(p.get("source") or "")}</div>'
                + (f'<div class="ab">📄 {ab}</div>' if ab else '')
                + '</td>'
                f'<td class="c">{_cited_str(p)}</td>'
                f'<td class="c">{_pct_str(p)}</td>'
                f'<td class="c">{_html_links(p)}</td></tr>')
        sec.append("</table>")

        sec.append("<h3>🔥 近7天高被引 · 按被引百分位排序</h3>")
        if not b["hot"]:
            sec.append("<p class='muted'>(暂无)</p>")
        sec.append('<table class="tbl">')
        sec.append('<tr><th>#</th><th>标题 / 期刊</th><th>被引</th><th>百分位</th>'
                   "<th>入口</th></tr>")
        for i, p in enumerate(b["hot"], 1):
            ab = _esc(_abstract_str(p))
            sec.append(
                f'<tr><td>{i}</td>'
                f'<td><b>{_esc(p.get("title",""))}</b>'
                f'<div class="no">{_esc(p.get("journal") or "—")} · IF {_if_str(p)}'
                f' · {_esc(_publish_day(p))}</div>'
                + (f'<div class="ab">📄 {ab}</div>' if ab else '')
                + '</td>'
                f'<td class="r">{_cited_str(p)}</td>'
                f'<td class="r"><b>{_pct_str(p)}</b></td>'
                f'<td class="c">{_html_links(p)}</td></tr>')
        sec.append("</table>")
        section_html.append("".join(sec))

    body = f"""
    <div class="wrap">
      <h1>📰 {REPORT_TITLE} — {date}</h1>
      <p class="sub">领域：{SCOPE}</p>
      <p class="sub">数据窗口：{date} ← {date_from} ｜ 收录 <b>{len(papers)}</b> 篇</p>
      <table class="tbl ov"><caption>■■■ 概览</caption>
        <thead><tr><th>领域</th><th>篇数</th></tr></thead>
        {rows_domain}
      </table>
      {''.join(section_html)}
      <p class="foot">{SOURCES_NOTE}</p>
    </div>
    """
    head = """
    <meta charset="utf-8">
    <title>前沿文献日报</title>
    <style>
      body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
        margin:0;background:#f4f7fb;color:#1f2937;}
      .wrap{max-width:1100px;margin:0 auto;padding:28px 20px 60px;}
      h1{font-size:24px;margin:6px 0;}
      h2{border-left:4px solid #2563eb;padding-left:10px;margin:32px 0 8px;
        font-size:19px;}
      h3{color:#475569;font-size:15px;margin:18px 0 6px;}
      .sub{color:#64748b;font-size:13px;margin:2px 0;}
      .subn{color:#94a3b8;font-size:14px;font-weight:400;}
      .tbl{border-collapse:collapse;width:100%;background:#fff;margin:6px 0 18px;
        box-shadow:0 1px 3px rgba(0,0,0,.06);border:1px solid #e2e8f0;font-size:13px;}
      .tbl caption{text-align:left;font-weight:600;padding:8px 2px;}
      .tbl th{background:#f8fafc;text-align:left;padding:7px 10px;border-bottom:1px solid #e2e8f0;}
      .tbl td{padding:9px 10px;border-bottom:1px solid #f1f5f9;vertical-align:top;}
      .tbl td.r{text-align:right;white-space:nowrap;}
      .tbl td.c{white-space:nowrap;max-width:210px;}
      .no{color:#64748b;font-size:12px;margin-top:1px;}
      .ab{color:#475569;font-size:12px;line-height:1.55;margin-top:4px;padding:6px 8px;
        background:#f8fafc;border-left:2px solid #cbd5e1;border-radius:3px;}
      .lnk{display:inline-block;margin:2px 3px 2px 0;padding:2px 8px;border:1px solid #cbd5e1;
        border-radius:999px;color:#2563eb;text-decoration:none;font-size:12px;background:#eff6ff;}
      .lnk-manual{color:#64748b;background:#f1f5f9;border-color:#e2e8f0;}
      .muted{color:#94a3b8;font-size:13px;}
      .footnote{color:#94a3b8;font-size:12px;border-top:1px solid #e2e8f0;
        padding-top:10px;margin-top:30px;}
    </style>
    """
    return f"<!DOCTYPE html><html><head>{head}</head><body>{body}\n</body></html>"


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")