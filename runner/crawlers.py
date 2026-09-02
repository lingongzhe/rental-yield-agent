# -*- coding: utf-8 -*-
"""在线数据采集模块。

【真实数据原则】只返回真实抓取到的数据；抓取失败时返回空并明确记录原因，
绝不使用内置猜测值。

【采集策略(2026-09 实测修正)】链家风控会拦截无头浏览器(→ hip.lianjia.com/forbidden)，
而普通 urllib 请求能正常拿到 SSR 内嵌的真实挂牌数据。因此：
  1) 主路径 = urllib 直抓，无需浏览器（CI 上同样可用）。
  2) 二手房走『总价40万以下段 /ershoufang/p1/』：低价房源集中，量比默认首页大；
     有本机登录态时还尝试翻页；无登录态(如 CI)则用默认首页兜底。
  3) 租房/ershoufang/、/zufang/ 翻页聚合板块挂牌租金率；有登录态时可翻更多页。
  4) 无头浏览器降级为“仅当 urllib 一条数据都拿不到”时的本地补充尝试。

数据源(链家，全部真实挂牌)：
  1) 二手房在售页 (/ershoufang/)：总价、板块、小区、面积、户型、楼龄。
  2) 租房页     (/zufang/)       ：板块、面积、真实挂牌月租。

关联方式：「板块同档」真实租金——把租房按"板块"聚合出该板块的真实挂牌
租金率(元/㎡/月)中位数，再对同板块的真实在售房，用 真实租金率 × 真实在售面积
估算参考月租。租金全部取自真实挂牌记录（只是套到同板块、不同套的房子）。
板块无真实租金率的在售房，不进入候选（宁缺毋滥）。
"""
import json
import os
import random
import re
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

COLLECT_LOG = []

# 城市 -> 链家子域名
LIANJIA_CITY = {"沈阳": "sy", "大连": "dl"}

# 登录态 cookie 文件（与 headless.login 共用）
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           ".lianjia_cookies.json")

ESF_P1_MAX_PAGES = 3    # 40万以下段最大翻页数（实测第2页即被CAPTCHA拦，留点余地）
ZUF_MAX_PAGES = 6       # 租房最大翻页数（带登录态时实测前5页可用）
PAGE_DELAY = (0.8, 1.5)  # 页间隔随机秒（节流）


def _load_cookie_jar():
    """读取本机保存的链家登录态，拼成 Cookie 头；无则返回 None。"""
    try:
        with open(COOKIE_FILE, encoding="utf-8") as f:
            cks = json.load(f)
        jar = "; ".join("%s=%s" % (c.get("name"), c.get("value"))
                        for c in cks if c.get("name") and c.get("value"))
        return jar or None
    except Exception:  # noqa: BLE001
        return None


def _sleep():
    time.sleep(random.uniform(*PAGE_DELAY))


def _fetch_url(url, cookie_jar=None, timeout=15):
    headers = {"User-Agent": UA, "Accept": "*/*",
               "Accept-Language": "zh-CN,zh;q=0.9",
               "Referer": "https://sy.lianjia.com/"}
    if cookie_jar:
        headers["Cookie"] = cookie_jar
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _page_title(html):
    m = re.search(r"<title>(.*?)</title>", html or "", re.S)
    return (m.group(1).strip() if m else "") or ""


def _page_blocked(html, title="", url=""):
    """链家风控页识别：登录/CAPTCHA/Forbidden 页。"""
    if not html:
        return True
    if "forbidden" in url or "hip.lianjia.com/forbidden" in html:
        return True
    if title.startswith(("登录", "CAPTCHA", "Forbidden")):
        return True
    return False


def _collect_ershoufang(sub, city, budget, jar, log):
    """urllib 抓二手房：40万以下段 p1（翻页) + 默认首页兜底。"""
    houses, seen = [], set()
    urls = []
    if jar:
        urls.append("https://{s}.lianjia.com/ershoufang/p1/".format(s=sub))
        urls += ["https://{s}.lianjia.com/ershoufang/pg{d}/p1/".format(s=sub, d=i)
                 for i in range(2, ESF_P1_MAX_PAGES + 1)]
    urls.append("https://{s}.lianjia.com/ershoufang/".format(s=sub))  # 兜底
    for u in urls:
        label = u.split("lianjia.com/")[-1]
        try:
            html = _fetch_url(u, jar)
        except Exception as exc:  # noqa: BLE001
            log.append("链家·{c}二手房: {p} 抓取失败({t})".format(
                c=city, p=label, t=type(exc).__name__))
            break
        title = _page_title(html)
        if _page_blocked(html, title, u):
            log.append("链家·{c}二手房: {p} {w} → 停止翻页".format(
                c=city, p=label, w=title[:14] or "风控"))
            break
        if "totalPrice" not in html:
            log.append("链家·{c}二手房: {p} 无可解析列表".format(c=city, p=label))
            continue
        for h in parse_ershoufang_html(html, city, budget):
            key = (h["community"], h["price_wan"], h["area"])
            if key not in seen:
                seen.add(key)
                houses.append(h)
        if u.endswith("/ershoufang/"):
            break  # 默认首页只抓一页
        _sleep()
    log.append("链家·{c}: 二手房累计 {n} 条 <={b}万".format(c=city, n=len(houses), b=budget))
    return houses


def _collect_zufang(sub, city, jar, log):
    """urllib 抓租房并聚合板块挂牌租金率（有登录态可多翻几页）。"""
    rates, max_pg = {}, ZUF_MAX_PAGES if jar else 1
    for pg in range(1, max_pg + 1):
        u = ("https://{s}.lianjia.com/zufang/".format(s=sub) if pg == 1
             else "https://{s}.lianjia.com/zufang/pg{d}/".format(s=sub, d=pg))
        try:
            html = _fetch_url(u, jar)
        except Exception as exc:  # noqa: BLE001
            log.append("链家·{c}租房: 第{p}页抓取失败({t})".format(
                c=city, p=pg, t=type(exc).__name__))
            break
        if _page_blocked(html, _page_title(html), u):
            log.append("链家·{c}租房: 第{p}页被风控 → 停止".format(c=city, p=pg))
            break
        if "content__list" not in html:
            log.append("链家·{c}租房: 第{p}页无可解析列表 → 停止".format(c=city, p=pg))
            break
        for name, info in parse_zufang_html(html).items():
            rates.setdefault(name, []).append(info["rate"])
        if pg >= max_pg:
            break
        _sleep()
    rent = {}
    for name, rs in rates.items():
        srs = sorted(rs)
        rent[name] = {"rate": round(srs[len(srs) // 2], 2), "samples": len(rs)}
    log.append("链家·{c}: 聚合到 {n} 个板块的真实挂牌租金率".format(c=city, n=len(rent)))
    return rent


def _collect_urllib(cities, budget, jar, log):
    """urllib 直抓主路径（无需浏览器，CI 亦可用）。"""
    fetched = []
    for city in cities:
        sub = LIANJIA_CITY.get(city)
        if not sub:
            continue
        houses = _collect_ershoufang(sub, city, budget, jar, log)
        rent = _collect_zufang(sub, city, jar, log)
        joined = _join_houses(houses, rent)
        log.append("链家·{c}: 关联真实板块租金 {j}/{t} 条".format(
            c=city, j=len(joined), t=len(houses)))
        fetched.extend(joined)
    return fetched


def _clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _parse_area(text):
    """从 '88.06平米' / '36.00-45.00㎡' 中取面积数值（兼容 平米/㎡ 两种写法）。"""
    m = re.search(r"([\d.]+)\s*(?:平米|㎡)", text or "")
    return float(m.group(1)) if m else None


def parse_ershoufang_html(html, city, budget):
    """从一个二手房列表页 HTML 解析出总价<=budget 的真实房源。"""
    prices = re.findall(r'class="totalPrice totalPrice2">(.*?)</div>', html, re.S)
    pos = re.findall(r'class="positionInfo">(.*?)</div>', html, re.S)
    infos = re.findall(r'class="houseInfo">(.*?)</div>', html, re.S)

    out = []
    for i in range(min(len(prices), len(pos), len(infos))):
        price_wan = None
        m = re.match(r"([\d.]+)\s*万", _clean(prices[i]))
        if m:
            price_wan = float(m.group(1))
        if price_wan is None or price_wan > budget:
            continue

        # 板块：positionInfo "小区 - 板块"
        plate_txt = _clean(pos[i])
        community = None
        plate = plate_txt
        if " - " in plate_txt:
            community = plate_txt.split(" - ", 1)[0].strip()
            plate = plate_txt.split(" - ", 1)[1].strip()
        if not community:
            community = plate_txt

        # 房型/面积/楼龄/楼层
        raw_parts = [_p.strip() for _p in re.split(r"[|]", infos[i]) if _p.strip()]
        parts = [_clean(p) for p in raw_parts if _clean(p)]
        parts = [p for p in parts if p]
        rooms_txt = None
        year_txt = None
        floor_txt = None
        for p in parts:
            if re.match(r"^\d+室", p):
                if rooms_txt is None:
                    rooms_txt = p
            ym = re.search(r"(\d{4})年", p)
            if ym:
                year_txt = int(ym.group(1))
            if "楼层" in p and floor_txt is None:
                floor_txt = p
        area = _parse_area(" ".join(parts))
        room_count = int(re.match(r"(\d+)室", rooms_txt or "").group(1)) \
            if rooms_txt and re.match(r"(\d+)室", rooms_txt) else 1

        out.append({
            "city": city,
            "plate": plate,
            "community": community or "未知",
            "price_wan": price_wan,
            "area": area,
            "building_year": year_txt,
            "floor": floor_txt or "",
            "rooms": rooms_txt or ("%d室" % room_count),
            "room_count": room_count,
        })
    return out


def collect_ershoufang(city, budget):
    """链家二手房在售（总价<=budget 的真实房源）。"""
    sub = LIANJIA_CITY.get(city)
    if not sub:
        return []
    url = "https://{sub}.lianjia.com/ershoufang/".format(sub=sub)
    html = _fetch_url(url)
    if not html or "totalPrice" not in html:
        return []
    return parse_ershoufang_html(html, city, budget)


def parse_zufang_html(html):
    """从一个租房列表页 HTML 聚合出 {板块: 中位租金率(元/㎡/月), 样本数}。"""
    des = re.findall(r'<p class="content__list--item--des">(.*?)</p>', html, re.S)
    prices = re.findall(r'<span class="content__list--item-price">(.*?)</span>', html, re.S)

    plate_rates = {}
    for i in range(min(len(des), len(prices))):
        parts = [p.strip() for p in re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", des[i]))
                 .split("/") if p.strip()]
        area = _parse_area(" ".join(parts))
        # 板块：形如 "大东-八王寺-边墙小区" -> 取中间段；若 '仅剩N间' 开头则跳过
        if not area or not parts or parts[0].startswith("仅剩") or parts[0].startswith("合租"):
            continue
        seg = parts[0]
        if " - " not in seg:
            continue
        segs = [x.strip() for x in seg.split(" - ")]
        if len(segs) < 3:
            continue
        plate = segs[1]
        rent_txt = _clean(prices[i])
        rm = re.search(r"([\d.]+)", rent_txt.replace(",", "").replace(" ", ""))
        if not rm:
            continue
        monthly = float(rm.group(1))
        rate = monthly / area
        if plate not in plate_rates:
            plate_rates[plate] = []
        plate_rates[plate].append(rate)

    out = {}
    for plate, rates in plate_rates.items():
        sorted_rates = sorted(rates)
        out[plate] = {
            "rate": round(sorted_rates[len(sorted_rates) // 2], 2),  # 中位数元/㎡/月
            "samples": len(rates),
        }
    return out


def collect_plate_rent(city):
    """链家租房：聚合同板块真实挂牌租金率(元/㎡/月)中位数(仅首屏)。"""
    sub = LIANJIA_CITY.get(city)
    if not sub:
        return {}
    url = "https://{sub}.lianjia.com/zufang/".format(sub=sub)
    html = _fetch_url(url)
    if not html or "content__list" not in html:
        return {}
    return parse_zufang_html(html)


def _join_houses(houses, plate_rent):
    """用板块真实挂牌租金率为每套在售房估算参考月租(真实口径，同板块套用)。"""
    joined = []
    for h in houses:
        info = plate_rent.get(h["plate"])
        if not info or not h.get("area"):
            continue
        ref_rent = int(round(info["rate"] * h["area"]))
        rec = dict(h)
        rec["rent"] = (ref_rent, ref_rent, ref_rent)
        rec["rent_basis"] = info  # 记录租金估算依据(真实挂牌)
        joined.append(rec)
    return joined


def collect_online(cities, budget):
    """链家真实抓取：urllib 直抓为主，无头浏览器仅做兜底。

    优先级：
      1) urllib 直抓（无需浏览器，本机/CI 均可用）——带登录态自动走
         40万以下低价段+租房翻页（量大），无登录态用免费首页（量小）。
      2) 仅当 urllib 一条数据都没拿到时，才尝试本机登录态无头批量采集
         （链家风控会拦截无头浏览器，实测多为 Forbidden，仅作为补救）。

    真实数据原则：只有能关联到板块真实挂牌租金率的在售房才计入候选；
    全部失败时返回 (False, None, 说明)，交由 main 生成提示页。
    """
    global COLLECT_LOG
    COLLECT_LOG = []
    jar = _load_cookie_jar()
    if jar:
        COLLECT_LOG.append("已加载本机链家登录态({n} cookies) → 走低价段+翻页高量采集".format(
            n=len(jar.split(";")))
        )

    # 【首选源】贝壳官方真实数据（本机已装 beike CLI + Key）：官方租售比/挂牌租金
    beike_data = None
    try:
        import beike_source as _bk
        if _bk.available():
            _bl = []
            _okb, beike_data, _ = _bk.collect_beike(cities, budget, _bl)
            COLLECT_LOG.extend(_bl)
    except Exception as exc:  # noqa: BLE001
        COLLECT_LOG.append("贝壳官方数据源报错({})".format(type(exc).__name__))
    if beike_data:
        COLLECT_LOG.append("→ 本次采用贝壳官方数据源（优先于链家爬虫），共{}条".format(
            len(beike_data)))
        return True, beike_data, COLLECT_LOG

    fetched = _collect_urllib(cities, budget, jar, COLLECT_LOG)

    # urllib 没拿到任何数据时，才轮到无头浏览器补救（可能被风控拦掉）
    if not fetched:
        try:
            import headless as _hd
            ok, extra, log = _hd.collect_online_headless(cities, budget)
            COLLECT_LOG.extend(log)
            if ok and extra:
                fetched = extra
        except Exception as exc:  # noqa: BLE001
            COLLECT_LOG.append("无头补充采集不可用({})".format(type(exc).__name__))

    if not fetched:
        COLLECT_LOG.append("本次未获取到任何真实在线数据 → 不输出估算结果")
        return False, None, COLLECT_LOG
    return True, fetched, COLLECT_LOG


def fallback_houses():
    """已移除猜测样本回退。保证永远返回空，避免影响判断。"""
    return []


if __name__ == "__main__":
    ok, data, log = collect_online(["沈阳", "大连"], 30)
    print("online:", ok, "条数:", len(data) if data else 0)
    for line in log:
        print(" -", line)
    if data:
        for r in data[:6]:
            print("  ", r["plate"], r["community"], r["price_wan"], "万 | 面积", r["area"],
                  "| 参考月租", r["rent"][0], "| 依据率", r["rent_basis"]["rate"], "元/㎡/月")
    print("fallback houses:", len(fallback_houses()))