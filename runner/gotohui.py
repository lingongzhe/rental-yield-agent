# -*- coding: utf-8 -*-
"""gotohui.com(聚汇数据) 城市级市场行情取数模块(补充行情源，非交易主源)。

用途：
  - 抓取沈阳/大连的城市级行情：二手房均价(元/㎡)、新房均价(元/㎡)、月均房租(元/月/㎡)；
  - 你没记错——你之前给的 `fjdata-216` 正是本站的「大连」页(`fjdata-215`=沈阳)，
    而不是 creprice.cn(那个域名下是 404)。本站即"聚汇数据"，房价频道的区县级数据在
    m.gotohui.com/fangjia/{id}，本模块取**城市级**行情做独立交叉校验：与 creprice
    的区县均值相互印证，口径独立。

原则与 beike/creprice 一致：只并入真实抓取到的数值；抓不到只记日志、不伪造、不影响主流程。
离线读上次快照 output/gotohui_data.json。
"""
import io
import json
import os
import re
import time

try:
    import requests
except ImportError:
    requests = None

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "output")
SNAPSHOT = os.path.join(OUT_DIR, "gotohui_data.json")

ENABLE = True
RETRY = 3          # 单页抓取重试次数
TIMEOUT = 25
RATE_GAP = 3.0     # 请求间隔(秒)

# 城市 → 聚汇数据 城市ID（fjdata-{id}，215=沈阳 216=大连）
CITY_ID = {"沈阳": 215, "大连": 216}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://fangjia.gotohui.com/",
}


def _num(s):
    m = re.search(r"[\d.,]+", str(s or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _fetch(url):
    if requests is None:
        return ""
    for att in range(RETRY):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=TIMEOUT)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:          # noqa: BLE001
            if att < RETRY - 1:
                time.sleep(RATE_GAP + 3.0 * att)
    return ""


def parse_city_page(text):
    """从 fjdata-{id} 页提取城市行情。
    返回 {"second_price":元/㎡, "new_price":元/㎡, "rent_rate":元/月/㎡}。
    结构: <div class="pro-quote-label">2026年08月二手房均价</div>
             <div class="pro-quote-value-group"><span class="pro-quote-value">7,875</span>...
          <div class="pro-quote-note">月均房租：25元/月/㎡</div>
    """
    val_pat = (r'pro-quote-label">\s*(\d{4}年\d\d?月(?:二手房均价|新房均价))\s*</div>\s*'
               r'<div class="pro-quote-value-group">\s*'
               r'<span class="pro-quote-value[^"]*">\s*([\d.,]+)\s*</span>')
    first_second = new_price = None
    for m in re.finditer(val_pat, text, re.S):
        kind = m.group(1)
        v = _num(m.group(2))
        if "二手房" in kind and first_second is None:
            first_second = v          # 页面上第一个二手房均价=当前月
        if "新房" in kind:
            new_price = v             # 取最后一个(最新)新房均价
    out = {"second_price": first_second, "new_price": new_price, "rent_rate": None}
    m = re.search(r'月均房租：([\d.]+)\s*元/月/㎡', text)
    out["rent_rate"] = _num(m.group(1)) if m else None
    return out


def collect(cities=("沈阳", "大连"), log=None):
    """抓取各城城市行情。返回 ({city:{...}}, log)。"""
    out_log = log if log is not None else []
    if not ENABLE or requests is None:
        return {c: {} for c in cities}
    result = {}
    for city in cities:
        fid = CITY_ID.get(city)
        if not fid:
            out_log.append("行情·{c}: 聚汇数据无此城市ID".format(c=city))
            result[city] = {}
            continue
        text = _fetch("https://fangjia.gotohui.com/fjdata-%d" % fid)
        if not text:
            out_log.append("行情·{c}: 聚汇数据 fjdata-{id} 抓取失败(已跳过)".format(c=city, id=fid))
            result[city] = {}
            continue
        info = parse_city_page(text)
        info["city"] = city
        got = {k: v for k, v in info.items() if v is not None}
        result[city] = got
        out_log.append("行情·{c}: 聚汇数据 → 二手均价 {p} 元/㎡ · 月均房租 {r} 元/月/㎡".format(
            c=city,
            p=("{:,.0f}".format(got["second_price"]) if got.get("second_price") else "—"),
            r=("{:.0f}".format(got["rent_rate"]) if got.get("rent_rate") else "—")))
        time.sleep(RATE_GAP)
    _write_snapshot(result)
    return result


def city_medians(got):
    """城市行情里可用的租金率中位(元/月/㎡)，用于兜底(与市内各区平均)。"""
    out = {}
    for c, info in got.items():
        r = (info or {}).get("rent_rate")
        if r:
            out[c] = r
    return out


# ---------------------------------------------------------------- 快照
def load_snapshot():
    try:
        with io.open(SNAPSHOT, "r", encoding="utf-8") as f:
            return json.load(f).get("cities") or {}
    except (OSError, ValueError):
        return {}


def _write_snapshot(result):
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with io.open(SNAPSHOT, "w", encoding="utf-8") as f:
            json.dump({"cities": result}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


if __name__ == "__main__":
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    got = collect(("沈阳", "大连"))
    for c, info in got.items():
        print("###", c)
        for k, v in info.items():
            if v is not None:
                print("   %-14s %s" % (k, v))