# 沈阳 · 大连 30万内老破小「收租」筛选智能体

纯 Python 标准库（零依赖）实现：多源数据（贝壳/链家、安居客、58 的接入框架 + 内置行情样本回退）→ 清洗 → 出租难易度评分 → 综合投资分 → 生成**傻瓜式可视化报告**。

**每日自动更新**：GitHub Actions 定时任务（`.github/workflows/daily.yml`）每天 08:00（北京时间）自动运行，刷新并提交 `runner/output/rental-report.html`——机制与你之前 rv-compare 一致。

## 快速使用
- 本地：双击 `runner\run.bat`，或 `python runner\main.py`（未装 Python 可先 `runner\README.md`）。
- GitHub：Actions 面板可手动 `Run workflow`，或等每日定时。生成结果见 `runner/output/rental-report.html`。

## 文档
- 方案蓝图：`old-town-rental-agent.html`
- 评分方法详述（公式 + 示例演算）：`runner/scoring-basis.html`
- 程序说明：`runner/README.md`

## 免责声明
仅作个人投资研究参考，不构成投资建议。租售比/净回报为行情口径估算，实地购房前请自行核实。