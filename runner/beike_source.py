# -*- coding: utf-8 -*-
"""贝壳官方数据源（替换脆弱爬虫的首选源）。

只返回贝壳官方接口返回的『真实挂牌数据』，绝不虚拟：
  1) buy search  → 二手真实在售（总价、面积、户型、楼龄、板块、地铁距离）。
  2) 小区信息里的『租售比』→ 官方口径，直接作为租金依据（最优先）。
  3) 无租售比的小区 → 用该城『真实挂牌租房』按城区聚出的租金率 × 面积估算月租
     （同城区套用，仍是真实挂牌数据，仅挂牌房/出租房为不同套）。
  4) 拿不到任何真实租金依据的房源，不入候选（宁缺毋滥）。

输出房源结构与 crawlers 一致，可直接进 score.run。
"""
import json
import os
import re
import shutil
import subprocess
import sys

CURRENT = "2026-09"

# beike 可执行文件：本机已装到 AppData/Local/beike，其它环境用 PATH 里的 beike。
_BEKE_CANDIDATES = [
    r"C:\Users\zheli\AppData\Local\beike\beike.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "beike", "beike.exe"),
]
_BEKE = None
for p in _BEKE_CANDIDATES:
    if p and os.path.exists(p):
        _BEKE = p
        break
if _BEKE is None:
    _BEKE = shutil.which("beike")

BUY_QUERIES = ("30万以内两居室老房子低价", "主城区老破小低总价", "低价老小区二手房")
RENT_QUERY = "便宜整租"


def available():
    """是否可用（本机装了 beike CLI + Key 才算）。"""
    return _BEKE is not None and _has_key()


def _has_key():
    return bool(os.environ.get("BEIKE_MCP_API_KEY") or
                os.path.exists(os.path.join(os.path.expanduser("~"), ".beike", "BEIKE_MCP_API_KEY")))


def _run(args):
    if not _BEKE:
        return ""
    try:
        r = subprocess.run([_BEKE] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        out = r.stdout or ""
    except Exception:  # noqa: BLE001
        return ""
    # stdout 通常是 ``  {"data":"...","ok":true} `` 一行 JSON；取 data 内的大文本
    chunks = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "data" in obj:
                chunks.append(obj["data"] or "")
                continue
        except Exception:  # noqa: BLE001
            pass
        chunks.append(line)
    return "\n".join(chunks)


def _iter_objects(text):
    """从 CLI 文本里找出所有 `{"摘要信息": {...}}` 顶层对象并还原成 dict。"""
    i, n = 0, len(text)
    while i < n:
        pos = text.find('{"摘要信息"', i)
        if pos < 0:
            break
        depth, j, in_str, esc = 0, pos, False, False
        while j < n:
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        block = text[pos:j + 1]
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and "摘要信息" in obj:
                yield obj["摘要信息"]
        except Exception:  # noqa: BLE001
            pass
        i = j + 1


def _district(loc):
    m = re.search(r"位于\s*([\u4e00-\u9fa5]+?[区市县])", loc or "")
    return m.group(1) if m else None


def _plate(loc, district):
    m = re.search(r"([\u4e00-\u9fa5]+)板块", loc or "")
    return m.group(1) if m else (district or "")


def _parse_buy(city, log):
    """返回真实二手房房源（仅总价<=预算在 parse 时按字段,但预算过滤在调用处）。"""
    houses = []
    seen = set()
    for q in BUY_QUERIES:
        text = _run(["buy", "search", "-c", city, "-q", q])
        for d in _iter_objects(text):
            pid = d.get("房源ID")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            h = _buy_to_house(city, d)
            if h:
                houses.append(h)
    log.append("贝壳·{c}: 原始召回真实二手房 {n} 条".format(c=city, n=len(houses)))
    return houses


def _buy_to_house(city, d):
    m = re.search(r"总价\s*([\d.]+)\s*万", d.get("价格信息") or "")
    if not m:
        return None
    price_wan = float(m.group(1))

    home = d.get("户型信息") or ""
    am = re.search(r"(?:建筑面积|出租面积)\s*([\d.]+)\s*㎡", home)
    area = float(am.group(1)) if am else None
    rmc = re.search(r"(\d+)室", home)
    room_count = int(rmc.group(1)) if rmc else 1

    title = d.get("房源标题") or ""
    tm = re.search(r"^(.+?)\s+?(\d+室\d*厅?)", title)
    community = (tm.group(1) if tm else title.split(" ")[0]).strip()
    rooms = tm.group(2) if tm else ("%d室" % room_count)

    loc = d.get("区位交通") or ""
    district = _district(loc)
    plate = _plate(loc, district)

    comm = d.get("小区信息") or ""
    years = [int(x) for x in re.findall(r"(\d{4})年建成", comm)]
    building_year = max(years) if years else None
    ym = re.search(r"租售比\s*([\d.]+)%", comm)
    yield_pct = float(ym.group(1)) if ym else None

    return {
        "house_id": d.get("房源ID"),
        "city": city,
        "plate": plate,
        "district": district or "",
        "community": community or "未知",
        "price_wan": price_wan,
        "area": area,
        "building_year": building_year,
        "floor": (d.get("房源所在楼层信息") or "").split("，")[0],
        "rooms": rooms,
        "room_count": room_count,
        "location": loc,
        "yield_pct": yield_pct,
    }


def _rent_rates(city, log):
    """按城区聚出真实挂牌租金率(元/㎡/月)中位数。返回 {城区: {rate, samples}}。"""
    agg = {}
    text = _run(["rent", "search", "-c", city, "-q", RENT_QUERY])
    for d in _iter_objects(text):
        if not d.get("房源ID") or not d.get("租赁价格"):
            continue
        dist = _district(d.get("区位交通") or "")
        if not dist:
            continue
        hm = re.search(r"出租面积\s*([\d.]+)\s*㎡", d.get("户型信息") or "")
        rm_ = re.search(r"月租金\s*([\d.]+)\s*元", d.get("租赁价格") or "")
        if not hm or not rm_:
            continue
        area, monthly = float(hm.group(1)), float(rm_.group(1))
        if area <= 0:
            continue
        agg.setdefault(dist, []).append(monthly / area)
    rates = {}
    for dist, rs in agg.items():
        srs = sorted(rs)
        rates[dist] = {"rate": round(srs[len(srs) // 2], 2), "samples": len(rs)}
    log.append("贝壳·{c}: 聚出 {n} 个城市片区的真实挂牌租金率".format(c=city, n=len(rates)))
    return rates


def _attach_rent(city, house, rates):
    """给房源挂真实月租依据；没有依据返回 None。"""
    basis = None
    if house["yield_pct"] is not None:
        annual = house["yield_pct"] / 100.0 * house["price_wan"] * 10000.0
        rent_mid = annual / 12.0
        rate = (rent_mid / house["area"]) if house.get("area") else None
        basis = {"rate": rate, "samples": None,
                 "source": "贝壳官方小区租售比 %.2f%%" % house["yield_pct"]}
    else:
        info = rates.get(house["district"])
        if not info or not house.get("area"):
            return None
        rent_mid = info["rate"] * house["area"]
        basis = {"rate": info["rate"], "samples": info["samples"],
                 "source": "贝壳真实挂牌租金按城区套用"}
    rent = (round(rent_mid), round(rent_mid), round(rent_mid))
    rec = dict(house)
    rec["rent"] = rent
    rec["rent_basis"] = basis
    return rec


def collect_beike(cities, budget, log):
    """贝壳官方真实采集。返回 (ok, houses, log)。"""
    if not available():
        log.append("贝壳官方数据源不可用(未检测到 beike CLI / Bearer Key) → 跳过")
        return False, None, log
    fetched = []
    for city in cities:
        houses = _parse_buy(city, log)
        rates = _rent_rates(city, log)
        joined, kept = [], 0
        # 预算上限放宽3万：主城老破小常>30万(如实标"超预算")，避免静默丢弃
        ceiling = budget + 3
        for h in houses:
            if h["price_wan"] > ceiling:
                continue
            rec = _attach_rent(city, h, rates)
            if rec:
                joined.append(rec)
                kept += 1
        log.append("贝壳·{c}: 预算内且有真实租金依据 {k}/{t} 条".format(
            c=city, k=kept, t=len(houses)))
        fetched.extend(joined)
    if not fetched:
        log.append("贝壳官方：本次未拿到任何有租金依据的真实房源 → 不输出估算")
        return False, None, log
    return True, fetched, log


if __name__ == "__main__":
    import crawlers  # noqa: F401  (路径)
    _log = []
    _ok, _data, _log = collect_beike(["沈阳", "大连"], 30, _log)
    print("beike online:", _ok, "条数:", len(_data) if _data else 0)
    for line in _log:
        print(" -", line)
    if _data:
        for r in _data[:12]:
            print("  ", r["city"], r["plate"], "|", r["community"],
                  "{p}万".format(p=r["price_wan"]), "| {a}㎡".format(a=r["area"]),
                  "| 参考月租", r["rent"][0], "|", r["rent_basis"].get("source"))
    sys.exit(0 if _ok else 2)