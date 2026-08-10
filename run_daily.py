"""前沿文献日报 —— 入口脚本

用法：
  python3 run_daily.py --date 2026-08-09 --dry-run   # 指定日期，仅打印
  python3 run_daily.py                               # 默认跑昨天(北京)，写 reports/ 并存档
  配置邮件环境变量后会自动推送 (见 README)
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

from frontier_daily.fetcher import fetch_papers
from frontier_daily.reporter import build_markdown, build_html
from frontier_daily.mailer import send_email


def beijing_today():
    return (datetime.utcnow() + timedelta(hours=8)).date()


def main():
    ap = argparse.ArgumentParser(description="前沿文献日报")
    ap.add_argument("--date", help="报告日期 YYYY-MM-DD（默认：昨天，北京时间）")
    ap.add_argument("--window", type=int, default=7, help="回溯天数（默认 7）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印 Markdown，不生成文件/不邮件")
    ap.add_argument("--outdir", default="reports", help="输出目录")
    ap.add_argument("--no-email", action="store_true", help="禁止发邮件")
    args = ap.parse_args()

    if args.date:
        report_date = date.fromisoformat(args.date)
    else:
        report_date = beijing_today() - timedelta(days=1)
    date_from = report_date - timedelta(days=args.window - 1)

    print(f"[RUN] 报告日期 {report_date}，数据窗口 {date_from} ~ {report_date}")

    papers = fetch_papers(date_from.isoformat(), report_date.isoformat())

    openalex_n = sum(1 for p in papers if p.get("source") == "OpenAlex")
    if openalex_n == 0:
        print("[ABORT] OpenAlex 数据源未取得任何文献（可能被限流），"
              "本次不生成报告，避免提交残缺数据")
        sys.exit(2)

    md = build_markdown(papers, report_date.isoformat(), date_from.isoformat())
    html = build_html(papers, report_date.isoformat(), date_from.isoformat())

    if args.dry_run:
        print("\n" + "=" * 60)
        print(md)
        print("=" * 60)
        print(f"[DRY] {len(papers)} papers, html {len(html)} chars")
        return

    os.makedirs(args.outdir, exist_ok=True)
    base = f"前沿文献日报_{report_date.isoformat()}"
    md_path = os.path.join(args.outdir, base + ".md")
    html_path = os.path.join(args.outdir, base + ".html")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[SAVED] {md_path}")
    print(f"[SAVED] {html_path}")

    if not args.no_email:
        sent, info = send_email(html_path, f"前沿文献日报 {report_date.isoformat()}")
        print(f"[EMAIL] {info}")


if __name__ == "__main__":
    main()