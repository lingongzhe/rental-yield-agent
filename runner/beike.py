# -*- coding: utf-8 -*-
"""官方贝壳 API 取数模块（本 app 唯一数据源）。

数据全部来自贝壳官方开放平台（beike CLI + 用户自己的 API Key），
不爬页面、不估算、不伪造：
  - buy search  → 按低价段/城区检索在售二手房，收集房源ID
  - buy detail  → 逐套拿完整挂牌卡片（总价/面积/房型/楼龄/商圈/小区），
                  顺带拿到官方「小区租售比 / 小区租房均价」——租售比指标的直接依据
  - rent search → 在租挂牌：板块、出租面积、月租金 → 按板块聚合中位租金率(元/月/㎡)

输出为 JSON 快照（output/beike_data.json）。main.py --refresh 调本模块联网更新；
无参数运行时直接读快照重建报告（离线可用）。手动更新数据 = 重跑一次 --refresh。
"""
import json
import os
import re
import shutil
import subprocess
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "output")
SNAPSHOT = os.path.join(OUT_DIR, "beike_data.json")
CUR_YEAR = 2026

MAX_HOUSE_DETAIL = 60    # 每城最多抓多少套详情（够用且有节流）
RETRY = 4                # 服务偶发不可用（限流/大连等）时的重试次数（含指数退避）
QUERY_GAP = 1.0          # 每次查询间的小间隔（秒），克制调用
DETAIL_GAP = 0.6         # 详情调用间隔（秒）
MAX_CONSEC_FAIL = 8      # 连续失败这么多就停止本轮尝试（防限流失控）

# 城市 → 主城区（老破小集中，逐区检索以扩大候选池）
CITY_DISTRICTS = {
    "沈阳": ["和平", "沈河", "大东", "皇姑", "铁西", "苏家屯", "于洪", "沈北"],
    "大连": ["中山", "西岗", "沙河口", "甘井子", "金州", "旅顺口"],
}
PRICE_QUERIES = ["总价20万以内 二手房", "总价25万以内 二手房", "总价30万以内 二手房"]
DISTRICT_PRICE = "{} 30万以内 二手房"
RENT_QUERIES = ["1000元以内 整租", "1500元以内 整租", "2000元以内 整租"]
DISTRICT_RENT = "{} 整租"

LOG = []  # 本次取数说明日志（会写进报告"数据来源"区）


class BeikeError(Exception):
    pass


# ---------------------------------------------------------------- CLI 与调用
def find_cli():
    """定位 beike CLI：环境变量 > PATH > 本机默认安装路径。"""
    exe = os.environ.get("BEIKE_CLI") or shutil.which("beike")
    if exe:
        return exe
    for c in (os.path.expanduser(r"~/AppData/Local/beike/beike.exe"),
              os.path.expanduser("~/.local/bin/beike")):
        if os.path.exists(c):
            return c
    return "beike"


def _run(args):
    """执行 beike 命令并解析返回。

    注意：服务异常时 beike 可能在 stdout 连排多个 JSON 文档，且错误信息为
    'service temporarily unavailable'（限流/短暂故障）。此类错误按可重试处理。
    """
    exe = find_cli()
    last = None
    wait = 0.0
    for idx in range(RETRY + 1):
        if wait:
            time.sleep(wait)
        try:
            r = subprocess.run([exe] + args, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
        except FileNotFoundError:
            raise BeikeError("未找到贝壳 CLI(beike.exe)，请先按官方安装命令安装。")
        except subprocess.TimeoutExpired:
            last = BeikeError("贝壳 CLI 超时")
            wait = 3.0
            continue
        text = r.stdout or r.stderr or ""
        data = None
        for o in _json_objects(text):
            if isinstance(o, dict) and "ok" in o:   # 取最后一个完整的 JSON 信封
                data = o
        if data is None:
            last = BeikeError("贝壳返回无法解析：{}".format(text[:120]))
            wait = 2.0
            continue
        if data.get("ok") is False:
            msg = str(data.get("error") or "unknown")[:120]
            last = BeikeError(msg)
            if "unavailable" in msg.lower():
                # 限流多发生在整套业务上，指数退避后再试
                wait = 3.0 * (2 ** idx)
                continue
            raise last
        payload = data.get("data", "")
        if isinstance(payload, str) and "service temporarily unavailable" in payload.lower():
            last = BeikeError("服务临时不可用")
            wait = 3.0 * (2 ** idx)
            continue
        return data
    raise last if last else BeikeError("贝壳 CLI 连续失败")


# ---------------------------------------------------------------- 文本解析
def _json_objects(text):
    """提取顶层平衡的 {…} JSON 对象（贝壳卡片即以这些对象内嵌于文本）。

    只把双引号当作 JSON 字符串界定符，避免正文里用单引号写列表(如
    ['10210…'])干扰括号配对；解析失败的对象静默跳过即可。
    """
    objs, i, n = [], 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth, j, quote = 0, i, False
        while j < n:
            ch = text[j]
            if quote:
                if ch == "\\":
                    j += 2
                    continue
                if ch == '"':
                    quote = False
            elif ch == '"':
                quote = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth == 0 and j < n:
            try:
                objs.append(json.loads(text[i:j + 1]))
            except ValueError:
                pass
        i = j + 1
    return objs


def _num(s):
    m = re.search(r"([\d.]+)", str(s or "").replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_wan(s):
    """'32万' → 32.0；'暂无'/None → None。"""
    return _num(s)


def _parse_area(s):
    return _num(s)


def _metro_m(traffic):
    """从『周边交通』里取最近地铁步行距离（米），无则 None。"""
    if not isinstance(traffic, list):
        return None
    dists = [_num(t) for t in traffic]
    dists = [int(d) for d in dists if d]
    return min(dists) if dists else None


# ---------------------------------------------------------------- 贝壳卡片解析
def parse_house_card(text, city):
    """buy detail → 我方 house 记录（真实挂牌字段；缺失即 None）。"""
    objs = _json_objects(text)
    base = comm = traffic = None
    for o in objs:
        if "基础信息" in o:
            base = o["基础信息"]
        elif "基本信息" in o:
            comm = o["基本信息"]
        elif "周边交通" in o:
            traffic = o["周边交通"]
    if not base:
        return None
    price = _parse_wan(base.get("总价"))
    area = _parse_area(base.get("建筑面积"))
    if price is None or not area:
        return None
    building_year = _num(base.get("建成年代"))
    if not building_year:
        age = _num(base.get("楼龄"))
        if age:
            building_year = CUR_YEAR - int(age)
    rooms = str(base.get("房型") or "")
    mm = re.match(r"(\d+)室", rooms)
    room_count = int(mm.group(1)) if mm else 1
    rec = {
        "city": city,
        "plate": str(base.get("商圈") or "").strip(),
        "community": str(base.get("小区") or "").strip() or "未知",
        "district": str(base.get("城区") or "").strip(),
        "price_wan": price,
        "area": area,
        "building_year": int(building_year) if building_year else None,
        "rooms": rooms or ("%d室" % room_count),
        "room_count": room_count,
        "floor": str(base.get("房源所属楼层") or "").strip(),
        "orientation": str(base.get("朝向") or "").strip(),
        "tags": str(base.get("标签") or "").strip(),
        "listing_time": str(base.get("挂牌时间") or "").strip(),
        "metro_m": _metro_m(traffic),
        "comm_name": (comm or {}).get("小区名称") if isinstance(comm, dict) else None,
        "comm_rent_rate": _num(comm.get("租房均价")) if isinstance(comm, dict) else None,
        "repos_yield_pct": _num(comm.get("租售比")) if isinstance(comm, dict) else None,
    }
    return rec


def parse_rent_cards(text, city):
    """rent search → [{plate, area, rent(mid), whole, house_info, rent_id}]。"""
    out = []
    for o in _json_objects(text):
        s = o.get("摘要信息")
        if not isinstance(s, dict):
            continue
        loc = str(s.get("区位交通") or "")
        # 形如「位于浑南区新南站板块…」/「位于沈北新区正良板块…」：取"区"之后、板块之前
        pm = re.search(r"区([一-龥A-Za-z0-9\-]{1,10})板块", loc)
        hi = str(s.get("户型信息") or "")
        am = re.search(r"出租面积([\d.]+)㎡", hi)
        if not pm or not am:
            continue
        rm = re.search(r"月租金([\d.]+)元", str(s.get("租赁价格") or ""))
        if not rm:
            continue
        out.append({
            "city": city,
            "plate": pm.group(1),
            "area": float(am.group(1)),
            "rent": float(rm.group(1)),
            "whole": "合租" not in hi,
            "house_info": hi,
            "rent_id": str(s.get("房源ID") or ""),
        })
    return out


# ------------------------------------------------------------------ 取数主流程
def collect_house_ids(city, log):
    """多组 buy search 查询 → 去重收集在售房源ID（连续失败到阈值即止损）。"""
    ids, consec_fail = [], 0
    for q in PRICE_QUERIES + [DISTRICT_PRICE.format(d) for d in CITY_DISTRICTS.get(city, [])]:
        before = set(ids)
        try:
            data = _run(["buy", "search", "-c", city, "-q", q,
                         "--house-type", "second", "--json"])
            got = set(re.findall(r"'(\d{9,})'", str(data.get("data") or "")))
            consec_fail = 0
        except BeikeError as e:
            consec_fail += 1
            log.append("贝壳·{c} 查询『{q}』失败：{e}".format(c=city, q=q, e=e))
            if consec_fail >= MAX_CONSEC_FAIL:
                log.append("贝壳·{c}: 连续失败 {k} 次(疑似限流)，停止本轮尝试".format(c=city, k=consec_fail))
                break
            continue
        fresh = [u for u in sorted(got - before)]
        ids += fresh
        log.append("贝壳·{c} 查询『{q}』→ 新收录 {n} 个ID(累计 {t})".format(
            c=city, q=q, n=len(fresh), t=len(ids)))
        time.sleep(QUERY_GAP)
    return ids


def collect_rent(city, log):
    """多组 rent search → 板块 → 中位租金率(元/月/㎡)+样本数。"""
    rates, consec_fail = {}, 0
    for q in RENT_QUERIES + [DISTRICT_RENT.format(d) for d in CITY_DISTRICTS.get(city, [])]:
        try:
            data = _run(["rent", "search", "-c", city, "-q", q, "--json"])
            cards = parse_rent_cards(str(data.get("data") or ""), city)
            consec_fail = 0
        except BeikeError as e:
            consec_fail += 1
            log.append("贝壳·{c} 租房『{q}』失败：{e}".format(c=city, q=q, e=e))
            if consec_fail >= MAX_CONSEC_FAIL:
                log.append("贝壳·{c}: 连续失败 {k} 次(疑似限流)，停止本轮尝试".format(c=city, k=consec_fail))
                break
            continue
        for c in cards:
            if c["whole"] and c["area"] > 0:
                rates.setdefault(c["plate"], []).append(c["rent"] / c["area"])
        log.append("贝壳·{c} 租房『{q}』→ {n} 条在租挂牌".format(c=city, q=q, n=len(cards)))
        time.sleep(QUERY_GAP)
    out = {}
    for plate, rs in rates.items():
        srs = sorted(rs)
        out[plate] = {"rate": round(srs[len(srs) // 2], 2), "samples": len(rs)}
    log.append("贝壳·{c}: 聚合到 {n} 个板块的中位挂牌租金率".format(c=city, n=len(out)))
    return out


def _join_house(house, plate_rents, log):
    """给真实在售房配参考租金（真实口径）：
    优先官方『小区租房均价』；没有则用同板块挂牌租金率中位数；都没有则不估算。"""
    basis = None
    if house["comm_rent_rate"]:
        basis = {"rate": house["comm_rent_rate"], "samples": 0,
                 "source": "贝壳·小区租房均价({})".format(
                     house["comm_name"] or house["community"])}
    elif house.get("plate") in plate_rents:
        p = plate_rents[house["plate"]]
        basis = {"rate": p["rate"], "samples": p["samples"],
                 "source": "贝壳·{}板块挂牌租金率中位数".format(house["plate"])}
    if not basis:
        log.append("贝壳·{c} 跳过：{p}·{cm} 暂无租金依据(不估算)".format(
            c=house["city"], p=house.get("plate") or "?", cm=house["community"]))
        return None
    ref = int(round(basis["rate"] * house["area"]))
    h = dict(house)
    h["rent"] = (ref, ref, ref)  # 官方挂牌口径；真实波动未知，不虚构区间
    h["rent_basis"] = basis
    return h


def refresh(cities, budget=30):
    """联网更新贝壳数据 → 写快照。返回 (ok, dataset, log)。"""
    global LOG
    LOG = []
    collected, plate_rents = [], {}
    for city in cities:
        log = []
        ids = collect_house_ids(city, log)
        log.append("贝壳·{c}: 检索去重后 {n} 个在售房源ID".format(c=city, n=len(ids)))

        got, consec_fail = [], 0
        for i, uid in enumerate(ids[:MAX_HOUSE_DETAIL]):
            try:
                data = _run(["buy", "detail", "-c", city, "--id", uid,
                             "-t", "house", "--json"])
                rec = parse_house_card(str(data.get("data") or ""), city)
                consec_fail = 0
            except BeikeError as e:
                consec_fail += 1
                log.append("贝壳·{c} 详情 {id} 失败：{e}".format(c=city, id=uid, e=e))
                rec = None
                if consec_fail >= MAX_CONSEC_FAIL:
                    log.append("贝壳·{c}: 详情连续失败 {k} 次(疑似限流)，停止本轮尝试".format(
                        c=city, k=consec_fail))
                    break
            if rec and rec["price_wan"] <= budget:
                got.append(rec)
            if (i + 1) % 15 == 0 and i + 1 < len(ids):
                log.append("贝壳·{c}: 详情进度 {i}/{n}".format(c=city, i=i + 1, n=len(ids)))
            time.sleep(DETAIL_GAP)
        log.append("贝壳·{c}: 拿到 {n} 套真实挂牌 <={b}万".format(c=city, n=len(got), b=budget))

        pr = collect_rent(city, log)
        plate_rents[city] = pr

        joined = [j for h in got for j in [_join_house(h, pr, log)] if j]
        log.append("贝壳·{c}: 关联真实租金 {j}/{t} 套".format(c=city, j=len(joined), t=len(got)))
        collected.extend(joined)
        LOG += log

    if not collected:
        LOG.append("本次未从贝壳 API 获取到任何候选 → 不输出估算结果")
        return False, None, LOG

    ds = {
        "source": "beike-api 官方贝壳开放平台",
        "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
        "cities": list(cities),
        "budget": budget,
        "houses": collected,
        "plate_rents": plate_rents,
        "log": LOG,
    }
    _write_snapshot(ds)
    return True, ds, LOG


def _write_snapshot(ds):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(ds, f, ensure_ascii=False, indent=1)


def load_snapshot():
    """读上次快照（离线重建报告用）。"""
    if not os.path.exists(SNAPSHOT):
        return None
    try:
        with open(SNAPSHOT, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return None