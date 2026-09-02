# -*- coding: utf-8 -*-
"""登录态无头批量采集（量大）。

依赖：Playwright + 链家登录态（.lianjia_cookies.json，由 login.py 生成保存）。
策略：
  - 携带登录态用无头浏览器逐页翻页抓取真实房源（二手房/租房）。
  - 每页随机延时(节流)，降低触发风控概率。
  - 任一页被"登录/验证码"拦截或取不到列表 → 立即停止该栏目，绝不硬闯。
  - 数据全部为页面上的真实挂牌，不生成/不估算任何数值。
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import crawlers  # noqa: E402  复用同一套解析切片

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            ".lianjia_cookies.json")
ESF_MAX_PAGES = 25          # 每城二手房最大翻页数（30 条/页）
ZUF_MAX_PAGES = 15          # 每城租房最大翻页数
PAGE_DELAY = (2.5, 4.5)     # 每页随机延时秒（节流）


def has_saved_state():
    return os.path.exists(COOKIES_FILE)


def _load_cookies():
    with open(COOKIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _visit(page, url):
    """带登录态打开一个列表页。返回 ('OK', html) / ('BLOCKED', None) / ('ERR', None)。"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(random.randint(1200, 2200))
        title = page.eval_on_selector("title",
                                      "e => e ? e.textContent : ''").strip()
        if title.startswith(("登录", "CAPTCHA")):
            return "BLOCKED", None
        return "OK", page.content()
    except Exception:  # noqa: BLE001
        return "ERR", None


def _crawl_city(page, sub, city, budget, esf_max, zuf_max):
    """采集单城：翻页二手房(<=budget) + 翻页租房(聚合板块租金率)。"""
    log = []
    houses, seen = [], set()
    for pg in range(1, esf_max + 1):
        url = "https://{sub}.lianjia.com/ershoufang/".format(sub=sub)
        if pg > 1:
            url = "https://{sub}.lianjia.com/ershoufang/pg{d}/".format(sub=sub, d=pg)
        st, html = _visit(page, url)
        if st != "OK" or "totalPrice" not in html:
            why = "拦截" if st == "BLOCKED" else ("失败" if st == "ERR" else "无列表")
            log.append("链家无头·{c}二手房: 第{p}页{why} → 停止翻页".format(c=city, p=pg, why=why))
            break
        for h in crawlers.parse_ershoufang_html(html, city, budget):
            key = (h["community"], h["price_wan"], h["area"])
            if key not in seen:
                seen.add(key)
                houses.append(h)
        log.append("链家无头·{c}二手房: 第{p}页 → 累计 {n} 条 <={b}万".format(
            c=city, p=pg, n=len(houses), b=budget))
        if pg >= esf_max:
            break
        time.sleep(random.uniform(*PAGE_DELAY))

    plate_rates = {}
    for pg in range(1, zuf_max + 1):
        url = "https://{sub}.lianjia.com/zufang/".format(sub=sub)
        if pg > 1:
            url = "https://{sub}.lianjia.com/zufang/pg{d}/".format(sub=sub, d=pg)
        st, html = _visit(page, url)
        if st != "OK" or "content__list" not in html:
            why = "拦截" if st == "BLOCKED" else ("失败" if st == "ERR" else "无列表")
            log.append("链家无头·{c}租房: 第{p}页{why} → 停止翻页".format(c=city, p=pg, why=why))
            break
        for plate_name, info in crawlers.parse_zufang_html(html).items():
            plate_rates.setdefault(plate_name, []).append(info["rate"])
        if pg >= zuf_max:
            break
        time.sleep(random.uniform(*PAGE_DELAY))

    rent = {}
    for name, rs in plate_rates.items():
        srs = sorted(rs)
        rent[name] = {"rate": round(srs[len(srs) // 2], 2), "samples": len(rs)}
    log.append("链家无头·{c}: 租房聚合到 {n} 个板块租金率".format(c=city, n=len(rent)))
    return {"houses": houses, "rent": rent, "log": log}


def collect_online_headless(cities, budget,
                            esf_max=ESF_MAX_PAGES, zuf_max=ZUF_MAX_PAGES):
    """登录态批量采集入口。返回 (ok, fetched, log)，语义与 crawlers.collect_online 一致。"""
    if not has_saved_state():
        return False, None, ["无本机登录态，跳过登录态批量采集。"]
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return False, None, ["Playwright 不可用({})，跳过登录态批量采集。".format(type(exc).__name__)]

    cookies = _load_cookies()
    log = []
    fetched = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 850},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        for c in cookies:
            try:
                cc = dict(c)
                cc["sameSite"] = {"Lax": "Lax", "Strict": "Strict",
                                  "None": "None"}.get(str(cc.get("sameSite")), "Lax")
                ctx.add_cookies([cc])
            except Exception:  # noqa: BLE001
                pass
        page = ctx.new_page()
        try:
            for city in cities:
                sub = crawlers.LIANJIA_CITY.get(city)
                if not sub:
                    continue
                res = _crawl_city(page, sub, city, budget, esf_max, zuf_max)
                log.extend(res["log"])
                joined = crawlers._join_houses(res["houses"], res["rent"])
                fetched.extend(joined)
                log.append("链家无头·{c}: 关联真实板块租金 {j}/{t} 条".format(
                    c=city, j=len(joined), t=len(res["houses"])))
        finally:
            browser.close()

    if not fetched:
        log.append("登录态批量采集未取到真实数据 → 不输出估算结果")
        return False, None, log
    return True, fetched, log


if __name__ == "__main__":
    ok, data, log = collect_online_headless(["沈阳", "大连"], 30)
    print("headless online:", ok, "条数:", len(data) if data else 0)
    for line in log:
        print(" -", line)
    if data:
        for r in data[:10]:
            print("  ", r["city"], r["plate"], r["community"], r["price_wan"], "万 | 面积",
                  r["area"], "| 参考月租", r["rent"][0], "| 依据率",
                  r["rent_basis"]["rate"], "元/㎡/月")