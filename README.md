# 沈阳 · 大连 30万内老破小「收租」筛选智能体

纯 Python 标准库 + **贝壳官方开放平台**真实挂牌数据：贝壳官方 API 取数 → 清洗 → 租售比/出租易度评分 → 综合投资分 → 生成**傻瓜式可视化报告**。数据真实、合规、可手动随时更新。

## 快速使用

- 首次准备：在本机安装贝壳 CLI 并配置 API Key（仅存本机）：

  ```bash
  curl -fsSL https://raw.githubusercontent.com/LianjiaTech/beike-ai-platform/master/cli/releases/install.sh | bash
  beike auth <你的Key> --save && beike doctor
  ```

- **手动更新数据**（联网，约几分钟）：`python runner\main.py --refresh`

- **出报告**（读上次贝壳快照，离线秒出）：`python runner\main.py`

- 或双击 `runner\run.bat`（A=联网更新，B=快照重建）。

## 更新机制

- **手动更新**：随时 `main.py --refresh` → 经贝壳官方 API 获取最新挂牌数据 → 覆盖本地快照 `runner/output/beike_data.json` → 重建报告。

- **自动/每日**：本机 `deploy\push_daily.bat`（Windows 计划任务）走 `--refresh` 更新后 push 回仓库；GitHub Pages 随之更新。贝壳 API Key 不进仓库（`beike_data.json` 快照会提交，供预览/CI 一致性重建）。

- GitHub Actions（`.github/workflows/daily.yml`）只从仓库内快照重建，**无真实数据时不会覆盖线上**。

## 可选：接入 house-cli 多平台补充数据源（安居客 / 58同城 / 房天下 / 诸葛 / 贝壳网页）

贝壳官方 API 是本项目唯一主数据源。此外可选接入开源工具 **house-cli**，让 `--refresh` 自动补充贝壳之外的平台真实房源（安居客、58同城、房天下、诸葛找房等），并合进同一份快照和报告。它是**补充**而非替代：不装、未登录、平台失败，都只跳过并记日志，不影响贝壳主流程、不伪造数据。

**1. 安装 house-cli（需 uv + Python 3.12+，一次性）**

```bash
git clone https://github.com/lingongzhe/house-cli.git
cd house-cli
uv sync          # 自动创建 .venv 并装依赖
```

> 集成代码 `runner/housecli.py` 会自动在 `../../house-cli/.venv/Scripts/house.exe`
> （或环境变量 `HOUSE_CLI` / 系统 `PATH` 里的 `house`）找到可执行文件，无需额外配置。

**2. 解锁登录态（关键一步，否则取不到数据）**
house-cli 的贝壳/安居客/58/诸葛等 adapter 需要**浏览器 Cookie**（有效期约 7 天）。在
本机 **Chrome 或 Edge** 登录一次所用平台即可，house-cli 会自动抓取 Cookie：
安居客 `anjuke.com` · 58同城 `58.com` · 房天下 `fang.com` · 诸葛找房 `zhuge.com`。
（链家/贝壳 `ke.com` 可不必登录——本项目贝壳走官方 API，质量更高。）
不想用浏览器自动抓取时，也可手动把 Cookie 写入 `~/.config/house-cli/cookies.json`。

**3. 更新数据并出报告**（联网，同主流程）

```bash
# 用贝壳官方 API + house-cli 多平台一起刷新；然后离线出报告
python runner\main.py --refresh
python runner\main.py
```

**4. 想调整启用哪些平台**
改 `runner/housecli.py` 顶部的 `PLATFORM`，例如只留安居客+房天下：`PLATFORM = "anjuke,fang"`。

> **贝壳官方 API 停机时的自足模式**：`--refresh` 里贝壳取不到数据时，house-cli 会自己抓
> 租房挂牌、聚合出「区」粒度的真实租金率来关联在售房源，独立产出真实报告（粒度比贝壳
> 板块粗）。贝壳恢复后自动回到"贝壳优先"。

## 新增行情源：creprice.cn（中国房价行情）区县市场行情

`main.py --refresh` 联网时，还会顺带抓取 **creprice.cn（全国房价行情）** 的公开区县行情，
作用与 house-cli 一样是**补充/校验，不替代贝壳主流程**：

- **做什么**：抓取 沈阳/大连 各区县的**真实房价（元/㎡）与挂牌租金（元/月/㎡）**；

- **展示**：报告里多出一块「区县市场行情」面板（区 → 房价/租金/售租比）；

- **兜底**：把 creprice 的区县租金率作为「兜底」并入板块租金地图（仅当该区/板块尚未有
  更精确数据时），让更多房源能关联到真实租金，提升自足场景覆盖率；

- **抓不到影响主流程**：只记日志、不伪造，贝壳/多平台照常工作。

这是此前你给的 `https://www.creprice.cn/` 里可用的一类入口——`/fjdata-216` 那个具体编号
页面实际返回 404，真正可用的是「区县房价/租金」列表页（本模块已自动走到），无需手动改链接。

数据只在联网刷新时更新，快照存 `runner/output/creprice_data.json`，离线重建报告仍可显示上次行情。

## 新增行情源：gotohui.com（聚汇数据）城市市场台账

你可能已经注意到——你之前给的 `creprice.cn//fjdata-216` 里那个 `/fjdata-216` 其实**不属于
creprice**（那儿是 404），而是本平台 **聚汇数据（gotohui.com）** 的「大连」数据页
（`/fjdata-215`=沈阳）。`main.py --refresh` 联网时也会抓它在城市页的行情：

- **抓什么**：沈阳/大连的**二手房均价、新房均价、月均房租（元/月/㎡）**（城市口径）；

- **展示**：报告里新增「城市市场台账」面板，并把聚汇的月均房租与本报告里 creprice
  的区县均值做**独立交叉校对**（显示"较区县均值 高/低 x%"），两源相互印证行情可信度；

- **抓不到**：只记日志、不伪造，不影响主流程；快照存 `runner/output/gotohui_data.json`。

## 指标口径（分析依据）

| 指标     | 口径                                                               |
| ------ | ---------------------------------------------------------------- |
| 租售比(年) | `参考月租×12 ÷ 总价`。参考月租优先取该套所在**小区官方租房均价×面积**，缺失时取**同板块挂牌租金率中位数×面积** |
| 回本年限   | `总价 ÷ 年租金`                                                       |
| 净回报率   | 与租售比同口径（真实空置/税费未知，不虚构扣减，需实地核验）                                   |
| 出租易度   | 真实维度加权：楼龄 + 板块租金率反推需求强度（缺项不给分、权重重归一化）                            |
| 覆盖城市   | 沈阳、大连 · 老破小总价 ≤30 万（`config.py` 可调）                              |

## 文档

- 评分方法详述（公式 + 示例演算）：`runner/scoring-basis.html`

- 程序说明：`runner/README.md`

## 免责声明

仅作个人投资研究参考，不构成投资建议。租售比/净回报为挂牌行情口径估算，实地购房前请自行核实。
