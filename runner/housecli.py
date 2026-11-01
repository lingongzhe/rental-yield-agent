# -*- coding: utf-8 -*-
"""可选的多平台取数模块：调用第三方开源工具 house-cli（贝壳/安居客/58/房天下/诸葛等）。

设计目标与 beike.py 一致：
  - 用 subprocess 调 house CLI（等价地，像 beike 调 beike CLI）；
  - 只把 house 真正返回的房源并入快照，不伪造、不估算；
  - 找不到 house CLI 或某平台失败时，只记日志、不影响贝壳主流程。

【自足能力(2026-09 扩展)】贝壳官方 API 停机时，house-cli 也能独立出真实报告：
  - 二手在售：`search --type buy` 归一化成 house 记录；
  - 租房：`search --type rent` 自建「区」粒度挂牌租金率中位地图（house-cli 数据只到区，
    粒度粗于贝壳的板块；两类地图按 key 合并，板块精确匹配优先，城市中位兜底）。

依赖：本机需另装 house-cli（git clone + uv sync），并把 house.exe 所在目录
交给 find_cli() 找到（默认自动探测同目录集合 house-cli/.venv/Scripts/house.exe）。
多数平台需要浏览器 Cookie（详见根目录 README），未登录时仅对应平台失败并跳过。
"""
import json
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))

ENABLE = True
PLATFORM = "fang"              # 仅房天下稳定可采（链家/58/安居客反爬拦截，见根目录 README）
SUBPROCESS_TIMEOUT = 120       # 单城单次搜索最长等待（含 house-cli 自身节流/重试）
RENT_MAX_MONTHLY = 3000        # 租房搜索月租上限（元/月），覆盖老破小出租主力区间


def find_cli():
    exe = os.environ.get("HOUSE_CLI")
    if exe and os.path.exists(exe):
        return exe
    for cand in (
        os.path.join(ROOT, "..", "..", "house-cli", ".venv", "Scripts", "house.exe"),
        os.path.join(ROOT, "..", "..", "house-cli", ".venv", "Scripts", "house"),
        os.path.join(ROOT, "..", "house-cli", ".venv", "Scripts", "house.exe"),
        os.path.join(ROOT, "..", "house-cli", ".venv", "Scripts", "house"),
    ):
        if os.path.exists(cand):
            return cand
    return shutil.which("house") or shutil.which("house.exe")


def _run_search(city, budget, htype):
    """调 house search 取 JSON。返回 (列表, 错误说明)。htype: buy / rent。"""
    exe = find_cli()
    if not exe:
        return [], "未找到 house CLI（house-cli），请先 git clone + uv sync 安装。"
    args = [exe, "search", "--city", city]
    if budget:
        args += ["--max-price", str(budget)]
    args += ["--type", htype, "--platform", PLATFORM,
             "--sort", "price_asc", "--output", "json"]
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=SUBPROCESS_TIMEOUT)
    except FileNotFoundError:
        return [], "未找到 house CLI（house-cli）。"
    except subprocess.TimeoutExpired:
        return [], "house-cli 搜索超时(>{}s)。".format(SUBPROCESS_TIMEOUT)
    out = (r.stdout or "").strip()
    if not out:
        return [], (r.stderr or "").strip() or "无结果"
    try:
        data = json.loads(out)
    except ValueError:
        return [], "house 输出无法解析为 JSON：{s}".format(s=out[:120])
    return (data if isinstance(data, list) else []), ("" if isinstance(data, list)
                                                      else "house 返回非列表结构")


# ---------------------------------------------------------------- 字段映射
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _room_count(layout):
    m = re.match(r"(\d+)室", str(layout or ""))
    return int(m.group(1)) if m else 1


def _to_house(city, item):
    """house-cli 的 in-sale JSON → 本系统 house 记录。"""
    price = _num(item.get("price"))
    area = _num(item.get("area"))
    if not price or not area or price <= 0 or area <= 0:
        return None
    if str(item.get("price_unit") or "") not in (None, "", "万"):
        return None  # 只收"总价万元"的买房结果
    community = str(item.get("community") or "").strip() or "未知"
    platform = str(item.get("platform") or "").strip()
    return {
        "city": city,
        "plate": str(item.get("district") or "").strip(),   # 无板块字段，暂用区名
        "community": community,
        "district": str(item.get("district") or "").strip(),
        "price_wan": price,
        "area": area,
        "building_year": None,
        "rooms": str(item.get("layout") or "").strip() or ("%d室" % _room_count(item.get("layout"))),
        "room_count": _room_count(item.get("layout")),
        "floor": str(item.get("floor") or "").strip(),
        "orientation": str(item.get("orientation") or "").strip(),
        "tags": " ".join(str(t) for t in (item.get("tags") or [])).strip(),
        "listing_time": str(item.get("listing_date") or "").strip(),
        "metro_m": None,
        "comm_name": community,
        "comm_rent_rate": None,
        "repos_yield_pct": None,
        "src_platform": platform if platform else "house",
        "src_url": str(item.get("url") or ""),
    }


# ---------------------------------------------------------------- 自建租房租金地图
def _rent_rate(item):
    """在租挂牌 → (区, 租金率元/㎡/月)；不能识别的返回 None。"""
    rent = _num(item.get("price"))
    area = _num(item.get("area"))
    if not rent or not area or rent <= 0 or area <= 0:
        return None
    unit = str(item.get("price_unit") or "")
    if unit not in ("元/月", ""):
        return None  # 按日/按套/其它单位不算月租金率
    district = str(item.get("district") or "").strip()
    if not district:
        return None
    return district, rent / area


def _build_rent_map(cities, log):
    """house-cli 独立聚合：城市 → 区 → 挂牌租金率中位。贝壳 API 停机时的兜底。"""
    result = {}
    for city in cities:
        raw, err = _run_search(city, RENT_MAX_MONTHLY, "rent")
        if err:
            log.append("多平台·{c} 租房搜索：{e}".format(c=city, e=err[:160]))
            continue
        rates = {}
        for item in raw:
            r = _rent_rate(item)
            if r:
                rates.setdefault(r[0], []).append(r[1])
        m = {}
        for district, rs in rates.items():
            srs = sorted(rs)
            m[district] = {"rate": round(srs[len(srs) // 2], 2),
                           "samples": len(rs), "from": "housecli"}
        result[city] = m
        if m:
            log.append("多平台·{c}: 自建租房挂牌租金率 {n} 个区/板块(贝壳不可用时兜底)".format(
                c=city, n=len(m)))
    return result


# ---------------------------------------------------------------- 房租关联
def _city_median_rate(rents):
    rates = [p["rate"] for p in rents.values() if p and p.get("rate")]
    if not rates:
        return None
    rates.sort()
    return rates[len(rates) // 2]


def _join_house(house, city_rents, housecli_keys, log):
    """给多平台房源配参考租金：板块精确 → 区精确 → 城市中位 → 都没有则跳过。"""
    basis = None
    if house.get("plate") in city_rents:
        p = city_rents[house["plate"]]
        if house["plate"] in housecli_keys:
            src = "house-cli·{c}{p}区租房挂牌租金率中位".format(c=house["city"], p=house["plate"])
        else:
            src = "贝壳·{p}板块挂牌租金率中位".format(p=house["plate"])
        basis = {"rate": p["rate"], "samples": p.get("samples", 0), "source": src}
    else:
        med = _city_median_rate(city_rents)
        if med is not None:
            basis = {"rate": med, "samples": 0,
                     "source": "{c}挂牌租金率中位(板块未匹配)".format(c=house["city"])}
    if not basis:
        log.append("多平台·{c} 跳过：{p}·{cm} 无租金依据".format(
            c=house["city"], p=house.get("plate") or "?", cm=house["community"]))
        return None
    ref = int(round(basis["rate"] * house["area"]))
    h = dict(house)
    h["rent"] = (ref, ref, ref)
    h["rent_basis"] = basis
    return h


# ---------------------------------------------------------------- 去重
def _dedup_key(h):
    return (h["city"], str(h["community"]).strip().lower(),
            round(h["price_wan"]), round(h["area"]))


# ---------------------------------------------------------------- 主入口
def collect(cities, budget, plate_rents, existing=None, log=None):
    """多平台补充采集（贝壳主源 + house-cli 补充 / 或贝壳停机时 house-cli 独立顶班）。

    返回 (新房源列表, 合并后的城市租金地图, 日志列表)。
      - plate_rents: 贝壳快照的板块租金地图（可能为空）。
      - existing: 已并入房源（跨源去重，通常是贝壳快照）。
    合并策略：贝壳板块租金优先；house-cli 自建"区"租金补充；key 精确匹配，城市中位兜底。
    """
    out_log = log if log is not None else []
    if not ENABLE:
        return [], plate_rents, out_log
    if not find_cli():
        out_log.append("多平台: house-cli 未安装，跳过（不影响贝壳数据）。")
        return [], plate_rents, out_log

    # 1) 自建租房租金地图（贝壳停机时也能出真实报告的关键）
    self_map = _build_rent_map(list(cities), out_log)
    merged, housecli_keys = {}, set()
    for city in cities:
        m = dict((plate_rents.get(city) or {}))            # 贝壳板块
        for k, v in (self_map.get(city) or {}).items():    # house-cli 区
            if k not in m:
                m[k] = v
                housecli_keys.add(k)
        merged[city] = m

    # 2) 二手在售搜索 → 归一化/关联租金/去重
    seen = {_dedup_key(h) for h in (existing or [])}
    new_houses = []
    for city in cities:
        raw, err = _run_search(city, budget, "buy")
        if err:
            out_log.append("多平台·{c}: {e}".format(c=city, e=err[:160]))
            continue
        cand, drop = [], 0
        for item in raw:
            h = _to_house(city, item)
            if not h:
                continue
            if h["price_wan"] > budget:      # 与贝壳口径一致：只并入预算内
                continue
            key = _dedup_key(h)
            if key in seen:
                drop += 1
                continue
            seen.add(key)
            cand.append(h)
        joined = [j for h in cand for j in [_join_house(h, merged.get(city) or {}, housecli_keys, out_log)] if j]
        out_log.append("多平台·{c}: 在售候选 {take}，去重 {drop}，成功关联真实租金 {j} 套".format(
            c=city, take=len(cand), drop=drop, j=len(joined)))
        new_houses.extend(joined)
    return new_houses, merged, out_log