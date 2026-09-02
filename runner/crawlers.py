# -*- coding: utf-8 -*-
"""在线数据采集模块。
三个平台(贝壳/链家、安居客、58同城)的采集函数。反爬强且本站需遵守条款，
因此采取"尽力抓取 + 失败安全回退"策略：任一平台取数失败不影响整体，
main 会用 demo_data 兜底，并在报告中明确标注数据来源。
"""
import json
import urllib.request

from demo_data import DEMO_HOUSES

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

COLLECT_LOG = []


def _fetch_url(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def collect_beike(city, budget):
    """贝壳/链家：优先数据源。示例接入点，按需替换为合规的检索接口。"""
    return None


def collect_anjuke(city, budget):
    """安居客：补充验证源。"""
    return None


def collect_58(city, budget):
    """58同城：低价老破小覆盖源。"""
    return None


def collect_online(cities, budget):
    """尝试各平台联网采集；全部失败时返回(False, None, 说明)。"""
    global COLLECT_LOG
    COLLECT_LOG = []
    fetched = []
    for city in cities:
        for name, fn in (("贝壳/链家", collect_beike),
                         ("安居客", collect_anjuke),
                         ("58同城", collect_58)):
            try:
                rows = fn(city, budget)
                if rows:
                    fetched.extend(rows)
                    COLLECT_LOG.append("{}·{}. 取得 {} 条".format(name, city, len(rows)))
            except Exception as exc:  # noqa: BLE001  联网失败属预期，回退
                COLLECT_LOG.append("{}·{}: 网络/反爬失败({}). 已跳过".format(name, city, type(exc).__name__))
    if not fetched:
        COLLECT_LOG.append("未获取到在线数据 → 使用内置行情样本(默认自动回退)")
        return False, None, COLLECT_LOG
    return True, fetched, COLLECT_LOG


def fallback_houses():
    """内置行情样本 → 统一为结构化字典列表。"""
    return [dict(h) for h in DEMO_HOUSES]


if __name__ == "__main__":
    ok, data, log = collect_online(["沈阳", "大连"], 30)
    print("online:", ok)
    for line in log:
        print(" -", line)
    print("fallback houses:", len(fallback_houses()))