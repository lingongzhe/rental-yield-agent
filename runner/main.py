# -*- coding: utf-8 -*-
"""主入口：读贝壳官方 API 数据 → 评分 → 生成可视化报告。

用法：
  python main.py              用上次贝壳快照重建报告（离线，不动网络）
  python main.py --refresh    连贝壳官方 API 手动更新数据并重建报告
  python main.py --refresh --open   更新后顺带用浏览器打开

数据源只有一处：贝壳官方开放平台（beike CLI + 本机 API Key）。
手动更新数据 = 重跑一次 --refresh；平时跑 main.py 用最近快照即可。
"""
import os
import argparse
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import beike  # noqa: E402
import housecli  # noqa: E402
import creprice  # noqa: E402
import gotohui  # noqa: E402
from config import BUDGET_WAN  # noqa: E402
from score import run  # noqa: E402
from report import write_report, build_html, build_no_data_html  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "output")
OUT_HTML = os.path.join(OUT_DIR, "rental-report.html")

CITIES = ("沈阳", "大连")


def main():
    parser = argparse.ArgumentParser(description="沈阳/大连 30万内老破小收租筛选智能体（贝壳官方数据）")
    parser.add_argument("--refresh", action="store_true",
                        help="联网从贝壳官方 API 更新数据(手动更新数据用)；默认用上次快照")
    parser.add_argument("--open", action="store_true", help="生成后用默认浏览器打开报告")
    args = parser.parse_args()

    print("=" * 62)
    print("  沈阳 · 大连  30万内老破小 · 纯投资收租筛选智能体")
    print("  预算 ≤{b}万 · 推荐线 净回报≥3.5% · 出租易度≥60".format(b=int(BUDGET_WAN)))
    print("  数据源：贝壳官方开放平台（beike CLI + 本机 Key）")
    print("=" * 62)

    # 1) 取数：--refresh 走官方 API；否则读上次快照
    ds, coll_log, date = None, [], None
    crep, crep_month, got = {}, "", {}
    if args.refresh:
        print("\n[数据] 联网更新贝壳数据(官方 API，需几分钟) ...")
        ok, ds, coll_log = beike.refresh(CITIES, BUDGET_WAN)
        if not ok:
            old = beike.load_snapshot()
            if old and old.get("houses"):
                ds, coll_log = old, list(old.get("log", [])) + ["(本次贝壳 API 未取到数据，已回退到上次快照)"]
                print("[提示] 本次贝壳 API 未取到数据，回退到上次快照。")
            else:
                ds, coll_log = None, []
                print("[提示] 贝壳 API 未取到数据。")

        # 补充：creprice.cn 区县市场行情（房价+租金），并以其租金率兜底板块租金地图
        print("\n[数据] 联网抓取 creprice 区县市场行情(房价/租金，各城约 8 秒) ...")
        crep, crep_month = creprice.collect(CITIES, coll_log)
        if ds and ds.get("plate_rents"):
            ds["plate_rents"] = creprice.overlay(ds["plate_rents"], crep, coll_log)
        if ds and (crep or crep_month):
            ds["creprice"], ds["creprice_month"] = crep, crep_month

        # 补充：gotohui.com(聚汇数据) 城市级行情（二手/新房均价、月均房租）独立交叉校验
        print("\n[数据] 联网抓取 gotohui 城市行情(聚汇数据) ...")
        got = gotohui.collect(CITIES, coll_log)
        if ds and got:
            ds["gotohui"] = got

        # 补充：house-cli 多平台（贝壳不可用时自建租房租金、独立顶班）
        base_rent = (ds.get("plate_rents") or {}) if ds and ds.get("houses") else {}
        existing = (ds.get("houses") or []) if ds and ds.get("houses") else []
        print("\n[数据] 联网补充多平台数据(house-cli，未装/无Cookie自动跳过) ...")
        extra, merged_rent, hlog = housecli.collect(
            CITIES, BUDGET_WAN, plate_rents=base_rent, existing=existing, log=coll_log)
        for line in hlog:
            if line not in coll_log:
                coll_log.append(line)
        if extra:
            if not (ds and ds.get("houses")):
                ds = {"source": "house-cli 多平台(贝壳API本次不可用)",
                      "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                      "cities": list(CITIES), "budget": BUDGET_WAN,
                      "houses": extra, "plate_rents": merged_rent, "log": coll_log}
                if crep:
                    ds["creprice"] = crep
                    ds["creprice_month"] = crep_month
                if got:
                    ds["gotohui"] = got
                print("      多平台独立产出 {n} 套候选（贝壳停机兜底）".format(n=len(extra)))
            else:
                ds["houses"].extend(extra)
                ds["source"] = (ds.get("source") or "beike") + " + house-cli多平台"
                ds["plate_rents"] = merged_rent
                print("      多平台补充 {n} 套候选（累计 {t} 套）".format(
                    n=len(extra), t=len(ds["houses"])))
            beike._write_snapshot(ds)
    else:
        ds = beike.load_snapshot()
        if ds and ds.get("houses"):
            coll_log = ["数据来源：上次贝壳快照({at})，含 {n} 套真实挂牌".format(
                at=ds.get("fetched_at", ""), n=len(ds["houses"]))]
            crep = ds.get("creprice") or {}
            crep_month = ds.get("creprice_month") or ""
            got = ds.get("gotohui") or gotohui.load_snapshot()
            if not crep:
                crep, crep_month = creprice.load_snapshot()
                if crep and not ds.get("creprice_month"):
                    coll_log.append("简述行情源：creprice.cn 区县房租房价（上次快照，{m}）".format(
                        m=crep_month or "?"))
        elif ds is None:
            coll_log = ["尚未生成贝壳快照。请先手动运行一次 main.py --refresh 拉取官方数据。"]

    if not (ds and ds.get("houses")):
        os.makedirs(OUT_DIR, exist_ok=True)
        html = build_no_data_html(date=date or None, coll_log=coll_log, offline=not args.refresh)
        write_report(OUT_HTML, html)
        print("\n[提示] 本次未生成任何推荐（详见报告顶部提示页）。")
        print("  报告已生成： {path}".format(path=OUT_HTML))
        if not ds:
            print("  首次使用请运行： python main.py --refresh")
        if args.open:
            _open_browser(OUT_HTML)
        return 0

    houses, date = ds["houses"], ds.get("fetched_at")
    for line in ds.get("log", []):
        if line not in coll_log:
            coll_log.append(line)
    print("      官方贝壳数据 · {n} 条真实候选".format(n=len(houses)))

    print("[评分] 租售比 / 回本年限 / 净回报率 / 出租易度 ...")
    recs = run([dict(h) for h in houses])
    n_rec = sum(1 for r in recs if r["recommend"])
    print("      共 {total} 套，其中达标推荐 {ok} 套。".format(total=len(recs), ok=n_rec))

    print("[报告] 生成可视化报告 ...")
    html = build_html(
        msg="",
        recs=recs,
        coll_log=coll_log,
        online=True,
        date=date,
        crep=crep,
        crep_month=crep_month,
        got=got,
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    write_report(OUT_HTML, html)

    print("-" * 62)
    print("  报告已生成： {path}".format(path=OUT_HTML))
    print("  双击用浏览器打开即可查看可视化结果。")
    print("  想更新数据？重跑一次： python main.py --refresh")
    if args.open:
        _open_browser(OUT_HTML)
    return 0


def _open_browser(path):
    try:
        os.startfile(path)  # Windows
    except Exception:       # noqa: BLE001
        import webbrowser
        webbrowser.open(path)


if __name__ == "__main__":
    sys.exit(main())