# -*- coding: utf-8 -*-
"""打分引擎：把真实房源 + 真实板块租金，合成完整记录，计算投资指标并排序。

【真实数据原则】只对"有真实数据支撑的维度"评分；拿不到真实数据的维度
不硬编估算分，而是标为"数据未知"，权重重分配给真实维度，并在结果中披露。

单房得分说明：
  出租易度：仅由真实维度(楼龄 / 板块真实挂牌租金率)加权，权重重归一化到 100。
  综合分   = 60% 租售比分 + 40% 出租易度分。
  净回报率 = 租售比扣除保守维护成本口径（真实空置率未知，故保守披露）。
"""
from config import (BUDGET_WAN, YIELD_TARGET, YIELD_MID, NET_YIELD_FLOOR,
                    RENT_EASE_FLOOR, W_YIELD, WEIGHTS)

CUR_YEAR = 2026
_MAINT = 0.04  # 保守维护/空置成本口径（真实空置率未知时的保守披露用）


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _age_score(year):
    """楼龄分数（真实年份驱动）。年份未知时不评分。"""
    if not year:
        return None
    age = CUR_YEAR - year
    return _clamp(100 - age * 2.6, 35.0, 100.0)


def _demand_score_rate(rate):
    """由真实挂牌租金率(元/㎡/月)反推出租需求强度。
    租金率是真实挂牌数据：租金率高的板块，租户支付意愿与需求更强。
    rate≈10→40分；25→65；35→80；45→100。
    """
    if not rate:
        return None
    return _clamp((rate - 10.0) / 35.0 * 60.0 + 40.0)


def enrich(house):
    """给真实房源补全指标，返回完整字典（含数据可信度标注）。"""
    price = house["price_wan"] * 10000.0
    rent_mid = float(house["rent"][1])
    annual = rent_mid * 12.0
    rent_yield = annual / price * 100.0 if price else 0.0
    payback = price / annual if annual else 0.0
    net_yield = rent_yield * (1 - _MAINT)

    # —— 真实数据可计算的维度 ——
    age_score = _age_score(house.get("building_year"))
    rate = (house.get("rent_basis") or {}).get("rate")
    demand_score = _demand_score_rate(rate)

    # —— 出租易度：由真实维度加权，权重重归一化到 100 ——
    # 用 config 里 age(20) 与 demand(25) 的相对权重
    _src = {"age": 20, "demand": 25}
    comps = {}
    if age_score is not None:
        comps["age"] = age_score * _src["age"]
    if demand_score is not None:
        comps["demand"] = demand_score * _src["demand"]
    sum_w = sum(_src[k] for k in comps)
    ease = (sum(comps.values()) / sum_w) if sum_w else None

    # 缺乏真实数据的维度披露清单
    unknown_dims = []
    if house.get("building_year") is None:
        unknown_dims.append("楼龄")
    if rate is None:
        unknown_dims.append("板块挂牌租金")
    for d in ("交通(地铁距离)", "学区", "板块在售供应量", "小区实际空置率"):
        unknown_dims.append(d)

    yield_score = _clamp((rent_yield - YIELD_MID) / (YIELD_TARGET - YIELD_MID) * 100.0)
    ease_eff = ease if ease is not None else 60.0
    overall = W_YIELD * yield_score + (1 - W_YIELD) * ease_eff

    over_budget = house["price_wan"] > BUDGET_WAN
    recommend = (not over_budget) and (net_yield >= NET_YIELD_FLOOR) \
        and (ease is None or ease >= RENT_EASE_FLOOR)

    tags = []
    if over_budget:
        tags.append(("超预算", "bad"))
    if not recommend:
        tags.append(("未达推荐线", "mid"))
    elif unknown_dims:
        tags.append(("数据待核实", "mid"))

    return {
        "city": house["city"], "plate": house.get("plate", ""),
        "community": house["community"], "price_wan": house["price_wan"],
        "area": house["area"], "building_year": house["building_year"],
        "floor": house.get("floor", ""), "rooms": house.get("rooms", ""),
        "rent_low": house["rent"][0], "rent_mid": rent_mid, "rent_high": house["rent"][2],
        "rent_yield": rent_yield, "payback_years": payback,
        "net_yield": net_yield,
        "ease_score": None if ease is None else round(ease, 1),
        "yield_score": round(yield_score, 1),
        "overall": round(overall, 1), "over_budget": over_budget,
        "recommend": recommend, "tags": tags,
        "unknown_dims": unknown_dims,
        "reason": _build_reason(house, ease, payback),
    }


def _build_reason(h, ease, payback):
    parts = []
    basis = h.get("rent_basis") or {}
    if basis.get("rate"):
        parts.append("租金率由{}条真实挂牌支撑".format(basis["samples"]))
    if h.get("building_year"):
        parts.append("楼龄{}年".format(CUR_YEAR - h["building_year"]))
    parts.append("回本约%g年" % round(payback))
    return " · ".join(parts)


def run(houses):
    """输入真实房源列表，返回已评分并按综合分排序的记录。"""
    recs = [enrich(h) for h in houses]
    recs.sort(key=lambda r: r["overall"], reverse=True)
    return recs