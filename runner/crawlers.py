# -*- coding: utf-8 -*-
"""在线数据采集模块。

【真实数据原则】只返回真实抓取到的数据；抓取失败时返回空并明确记录原因，
绝不使用内置猜测值。

数据源(链家首页首屏，反爬允许的稳定入口)：
  1) 二手房在售页 (/ershoufang/)：总价、板块、小区、面积、户型、楼龄。全部真实。
  2) 租房页     (/zufang/)       ：板块、面积、真实挂牌月租。全部真实。

关联方式：「板块同档」真实租金——把租房按"板块"聚合出该板块的真实挂牌
租金率(元/㎡/月)中位数，再对同板块的真实在售房，用 真实租金率 × 真实在售面积
估算参考月租。租金全部取自真实挂牌记录（只是套到同板块、不同套的房子）。
板块无真实租金率的在售房，不进入候选（宁缺毋滥）。
"""
import re
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

COLLECT_LOG = []

# 城市 -> 链家子域名
LIANJIA_CITY = {"沈阳": "sy", "大连": "dl"}


def _fetch_url(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _parse_area(text):
    """从 '88.06平米' / '36.00-45.00㎡' 中取面积数值（兼容 平米/㎡ 两种写法）。"""
    m = re.search(r"([\d.]+)\s*(?:平米|㎡)", text or "")
    return float(m.group(1)) if m else None


def collect_ershoufang(city, budget):
    """链家二手房在售（总价<=budget 的真实房源）。"""
    sub = LIANJIA_CITY.get(city)
    if not sub:
        return []
    url = "https://{sub}.lianjia.com/ershoufang/".format(sub=sub)
    html = _fetch_url(url)
    if not html or "totalPrice" not in html:
        return []

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


def collect_plate_rent(city):
    """链家租房：聚合同板块真实挂牌租金率(元/㎡/月)中位数。

    返回 {板块名: {"rate": 元/㎡/月中位, "samples": 样本条数}}。
    只统计"区 - 板块 - 小区"完整、且有面积的真实挂牌。
    """
    sub = LIANJIA_CITY.get(city)
    if not sub:
        return {}
    url = "https://{sub}.lianjia.com/zufang/".format(sub=sub)
    html = _fetch_url(url)
    if not html or "content__list" not in html:
        return {}

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


def collect_online(cities, budget):
    """链家真实抓取：二手房总价 + 租房板块租金率 => 关联出候选房源。

    全部失败时返回 (False, None, 说明)，交由 main 生成提示页。
    对真实在售房，仅当所在板块存在真实挂牌租金率时才计入；否则宁缺毋滥。
    """
    global COLLECT_LOG
    COLLECT_LOG = []
    fetched = []
    for city in cities:
        houses = []
        try:
            houses = collect_ershoufang(city, budget)
            COLLECT_LOG.append("链家二手房·{}: 取得 {} 条 <={}万的真实在售房源".format(city, len(houses), budget))
        except Exception as exc:  # noqa: BLE001
            COLLECT_LOG.append("链家二手房·{}: 抓取失败({})".format(city, type(exc).__name__))

        plate_rent = {}
        try:
            plate_rent = collect_plate_rent(city)
            COLLECT_LOG.append("链家租房·{}: 解析到 {} 个板块的真实挂牌租金率".format(city, len(plate_rent)))
        except Exception as exc:  # noqa: BLE001
            COLLECT_LOG.append("链家租房·{}: 抓取失败({})".format(city, type(exc).__name__))

        joined = 0
        for h in houses:
            info = plate_rent.get(h["plate"])
            if not info or not h.get("area"):
                continue
            ref_rent = int(round(info["rate"] * h["area"]))
            rec = dict(h)
            rec["rent"] = (ref_rent, ref_rent, ref_rent)
            rec["rent_basis"] = info  # 记录租金估算依据(真实挂牌)
            fetched.append(rec)
            joined += 1
        COLLECT_LOG.append("链家·{}: 关联真实板块租金 {}/{} 条".format(city, joined, len(houses)))

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