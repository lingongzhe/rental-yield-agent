# -*- coding: utf-8 -*-
"""主入口：一键运行 → 输出可视化报告。
用法：  python main.py            直接运行(优先联网，失败自动回退内置行情样本)
        python main.py --offline  强制用内置样本(离线演示)
产出：  output/rental-report.html  （双击用浏览器打开即可）
"""
import os
import argparse
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CURR_FILE                     # noqa: E402
from crawlers import collect_online              # noqa: E402
from score import run                            # noqa: E402
from report import write_report, build_html, build_no_data_html  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "output")
OUT_HTML = os.path.join(OUT_DIR, "rental-report.html")

CITIES = ("沈阳", "大连")
BUDGET = 30


def main():
    parser = argparse.ArgumentParser(description="沈阳/大连 30万内老破小收租筛选智能体")
    parser.add_argument("--offline", action="store_true", help="强制使用内置行情样本")
    parser.add_argument("--open", action="store_true", help="生成后用默认浏览器打开报告")
    args = parser.parse_args()

    print("=" * 62)
    print("  沈阳 · 大连  30万内老破小 · 纯投资收租筛选智能体")
    print("  预算 ≤{b}万 · 推荐线 净回报≥3.5% · 出租易度≥60".format(b=BUDGET))
    print("=" * 62)

    # 1) 取数（只认真实数据，绝不回退猜测样本）
    online, fetched, coll_log = False, None, []
    if args.offline:
        print("\n[1/4] 离线模式：无法采集真实数据，直接输出提示页。")
        coll_log = ["离线模式(--offline)：不采集数据，不估算。"]
    else:
        print("\n[1/4] 尝试联网采集(链家/贝壳) ...")
        online, fetched, coll_log = collect_online(CITIES, BUDGET)

    # 没有拿到任何真实数据 → 生成"无真实数据"提示页，不评分、不估算
    if not (online and fetched):
        os.makedirs(OUT_DIR, exist_ok=True)
        html = build_no_data_html(
            date=CURR_FILE, coll_log=coll_log, offline=args.offline)
        write_report(OUT_HTML, html)
        print("\n[提示] 本次未获取到任何真实数据，已生成提示页(未估算、未打分)。")
        print("  报告已生成： {path}".format(path=OUT_HTML))
        if args.open:
            _open_browser(OUT_HTML)
        return 0

    print("      在线取数成功：{} 条真实数据".format(len(fetched)))

    print("[2/4] 清洗 → 打分(租售比/回本/净回报/出租易度/综合分) ...")
    houses = [dict(h) for h in fetched]
    recs = run(houses)
    n_rec = sum(1 for r in recs if r["recommend"])
    print("      共 {total} 套，其中达标推荐 {ok} 套。".format(total=len(recs), ok=n_rec))

    print("[3/4] 生成可视化报告 ...")
    html = build_html(
        msg="",
        recs=recs,
        coll_log=coll_log,
        online=online,
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    write_report(OUT_HTML, html)

    print("[4/4] 完成！")
    print("-" * 62)
    print("  报告已生成： {path}".format(path=OUT_HTML))
    print("  双击用浏览器打开即可查看可视化结果。")
    if args.open:
        _open_browser(OUT_HTML)
    print("=" * 62)
    return 0


def _open_browser(path):
    try:
        os.startfile(path)  # Windows
    except Exception:       # noqa: BLE001
        import webbrowser
        webbrowser.open(path)


if __name__ == "__main__":
    sys.exit(main())