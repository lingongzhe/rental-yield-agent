# -*- coding: utf-8 -*-
"""creprice.cn(中国房价行情) 区县级市场行情取数模块(补充行情源，非交易主源)。

用途：
  - 抓取沈阳/大连「区县」粒度的真实房价(元/㎡)与挂牌租金(元/月/㎡)；
  - 该行情来自全国房价行情平台(creprice.cn)的公开行列数据，作为贝壳/多平台
    数据源之外的独立行情校验层，写入快照并在报告里展示；
  - 把区县租金率作为「兜底」并入板块租金地图(只有当该区/板块尚未有更精确数据时)，
    让更多房源能关联到真实租金，提高自足场景(贝壳停机)下的覆盖率。

原则：只并入真实抓取到的数值；抓不到只记日志、不伪造、不影响主流程。
离线读上次快照 output/creprice_data.json。
"""
import base64
import io
import json
import os
import re
import time
import urllib.parse

try:
    import requests
except ImportError:          # 标准库 fallback（避免无 requests 时整体崩溃）
    requests = None

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "output")
SNAPSHOT = os.path.join(OUT_DIR, "creprice_data.json")

ENABLE = True
RETRY = 3          # 单页抓取重试次数
TIMEOUT = 25       # 单次请求超时(秒)
RATE_GAP = 4.0     # 请求间间隔(秒)，克制调用、避免触发反爬

# 城市代码 → 城市ID/省份（creprice 用拼音缩写）
CITY_CODE = {"沈阳": "sy", "大连": "dl"}
PROVINCE = "liaoning"
# 区县中文名 → 《区房价/租金表》里出现的标准名（用于兜底匹配，若站点改名可在此修正）
# 不强制：解析直接按表内「区名」，仅当里查询的房子 district 与之一致即可命中。

# 表头单位随房产/租金不同，无需逐一列示，行结构一致：
#   <th>排名</th><th><a>区名</a></th><th><a>城市</a></th><th class=green>单价</th>...
# sale=房价(元/㎡)，rent=租金(元/月/㎡)。
TYPE_PRICE, TYPE_RENT = "sale", "rent"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.creprice.cn/",
}


# ---------------------------------------------------------------- 抓取与解析
def _last_month():
    """数据月份(上月，YYYY-MM)。今日 2026-09-03 → '2026-08'。"""
    now = time.localtime()
    y, m = now.tm_year, now.tm_mon - 1
    if m == 0:
        y, m = y - 1, 12
    return "{:04d}-{:02d}".format(y, m)


def _b64url(payload):
    """区县列表页 URL 里的 base64 参数(与原站 compact JSON 一致)。"""
    s = base64.b64encode(json.dumps(payload, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")).decode("ascii")
    return urllib.parse.quote(s, safe="")


def ranklist_url(city, ty, month=None):
    """构造 区县 {sale房价|rent租金} 列表页 URL。"""
    month = month or _last_month()
    payload = {"di": "all", "pi": PROVINCE, "ci": CITY_CODE[city],
               "dt": "month", "pt": 11, "ty": ty,
               "un": "district", "in": "Price", "mn": month}
    return "https://www.creprice.cn/ranklist/%s.html" % _b64url(payload)


def _fetch(url):
    """带重试的抓取，返回页面文本(失败返回空串)。"""
    if requests is None:
        return ""
    for att in range(RETRY):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=TIMEOUT)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:          # noqa: BLE001
            if att < RETRY - 1:
                time.sleep(RATE_GAP + 4.0 * att)
    return ""


def _parse_district_table(text):
    """从区县列表页提取 {区名: 单价}。行结构与两站一致：
    <tr>...<th>1</th><th><a>和平区</a></th><th><a>沈阳</a></th><th class=green>10920</th>...</tr>
    """
    out = {}
    pat = (r'<th>\s*\d+\s*</th>\s*<th>\s*<a[^>]*>([\u4e00-\u9fa5]{1,6}?区)</a>\s*</th>\s*'
           r'<th>\s*<a[^>]*>\s*[^<]*?</a>\s*</th>\s*<th[^>]*>([\d.,]+)</th>')
    for m in re.finditer(pat, text, re.S):
        try:
            out.setdefault(m.group(1), float(m.group(2).replace(",", "")))
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------- 主流程
def collect(cities=("沈阳", "大连"), log=None):
    """联网抓取各城市区县房价+租金，返回(({city:{区:行情}}, month), log)。

    行情条目结构: {"price_rate": 元/㎡, "rent_rate": 元/月/㎡, "month": 'YYYY-MM'}
    """
    out_log = log if log is not None else []
    if not ENABLE or requests is None:
        return {c: {} for c in cities}, _last_month()
    month = _last_month()
    result = {}
    for city in cities:
        m = {}
        for ty in (TYPE_PRICE, TYPE_RENT):
            url = ranklist_url(city, ty, month)
            text = _fetch(url)
            if not text:
                out_log.append("行情·{c}: creprice {t} 抓取失败(已跳过)".format(
                    c=city, t="租金" if ty == TYPE_RENT else "房价"))
                continue
            table = _parse_district_table(text)
            for name, v in table.items():
                m.setdefault(name, {"price_rate": None, "rent_rate": None, "month": month})
                m[name]["rent_rate" if ty == TYPE_RENT else "price_rate"] = v
            out_log.append("行情·{c}: creprice {t} → {n} 个区县".format(
                c=city, t="租金" if ty == TYPE_RENT else "房价", n=len(table)))
            time.sleep(RATE_GAP)
        result[city] = m
    _write_snapshot(result, month)
    return result, month


def overlay(plate_rents, crep, log=None):
    """把 creprice 区县租金率作为「兜底」并入板块租金地图。

    仅当该区/板块 key 尚未有更精确数据时才补入——贝壳板块、house-cli 区 优先，
    creprice 只填空位，绝不覆盖既有精确数据。返回合并后的地图。
    """
    out_log = log if log is not None else []
    merged = {}
    for city, dist_map in crep.items():
        base = dict(plate_rents.get(city) or {})
        added = 0
        for name, item in dist_map.items():
            rate = (item or {}).get("rent_rate")
            if rate is None:
                continue
            if name not in base:
                base[name] = {"rate": round(rate, 2), "samples": 0, "from": "creprice"}
                added += 1
        if added:
            out_log.append("行情·{c}: 以 creprice 区县租金兜底补入 {n} 个区/板块".format(
                c=city, n=added))
        merged[city] = base
    return merged


# ---------------------------------------------------------------- 快照
def _write_snapshot(crep, month):
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with io.open(SNAPSHOT, "w", encoding="utf-8") as f:
            json.dump({"month": month, "creprice": crep}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_snapshot():
    """读上次行情快照；无则返回 ( {}, '' )。"""
    try:
        with io.open(SNAPSHOT, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("creprice") or {}, d.get("month") or ""
    except (OSError, ValueError):
        return {}, ""


if __name__ == "__main__":
    # 便于单独验证：python runner\creprice.py
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    crep, month = collect(("沈阳", "大连"))
    print("行情月份:", month)
    for city, m in crep.items():
        print("\n###", city)
        for name, it in sorted(m.items(), key=lambda kv: -(kv[1]["rent_rate"] or 0)):
            print("  %-6s 房价 %7s 元/㎡ | 租金 %6s 元/月/㎡" % (
                name,
                ("" if it["price_rate"] is None else "{:,.0f}".format(it["price_rate"])),
                ("" if it["rent_rate"] is None else "{:.2f}".format(it["rent_rate"]))))