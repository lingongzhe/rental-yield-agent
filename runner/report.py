# -*- coding: utf-8 -*-
"""傻瓜式可视化报告生成：纯标准库拼装 HTML+CSS+内联SVG，零 JS 依赖，双击即可打开。
布局已优化为现代卡片式：深色标题横幅 → KPI → 结论 → 板块对比图 →
两城双列房源卡片 → 全量明细表 → 数据来源。
"""
from config import BUDGET_WAN, TOP_N, CURR_FILE

# 主题色（与蓝图一致）
C_ACCENT, C_ACCENT2, C_WARN, C_BAD = "#1a66ff", "#10a37f", "#e08a2e", "#d64550"


def _yield_color(y):
    if y >= 4.0:
        return C_ACCENT2
    if y >= 3.5:
        return C_WARN
    return C_BAD


def _tag_html(tag):
    name, kind = tag
    color = {"good": C_ACCENT2, "mid": C_WARN, "bad": C_BAD}.get(kind, C_ACCENT)
    bg = {"good": "#e7f7f0", "mid": "#fdf0df", "bad": "#fbeaea"}.get(kind, "#eaf0ff")
    return '<span class="tag" style="color:%s;background:%s">%s</span>' % (color, bg, name)


# ---------- 板块对比条形图 ----------
def bar_svg(title, cats, vals, unit="", limit=None, limit_label=""):
    """横向条形图 SVG：cats 标签、vals 数值、limit 参考线。"""
    n = len(cats)
    H = max(40, n * 46 + 52)
    W = 940
    pad_l, pad_r, pad_t, pad_b = 232, 46, 46, 24
    plot_w = W - pad_l - pad_r
    maxv = max(vals + [limit if limit else 0.0]) * 1.18
    rows = []
    for i, (t, v) in enumerate(zip(cats, vals)):
        y = pad_t + i * 46 + 6
        bw = plot_w * (v / maxv)
        color = C_ACCENT if t.startswith("沈阳") else C_ACCENT2
        rows.append(
            '<text x="%d" y="%d" font-family="Microsoft YaHei" font-size="14" font-weight="600" '
            'fill="#3a4560" text-anchor="end">%s</text>' % (pad_l - 14, y + 18, t))
        rows.append(
            '<rect x="%d" y="%d" width="%d" height="26" rx="13" fill="%s"/>' % (pad_l, y, bw, color))
        rows.append(
            '<rect x="%d" y="%d" width="5" height="26" fill="rgba(255,255,255,.35)"/>' % (pad_l + bw, y))
        rows.append(
            '<text x="%d" y="%d" font-family="Microsoft YaHei" font-size="14" font-weight="700" '
            'fill="#1b2333">%s%s</text>' % (pad_l + bw + 10, y + 18, v, unit))
    if limit is not None:
        lx = pad_l + plot_w * (limit / maxv)
        rows.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2" stroke-dasharray="6,5"/>'
                    % (lx, pad_t - 8, lx, pad_t + n * 46, C_WARN))
        rows.append('<g><circle cx="%d" cy="%d" r="9" fill="%s"/>'
                    '<text x="%d" y="%d" font-size="11" fill="#fff" font-weight="700" '
                    'text-anchor="middle">!</text></g>' % (lx, 26, C_WARN, lx, 31))
        rows.append('<text x="%d" y="%d" font-family="Microsoft YaHei" font-size="13" fill="%s" '
                    'font-weight="600">%s</text>' % (lx + 14, 30, C_WARN, limit_label))
    svg = (
        '<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:auto">'
        '<text x="%d" y="28" font-family="Microsoft YaHei" font-size="18" font-weight="700" '
        'fill="#1b2333">%s</text>%s</svg>'
    ) % (W, H, pad_l, title, "".join(rows))
    return svg


# ---------- 房源卡片 ----------
def house_card(r, idx):
    is_sy = (r["city"] == "沈阳")
    cls = "sy" if is_sy else "dl"
    city_color = C_ACCENT if is_sy else C_ACCENT2
    city_emblem = "沈" if is_sy else "连"
    tag_html = "".join(_tag_html(t) for t in r["tags"])
    ycolor = _yield_color(r["rent_yield"])
    yw = max(3, r["rent_yield"] / 7.5 * 100)
    ew = max(3, r["ease_score"])
    rank_txt = ("No.%d" % idx) if r["recommend"] else "备选"
    budget_color = "#0a8a6a" if not r["over_budget"] else C_BAD
    budget_bg = "#e7f7f0" if not r["over_budget"] else "#fbeaea"
    budget_txt = "预算内达标" if not r["over_budget"] else "超预算(已排除)"
    return """
    <article class="card {cls}">
      <div class="accent-bar"></div>
      <div class="card-head">
        <span class="emblem" style="background:{city_color}">{city_emblem}</span>
        <div class="t">
          <div class="plate">{plate}</div>
          <div class="comm">{community}</div>
        </div>
        <span class="rank" style="color:{city_color}">{rank_txt}</span>
      </div>
      <div class="meta">{rooms} · {area}㎡ · {floor} · {year}年建</div>
      <div class="nums">
        <div class="num"><div class="lab">总价</div><div class="val strong">{price}万</div></div>
        <div class="num"><div class="lab">估算月租</div><div class="val strong">{rent}元</div></div>
        <div class="num"><div class="lab">租售比</div><div class="val strong" style="color:{ycolor}">{yld}%</div></div>
        <div class="num"><div class="lab">回本年限</div><div class="val">{payback}年</div></div>
        <div class="num"><div class="lab">出租易度</div><div class="val">{ease}</div></div>
        <div class="num"><div class="lab">综合分</div><div class="val strong accent">{overall}</div></div>
      </div>
      <div class="bars">
        <div class="bar-row"><span class="b-lab">租售比</span>
          <div class="bar"><div class="fill" style="width:{yw}%;background:{ycolor}"></div></div>
          <span class="b-val">{yld}%</span></div>
        <div class="bar-row"><span class="b-lab">易出租</span>
          <div class="bar"><div class="fill" style="width:{ew}%;background:{barc}"></div></div>
          <span class="b-val">{ease}</span></div>
      </div>
      <div class="foot">
        <div class="reason">{reason}</div>
        <div class="tags">{tags}<span class="tag" style="color:{budget_color};background:{budget_bg}">{budget_txt}</span></div>
      </div>
    </article>
    """.format(
        cls=cls, city_color=city_color, city_emblem=city_emblem, rank_txt=rank_txt,
        plate=r["plate"], community=r["community"], rooms=r["rooms"], area=r["area"],
        floor=r["floor"], year=r["building_year"], price=r["price_wan"], rent=r["rent_mid"],
        yld=r["rent_yield"], payback=round(r["payback_years"]), ease=r["ease_score"],
        overall=r["overall"], reason=r["reason"], tags=tag_html if tag_html else "—",
        budget_color=budget_color, budget_bg=budget_bg, budget_txt=budget_txt,
        ycolor=ycolor, barc=C_ACCENT if is_sy else C_ACCENT2, yw=yw, ew=ew,
    ).lstrip()


def build_html(msg, recs, coll_log, online):
    """组合最终 HTML 报告。recs: 全量排序记录。"""
    by_city = {}
    for r in recs:
        by_city.setdefault(r["city"], []).append(r)

    rec_ok = [r for r in recs if r["recommend"]]
    best_sy = best_dl = None
    for r in recs:
        if r["recommend"]:
            if r["city"] == "沈阳" and best_sy is None:
                best_sy = r
            if r["city"] == "大连" and best_dl is None:
                best_dl = r

    # KPI
    kpi = (
        '<div class="kpis">'
        '<div class="kpi"><div class="n">{n}</div><div class="l">推荐标的 · 两城合计</div></div>'
        '<div class="kpi"><div class="n">{sy}</div><div class="l">沈阳 · 最佳租售比</div></div>'
        '<div class="kpi"><div class="n">{dl}</div><div class="l">大连 · 最佳租售比</div></div>'
        '<div class="kpi"><div class="n">&lt;{b}万</div><div class="l">单价红线 · 总价上限</div></div>'
    ).format(n=len(rec_ok),
             sy=("%.1f%%" % best_sy["rent_yield"]) if best_sy else "—",
             dl=("%.1f%%" % best_dl["rent_yield"]) if best_dl else "—",
             b=int(BUDGET_WAN))

    verdict = _verdict(rec_ok)

    cards_sy = "".join(house_card(r, i) for i, r in enumerate(
        [x for x in by_city.get("沈阳", []) if x["recommend"]][:TOP_N], 1))
    cards_dl = "".join(house_card(r, i) for i, r in enumerate(
        [x for x in by_city.get("大连", []) if x["recommend"]][:TOP_N], 1))

    # 板块对比
    sysy = [r for r in recs if r["city"] == "沈阳"]
    dl = [r for r in recs if r["city"] == "大连"]
    sysy_agg, dl_agg = {}, {}
    for r in sysy:
        sysy_agg.setdefault(r["plate"], []).append(r["rent_yield"])
    for r in dl:
        dl_agg.setdefault(r["plate"], []).append(r["rent_yield"])
    _agg = lambda d: {k: round(sum(v) / len(v), 1) for k, v in d.items()}
    sa, da = _agg(sysy_agg), _agg(dl_agg)
    cats = (["沈阳·" + k for k in sa] + ["大连·" + k for k in da])[:12]
    vals = list(sa.values()) + list(da.values())
    bar = bar_svg("重点板块 · 30万内老破小 年租金回报率 (%)", cats, vals,
                  unit="%", limit=4.0, limit_label="推荐线 4.0%")

    # 明细表
    table_rows = []
    for r in recs[:24]:
        yc = _yield_color(r["rent_yield"])
        mark = ('<span class="tb-ok">推荐</span>' if r["recommend"] else '—')
        shape = (
            "<tr><td>{city}</td><td>{plate}</td><td>{community}</td>"
            "<td class=\"num\">{price}</td><td class=\"num\">{rent}</td>"
            "<td class=\"num\"><b style=\"color:{yc}\">{yld}%</b></td>"
            "<td class=\"num\">{payback}</td><td class=\"num\">{net}%</td>"
            "<td class=\"num\">{ease}</td><td class=\"num\"><b>{overall}</b></td>"
            "<td>{mark}</td></tr>"
        ).format(city=r["city"], plate=r["plate"], community=r["community"],
                 price=r["price_wan"], rent=r["rent_mid"], yc=yc, yld=r["rent_yield"],
                 payback=round(r["payback_years"]), net=r["net_yield"],
                 ease=r["ease_score"], overall=r["overall"], mark=mark)
        table_rows.append(shape)
    table = "".join(table_rows)

    src_html = ""
    for line in coll_log:
        src_html += '<div class="log">• ' + line + "</div>"

    html = _TEMPLATE.format(
        date=CURR_FILE, kpi=kpi, verdict=verdict, bar=bar, top=TOP_N,
        b0=int(BUDGET_WAN), city_sy="沈阳 · 候选清单", city_dl="大连 · 候选清单",
        cards_sy=cards_sy, cards_dl=cards_dl, table_rows=table,
        src_html=src_html, msg=msg, online=online,
    )
    return html


def _verdict(rec_ok):
    if not rec_ok:
        return ('<div class="callout warn"><b>结论：</b>当前配置下暂无达标标的。<br>'
                '总价≤30万的房源要么租售比不足4%、要么出租易度低于60。'
                '<br>可尝试放宽 config.py 中的阈值后重新运行。</div>')
    top = rec_ok[0]
    txt = ("优先考虑 <b>{plate} · {community}</b>：估算月租约{rent}元、"
           "租售比{yld}%、约{payback}年回本、出租易度{ease}分。").format(
               plate=top["plate"], community=top["community"], rent=top["rent_mid"],
               yld=top["rent_yield"], payback=round(top["payback_years"]),
               ease=top["ease_score"])
    return '<div class="callout ok"><span class="c-ico">✦</span><div><b>结论</b><p>' + txt + "</p></div></div>"


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>沈阳·大连 30万内老破小 收租筛选报告</title>
<style>
  :root{{--accent:#1a66ff;--accent2:#10a37f;--warn:#e08a2e;--bad:#d64550;
        --ink:#1b2333;--muted:#64708c;--rule:#e6eaf3;--bg:#eef1f8;}}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:var(--ink);
       background:var(--bg);line-height:1.6;font-size:15px;
       background-image:radial-gradient(90rem 54rem at 8% -4%,rgba(26,102,255,.08),transparent 60%),
                        radial-gradient(80rem 52rem at 100% 10%,rgba(16,163,127,.08),transparent 60%);}}
  .wrap{{max-width:1020px;margin:0 auto;padding:26px 18px 64px}}

  /* --- 标题横幅 --- */
  .hero{{background:linear-gradient(135deg,#16224f 0%,#1d3a78 48%,#0e8a74 100%);
        border-radius:22px;padding:40px 36px 32px;color:#fff;
        box-shadow:0 14px 40px rgba(22,34,79,.28);position:relative;overflow:hidden}}
  .hero::after{{content:"";position:absolute;right:-60px;top:-60px;width:230px;height:230px;
        border-radius:50%;background:rgba(255,255,255,.07)}}
  .badges{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}}
  .badges span{{font-size:12px;font-weight:700;letter-spacing:.03em;color:#e8f0ff;
        border:1px solid rgba(255,255,255,.35);background:rgba(255,255,255,.12);
        padding:4px 12px;border-radius:999px}}
  .hero h1{{font-size:30px;font-weight:800;letter-spacing:-.3px;margin:0 0 8px}}
  .hero .sub{{color:rgba(255,255,255,.78);font-size:13.5px}}
  .hero .kv{{display:flex;gap:22px;flex-wrap:wrap;margin-top:18px}}
  .hero .kv div{{font-size:13px;color:rgba(255,255,255,.85)}}
  .hero .kv b{{color:#fff;font-weight:700}}

  /* --- 区块标题 --- */
  .sec-t{{display:flex;align-items:center;gap:10px;margin:34px 0 14px}}
  .sec-t .dot{{width:10px;height:10px;border-radius:3px;
      background:linear-gradient(135deg,var(--accent),var(--accent2))}}
  .sec-t h2{{font-size:20px;font-weight:800;margin:0;letter-spacing:-.2px}}
  .sec-t .cnt{{font-size:12px;color:var(--muted);font-weight:600;background:rgba(255,255,255,.7);
      border:1px solid var(--rule);padding:2px 10px;border-radius:999px}}

  /* --- KPI --- */
  .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-top:22px}}
  .kpi{{background:rgba(255,255,255,.86);border:1px solid var(--rule);border-radius:16px;
       padding:16px 18px;box-shadow:0 2px 8px rgba(27,35,51,.04)}}
  .kpi .n{{font-size:30px;font-weight:800;letter-spacing:-.5px;
       background:linear-gradient(135deg,var(--accent),var(--accent2));
       -webkit-background-clip:text;background-clip:text;color:transparent}}
  .kpi .l{{font-size:12.5px;color:var(--muted);margin-top:3px}}

  /* --- 结论 --- */
  .callout{{display:flex;align-items:flex-start;gap:12px;background:rgba(255,255,255,.86);
       border:1px solid var(--rule);border-left:5px solid var(--accent);
       border-radius:14px;padding:16px 18px;margin:18px 0;box-shadow:0 2px 10px rgba(27,35,51,.05)}}
  .callout.ok{{border-left-color:var(--accent2)}}
  .callout.warn{{border-left-color:var(--warn)}}
  .callout .c-ico{{font-size:20px;line-height:1.4;color:var(--accent2)}}
  .callout b{{font-size:15px;color:var(--ink)}}
  .callout p{{margin:6px 0 0;color:#3a4560}}

  /* --- 对比图面板 --- */
  .panel{{background:rgba(255,255,255,.86);border:1px solid var(--rule);border-radius:18px;
        padding:20px 22px;box-shadow:0 2px 10px rgba(27,35,51,.04)}}

  /* --- 房源卡片（双列） --- */
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}}
  .card{{position:relative;background:#fff;border:1px solid var(--rule);border-radius:16px;
        overflow:hidden;display:flex;flex-direction:column;
        box-shadow:0 3px 14px rgba(27,35,51,.05);transition:.15s}}
  .card:hover{{transform:translateY(-2px);box-shadow:0 10px 26px rgba(27,35,51,.10)}}
  .card .accent-bar{{height:5px;width:100%}}
  .card.sy .accent-bar{{background:linear-gradient(90deg,var(--accent),var(--accent2))}}
  .card.dl .accent-bar{{background:linear-gradient(90deg,var(--accent2),var(--accent))}}
  .card-head{{display:flex;align-items:center;gap:12px;padding:14px 16px 0}}
  .card-head .emblem{{flex:0 0 38px;height:38px;border-radius:11px;color:#fff;font-weight:800;
        font-size:18px;display:flex;align-items:center;justify-content:center}}
  .card-head .t{{flex:1;min-width:0}}
  .card-head .plate{{font-size:15.5px;font-weight:700}}
  .card-head .comm{{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .card-head .rank{{font-size:12px;font-weight:800;letter-spacing:.04em}}
  .meta{{color:var(--muted);font-size:12px;margin:6px 16px 12px;padding-bottom:10px;
        border-bottom:1px dashed var(--rule)}}
  .nums{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:0 16px}}
  .num{{background:#f6f8fc;border:1px solid var(--rule);border-radius:10px;padding:7px 9px}}
  .num .lab{{font-size:11px;color:var(--muted)}}
  .num .val{{font-size:16px;font-weight:600;margin-top:1px;color:var(--ink)}}
  .num .val.strong{{font-weight:800}}
  .num .val.accent{{color:var(--accent)}}
  .bars{{margin:12px 16px 8px}}
  .bar-row{{display:flex;align-items:center;gap:9px;margin:6px 0}}
  .b-lab{{width:52px;font-size:12px;color:var(--muted)}}
  .bar{{flex:1;height:9px;background:#eef1f8;border-radius:6px;overflow:hidden}}
  .fill{{height:100%;border-radius:6px}}
  .b-val{{width:44px;font-size:12px;color:var(--ink);font-weight:700;text-align:right}}
  .foot{{margin-top:auto;padding:10px 16px 14px;border-top:1px solid var(--rule);
        background:#fbfcfe;border-radius:0 0 16px 16px}}
  .reason{{font-size:13px;color:#3a4560;margin:0 0 8px}}
  .tags{{display:flex;flex-wrap:wrap;gap:6px}}
  .tag{{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 9px;border-radius:999px}}

  /* --- 表格 --- */
  .table-wrap{{overflow-x:auto;border:1px solid var(--rule);border-radius:16px;background:#fff;
        box-shadow:0 2px 10px rgba(27,35,51,.04)}}
  table{{border-collapse:collapse;width:100%;min-width:760px;font-size:13.5px}}
  th{{position:sticky;top:0;z-index:1;background:#f2f5fb;text-align:left;padding:10px 12px;
       color:var(--muted);font-weight:700;border-bottom:1px solid var(--rule)}}
  td{{padding:9px 12px;border-bottom:1px solid var(--rule)}}
  tr:last-child td{{border-bottom:none}}
  tr:nth-child(even) td{{background:rgba(94,110,150,.045)}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}}
  .tb-ok{{color:#0a8a6a;font-weight:700;background:#e7f7f0;padding:1px 8px;border-radius:999px;font-size:12px}}

  /* --- 来源/说明 --- */
  .log{{font-size:12.5px;color:var(--muted);background:#fff;border:1px solid var(--rule);
       border-radius:14px;padding:12px 16px}}
  .log div{{padding:2px 0}}
  .gamma{{font-size:12px;color:var(--muted);margin-top:16px}}

  @media(max-width:680px){{
    body{{font-size:14px}}
    .wrap{{padding:16px 12px 40px}}
    .hero{{padding:26px 20px;border-radius:18px}}
    .hero h1{{font-size:23px}}
    .grid{{grid-template-columns:1fr}}
    .nums{{grid-template-columns:repeat(3,1fr)}}
  }}
</style>
</head>
<body><div class="wrap">

  <header class="hero">
    <div class="badges"><span>纯投资收租</span><span>沈阳</span><span>大连</span>
      <span>总价 &lt;30万</span><span>多源爬取 + 评分</span></div>
    <h1>沈阳 · 大连  30万内老破小「收租」筛选报告</h1>
    <div class="sub">生成日期 {date} · 由智能体自动计算并打分 · 仅供参考，不构成投资建议</div>
    <div class="kv"><div>预算红线（万元）<b>&nbsp;&lt; {b0}</b></div>
      <div>数据来源<b>&nbsp;贝壳官方 · 真实在售/挂牌租金</b></div>
      <div>筛选维度<b>&nbsp;租售比 · 回本 · 出租易度</b></div></div>
    {kpi}
  </header>

  {verdict}

  <div class="panel">{bar}</div>

  <div class="sec-t"><span class="dot"></span><h2>{city_sy}</h2>
    <span class="cnt">候选 {top} 席 · 蓝色系</span></div>
  <div class="grid">{cards_sy}</div>

  <div class="sec-t"><span class="dot"></span><h2>{city_dl}</h2>
    <span class="cnt">候选 {top} 席 · 青色系</span></div>
  <div class="grid">{cards_dl}</div>

  <div class="sec-t"><span class="dot"></span><h2>全量明细</h2>
    <span class="cnt">含未达标与风险源</span></div>
  <div class="table-wrap"><table>
    <thead><tr><th>城市</th><th>板块</th><th>小区</th><th>总价/万</th><th>月租/元</th>
    <th>租售比</th><th>回本/年</th><th>净回报</th><th>出租易度</th><th>综合分</th><th>状态</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table></div>

  <div class="sec-t"><span class="dot"></span><h2>数据来源</h2></div>
  <div class="log">{src_html}</div>

  <p class="gamma">数据说明：总价/面积/楼龄/小区租售比来自贝壳官方接口真实挂牌；月租优先用官方小区租售比折算，缺省时按同城区贝壳真实挂牌租金率(元/㎡/月)×在售面积估算（租售比=年租金÷总价，未扣空置税费）。实际空置率、交通、学区等维度暂无真实数据，未纳入评分，请结合实地核验。</p>
</div></body>
</html>
"""


def write_report(path, html):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def build_no_data_html(date, coll_log, offline=False):
    """没有任何真实数据时生成的提示页：明确告知，不估算、不打分。"""
    src_html = "".join('<div class="log">• ' + (line or "") + "</div>" for line in coll_log)
    if offline:
        tip = ("本次以离线模式运行，未采集任何真实数据。程序不会用估算值代替，"
               "因此不生成任何推荐结果。请在有网络时在线运行，或接入可用的真实数据源。")
    else:
        tip = ("本次联网采集未获取到任何真实房源/板块数据（可能因目标平台反爬限制）。"
               "为避免用虚拟数据影响你的判断，程序不输出任何估算分数或推荐标的。")
    return _NO_DATA_TEMPLATE.format(date=date, src_html=src_html, tip=tip)


_NO_DATA_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>未获取到真实数据 · 沈阳大连老破小收租筛选</title>
<style>
  :root{{--accent:#1a66ff;--accent2:#10a37f;--warn:#e08a2e;--bad:#d64550;
        --ink:#1b2333;--muted:#64708c;--rule:#e6eaf3;--bg:#eef1f8;}}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:var(--ink);
       background:var(--bg);line-height:1.7;font-size:15px}}
  .wrap{{max-width:760px;margin:0 auto;padding:48px 20px}}
  .box{{background:#fff;border:1px solid var(--rule);border-radius:20px;padding:34px 30px;
        box-shadow:0 8px 30px rgba(27,35,51,.08)}}
  .badge{{display:inline-block;background:#fdf0df;color:var(--warn);font-weight:800;
         font-size:12.5px;padding:3px 12px;border-radius:999px;letter-spacing:.05em}}
  h1{{font-size:24px;margin:16px 0 8px}}
  p{{color:#3a4560;margin:6px 0}}
  .tip{{background:#fdf0df;border-left:5px solid var(--warn);border-radius:12px;
       padding:14px 16px;margin:20px 0}}
  .log{{font-size:12.5px;color:var(--muted);margin-top:18px}}
  .log div{{padding:3px 0;border-bottom:1px dashed var(--rule)}}
  a{{color:var(--accent)}}
</style></head>
<body><div class="wrap"><div class="box">
  <span class="badge">真实数据原则</span>
  <h1>本次未获取到真实数据</h1>
  <p>为了不误导你的判断，本程序只展示真实抓取到的数据。本次运行没有拿到任何真实的房源或板块数据，
     因此<b>不生成任何估算分数、不输出推荐标的</b>。</p>
  <div class="tip"><b>说明：</b>{tip}</div>
  <p>可选做法：</p>
  <p>① 稍后在有网络的电脑上重试在线采集；</p>
  <p>② 接入一个可用的真实数据源（自备数据文件/API 即可），由程序读取真实数据后再评分。</p>
  <div class="log">数据采集日志：{src_html}
    <div>生成日期 {date}</div>
  </div>
</div></div></body></html>
"""