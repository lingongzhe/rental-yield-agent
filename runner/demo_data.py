# -*- coding: utf-8 -*-
"""内置行情样本。
爬虫联网失败/遇反爬时会自动回退到这份数据，保证报告永远可生成。
数值取自2026年沈阳/大连30万内老破小的真实行情区间（见蓝图 Sources）。
"""

# 板块画像：city -> (district, plate)
# vacancy_risk: good=空置低, mid=一般, bad=空置高(容易租不出去)
# demand: 需求与配套强度 0-3
PLATE_PROFILE = [
    # ---------------- 沈阳 ----------------
    {"city": "沈阳", "district": "皇姑区", "plate": "皇姑-长江街", "metro_m_base": 450, "demand": 3, "study": 1, "supply": 88, "vacancy_risk": "good"},
    {"city": "沈阳", "district": "大东区", "plate": "大东-沈阳大学北", "metro_m_base": 600, "demand": 3, "study": 1, "supply": 102, "vacancy_risk": "good"},
    {"city": "沈阳", "district": "沈河区", "plate": "沈河-青年大街", "metro_m_base": 500, "demand": 3, "study": 1, "supply": 120, "vacancy_risk": "good"},
    {"city": "沈阳", "district": "和平区", "plate": "和平-太原街北", "metro_m_base": 480, "demand": 3, "study": 1, "supply": 96, "vacancy_risk": "good"},
    {"city": "沈阳", "district": "铁西区", "plate": "铁西-兴顺/北二路", "metro_m_base": 720, "demand": 2, "study": 0, "supply": 134, "vacancy_risk": "good"},
    {"city": "沈阳", "district": "于洪区", "plate": "于洪-远郊段", "metro_m_base": 2100, "demand": 0, "study": 0, "supply": 260, "vacancy_risk": "bad"},
    {"city": "沈阳", "district": "苏家屯区", "plate": "苏家屯-主街", "metro_m_base": 2600, "demand": 0, "study": 0, "supply": 230, "vacancy_risk": "bad"},
    # ---------------- 大连 ----------------
    {"city": "大连", "district": "甘井子区", "plate": "泡崖/泉水", "metro_m_base": 800, "demand": 2, "study": 0, "supply": 180, "vacancy_risk": "mid"},
    {"city": "大连", "district": "甘井子区", "plate": "金州-万达商圈", "metro_m_base": 600, "demand": 3, "study": 1, "supply": 98, "vacancy_risk": "good", "metro_line": "3号线"},
    {"city": "大连", "district": "西岗区", "plate": "西岗-八一路", "metro_m_base": 700, "demand": 2, "study": 1, "supply": 76, "vacancy_risk": "good"},
    {"city": "大连", "district": "沙河口区", "plate": "沙河口-黑石礁周边", "metro_m_base": 550, "demand": 3, "study": 1, "supply": 90, "vacancy_risk": "good"},
    {"city": "大连", "district": "中山区", "plate": "中山-老街区", "metro_m_base": 750, "demand": 2, "study": 1, "supply": 70, "vacancy_risk": "good"},
    {"city": "大连", "district": "旅顺口区", "plate": "旅顺-老城区", "metro_m_base": 3200, "demand": 0, "study": 0, "supply": 150, "vacancy_risk": "bad"},
]

# 演示房源：总价/面积/楼龄/楼层/户型 + 每月租金(低/中/高) + 关联板块
DEMO_HOUSES = [
    # ---------------- 沈阳 ----------------
    {"city": "沈阳", "plate": "皇姑-长江街", "community": "前进小区", "price_wan": 20.0, "area": 38, "building_year": 2000, "floor": "中层/6", "rooms": "1室1厅", "rent": (820, 900, 1000)},
    {"city": "沈阳", "plate": "皇姑-长江街", "community": "新新小区", "price_wan": 29.5, "area": 57, "building_year": 1996, "floor": "低层/6", "rooms": "1室1厅", "rent": (1080, 1200, 1350)},
    {"city": "沈阳", "plate": "皇姑-长江街", "community": "重型小区", "price_wan": 27.0, "area": 48, "building_year": 1995, "floor": "中层/6", "rooms": "1室1厅", "rent": (1000, 1150, 1250)},
    {"city": "沈阳", "plate": "大东-沈阳大学北", "community": "小北大学城公寓", "price_wan": 20.0, "area": 44, "building_year": 1998, "floor": "中层/6", "rooms": "1室1厅", "rent": (900, 1000, 1150)},
    {"city": "沈阳", "plate": "大东-沈阳大学北", "community": "山水文园", "price_wan": 25.0, "area": 50, "building_year": 1997, "floor": "低层/6", "rooms": "2室1厅", "rent": (980, 1100, 1250)},
    {"city": "沈阳", "plate": "沈河-青年大街", "community": "房地产大厦公寓", "price_wan": 26.8, "area": 40, "building_year": 1995, "floor": "高层/电梯", "rooms": "1室1厅", "rent": (1080, 1200, 1350)},
    {"city": "沈阳", "plate": "沈河-青年大街", "community": "永环社区", "price_wan": 29.9, "area": 42, "building_year": 1993, "floor": "中层/6", "rooms": "1室1厅", "rent": (1100, 1250, 1400)},
    {"city": "沈阳", "plate": "和平-太原街北", "community": "马路湾延安里", "price_wan": 29.0, "area": 28, "building_year": 1990, "floor": "高层/7", "rooms": "1室0厅", "rent": (1000, 1150, 1300)},
    {"city": "沈阳", "plate": "和平-太原街北", "community": "砂山医院旁小区", "price_wan": 26.0, "area": 35, "building_year": 1994, "floor": "中层/6", "rooms": "1室1厅", "rent": (900, 1000, 1100)},
    {"city": "沈阳", "plate": "铁西-兴顺/北二路", "community": "兴顺工业区宿舍", "price_wan": 23.0, "area": 45, "building_year": 1998, "floor": "中层/6", "rooms": "1室1厅", "rent": (880, 980, 1080)},
    {"city": "沈阳", "plate": "于洪-远郊段", "community": "于洪远郊老高层", "price_wan": 20.0, "area": 55, "building_year": 1997, "floor": "高层/7", "rooms": "2室1厅", "rent": (700, 800, 900)},
    {"city": "沈阳", "plate": "苏家屯-主街", "community": "苏家屯老小区", "price_wan": 22.0, "area": 60, "building_year": 1995, "floor": "中层/6", "rooms": "2室1厅", "rent": (650, 750, 850)},
    # ---------------- 大连 ----------------
    {"city": "大连", "plate": "泡崖/泉水", "community": "泡崖六区", "price_wan": 30.0, "area": 62, "building_year": 1993, "floor": "中层/6", "rooms": "2室1厅", "rent": (980, 1100, 1250)},
    {"city": "大连", "plate": "泡崖/泉水", "community": "椒房小区", "price_wan": 18.0, "area": 40, "building_year": 1998, "floor": "中层/6", "rooms": "1室1厅", "rent": (720, 800, 900)},
    {"city": "大连", "plate": "金州-万达商圈", "community": "金州万达旁公寓", "price_wan": 30.0, "area": 56, "building_year": 1998, "floor": "高层/电梯", "rooms": "1室1厅", "rent": (1250, 1400, 1550)},
    {"city": "大连", "plate": "金州-万达商圈", "community": "金州城中村改造房", "price_wan": 22.0, "area": 34, "building_year": 1996, "floor": "中层/6", "rooms": "1室1厅", "rent": (850, 950, 1100)},
    {"city": "大连", "plate": "西岗-八一路", "community": "八一路老旧院", "price_wan": 28.0, "area": 30, "building_year": 1995, "floor": "中层/6", "rooms": "1室0厅", "rent": (900, 1000, 1100)},
    {"city": "大连", "plate": "沙河口-黑石礁周边", "community": "黑石礁高校租房", "price_wan": 29.0, "area": 40, "building_year": 1994, "floor": "高层/7", "rooms": "1室1厅", "rent": (1350, 1500, 1650)},
    {"city": "大连", "plate": "沙河口-黑石礁周边", "community": "李家街老小区", "price_wan": 22.0, "area": 40, "building_year": 1993, "floor": "中层/6", "rooms": "1室1厅", "rent": (800, 900, 1000)},
    {"city": "大连", "plate": "中山-老街区", "community": "中山老街区一室", "price_wan": 29.0, "area": 41, "building_year": 1991, "floor": "高层/7", "rooms": "1室1厅", "rent": (1080, 1200, 1350)},
    {"city": "大连", "plate": "旅顺-老城区", "community": "旅顺老城区两室", "price_wan": 25.0, "area": 63, "building_year": 1995, "floor": "中层/6", "rooms": "2室1厅", "rent": (700, 800, 900)},
]