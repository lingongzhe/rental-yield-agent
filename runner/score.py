# -*- coding: utf-8 -*-
"""打分引擎：把原始房源 + 板块画像合成完整记录，计算投资指标并排序。
纯计算，无 IO，方便单测与复用。
"""
from config import (BUDGET_WAN, YIELD_TARGET, YIELD_MID, NET_YIELD_FLOOR,
                    RENT_EASE_FLOOR, WEIGHTS, W_YIELD, W_EASE, VACANCY_MAP)
from demo_data import PLATE_PROFILE

CUR_YEAR = 2026


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


class PlateDB:
    """板块画像索引。"""

    def __init__(self, profile):
        self._map = {}
        for p in profile:
            key = (p.get("city"), p.get("plate"))
            self._map[key] = p

    def get(self, city, plate):
        return self._map.get((city, plate), {})


def _traffic_score(m):
    if m is None:
        return 45
    if m <= 500:
        return 100
    if m <= 800:
        return 85
    if m <= 1200:
        return 70
    if m <= 1800:
        return 55
    return 40


def _demand_score(d):
    return {0: 35, 1: 60, 2: 80, 3: 100}.get(d, 50)


def _age_score(year, is_elevator):
    age = CUR_YEAR - year
    base = 95 if age <= 20 else 85 if age <= 26 else 72 if age <= 32 else 60 if age <= 38 else 40
    return min(100, base + (5 if is_elevator else 0))


def _supply_score(n):
    if n is None:
        return 60
    if n <= 90:
        return 90
    if n <= 120:
        return 80
    if n <= 180:
        return 65
    if n <= 240:
        return 50
    return 38


def _school_score(study):
    return 100 if study else 60


def enrich(house):
    """给原始房源补全指标，返回完整字典。"""
    plate = PlateDB(PLATE_PROFILE).get(house["city"], house.get("plate", ""))
    risk = plate.get("vacancy_risk", "mid")
    metro_m = plate.get("metro_m_base")
    demand = plate.get("demand", 1)
    study = plate.get("study", 0)
    supply = plate.get("supply")
    metro_line = plate.get("metro_line", "地铁沿线")

    is_elevator = "电梯" in str(house.get("floor", ""))
    price = house["price_wan"] * 10000.0
    rent_mid = float(house["rent"][1])
    annual = rent_mid * 12.0
    rent_yield = annual / price * 100.0 if price else 0.0
    payback = price / annual if annual else 0.0
    vac = VACANCY_MAP.get(risk, 6.0)
    net_yield = annual * (1 - vac / 100.0) / price * 100.0 if price else 0.0

    comps = {
        "traffic": _traffic_score(metro_m) * WEIGHTS["traffic"],
        "demand": _demand_score(demand) * WEIGHTS["demand"],
        "age": _age_score(house["building_year"], is_elevator) * WEIGHTS["age"],
        "supply": _supply_score(supply) * WEIGHTS["supply"],
        "school": _school_score(study) * WEIGHTS["school"],
        "season": 88 * WEIGHTS["season"],   # 9月开学/换租季需求偏旺
    }
    ease = sum(comps.values()) / 100.0

    yield_score = _clamp((rent_yield - YIELD_MID) / (YIELD_TARGET - YIELD_MID) * 100.0)
    penalty = 15.0 if risk == "bad" else 5.0 if risk == "mid" else 0.0
    if CUR_YEAR - house["building_year"] > 40:
        penalty += 10.0
    overall = W_YIELD * yield_score + (1 - W_YIELD) * ease - penalty

    over_budget = house["price_wan"] > BUDGET_WAN
    recommend = (not over_budget) and (net_yield >= NET_YIELD_FLOOR) \
        and (ease >= RENT_EASE_FLOOR) and risk != "bad"

    tags = []
    if over_budget:
        tags.append(("超预算", "bad"))
    if risk == "bad":
        tags.append(("高空置风险", "bad"))
    if CUR_YEAR - house["building_year"] > 40:
        tags.append(("楼龄过老", "bad"))
    if not recommend:
        tags.append(("未达推荐线", "mid"))
    if metro_line:
        tags.append(("%s沿线" % metro_line, "good"))

    reason = _build_reason(house, plate, rent_yield, payback, ease)

    return {
        "city": house["city"], "plate": house.get("plate", ""),
        "community": house["community"], "price_wan": house["price_wan"],
        "area": house["area"], "building_year": house["building_year"],
        "floor": house.get("floor", ""), "rooms": house.get("rooms", ""),
        "rent_low": house["rent"][0], "rent_mid": rent_mid, "rent_high": house["rent"][2],
        "vacancy_risk": risk, "metro_line": metro_line,
        "rent_yield": rent_yield, "payback_years": payback, "net_yield": net_yield,
        "ease_score": round(ease, 1), "yield_score": round(yield_score, 1),
        "overall": round(overall, 1), "over_budget": over_budget,
        "recommend": recommend, "tags": tags, "reason": reason,
    }


def _build_reason(h, plate, y, payback, ease):
    parts = []
    if plate.get("metro_line"):
        parts.append("近" + plate["metro_line"])
    d = plate.get("demand", 0)
    if d >= 3:
        parts.append("商圈/配套需求旺")
    if ease >= 80:
        parts.append("易出租")
    parts.append("回本约%d年" % round(payback))
    return " · ".join(parts)


def run(houses):
    """输入原始房源列表，返回已评分并按综合分排序的记录。"""
    recs = [enrich(h) for h in houses]
    recs.sort(key=lambda r: r["overall"], reverse=True)
    return recs