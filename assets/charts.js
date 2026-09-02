(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  var axisBase = {
    axisLine: { lineStyle: { color: rule } },
    axisTick: { show: false },
    axisLabel: { color: muted, fontSize: 12 }
  };

  function tooltip() { return { trigger: 'axis', appendToBody: true, backgroundColor: 'rgba(27,35,51,.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 } }; }

  // --- Chart 1: 两城板块单价对比 ---
  var el1 = document.getElementById('chart-board-price');
  if (el1) {
    var c1 = echarts.init(el1, null, { renderer: 'svg' });
    c1.setOption({
      tooltip: tooltip(),
      animation: false,
      grid: { left: 16, right: 16, top: 40, bottom: 10, containLabel: true },
      legend: { top: 0, data: ['沈阳', '大连'], textStyle: { color: ink, fontSize: 13 } },
      xAxis: Object.assign({ type: 'category' }, axisBase, {
        data: ['皇姑', '大东', '沈河', '和平', '铁西', '甘井子泡崖', '旅顺', '开发区', '西岗', '沙河口']
      }),
      yAxis: Object.assign({ type: 'value', name: '元/㎡', nameTextStyle: { color: muted } }, axisBase),
      series: [
        { name: '沈阳', type: 'bar', barMaxWidth: 30, color: accent,
          data: [7900, 7500, 7900, 10000, 7800, null, null, null, null, null],
          label: { show: true, position: 'top', color: ink, fontSize: 11, formatter: function(p){ return p.value == null ? '' : p.value; } } },
        { name: '大连', type: 'bar', barMaxWidth: 30, color: accent2,
          data: [null, null, null, null, null, 6200, 6345, 8610, 11484, 13902],
          label: { show: true, position: 'top', color: ink, fontSize: 11, formatter: function(p){ return p.value == null ? '' : p.value; } } }
      ]
    });
    window.addEventListener('resize', function(){ c1.resize(); });
  }

  // --- Chart 2: 月租区间 (低-高) ---
  var el2 = document.getElementById('chart-rent-low');
  if (el2) {
    var c2 = echarts.init(el2, null, { renderer: 'svg' });
    c2.setOption({
      tooltip: tooltip(),
      animation: false,
      grid: { left: 16, right: 16, top: 10, bottom: 10, containLabel: true },
      xAxis: Object.assign({ type: 'category' }, axisBase, {
        data: ['沈阳 · 皇姑/大东', '沈阳 · 沈河/和平', '沈阳 · 近郊老小', '大连 · 甘井子', '大连 · 金州', '大连 · 西岗/沙河口老城']
      }),
      yAxis: Object.assign({ type: 'value', name: '元/月', nameTextStyle: { color: muted } }, axisBase),
      series: [{
        type: 'bar', barMaxWidth: 44, name: '月租',
        itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: accent }, { offset: 1, color: accent2 }] }, borderRadius: [6,6,0,0] },
        data: [[950, 1550], [1000, 1550], [800, 1200], [1100, 1500], [1000, 1400], [900, 1500]],
        label: { show: false }
      }]
    });
    window.addEventListener('resize', function(){ c2.resize(); });
  }

  // --- Chart 3: 租金回报率 vs 无风险参考线 ---
  var el3 = document.getElementById('chart-yield');
  if (el3) {
    var c3 = echarts.init(el3, null, { renderer: 'svg' });
    c3.setOption({
      tooltip: tooltip(),
      animation: false,
      grid: { left: 16, right: 16, top: 40, bottom: 10, containLabel: true },
      legend: { top: 0, data: ['年租金回报率'], textStyle: { color: ink, fontSize: 13 } },
      xAxis: Object.assign({ type: 'category' }, axisBase, {
        data: ['沈阳·皇姑', '沈阳·大东', '沈阳·沈河', '沈阳·和平', '沈阳·铁西', '大连·泡崖', '大连·金州', '大连·旅顺', '大连·西岗', '大连·沙河口']
      }),
      yAxis: Object.assign({ type: 'value', name: '%', min: 0, nameTextStyle: { color: muted } }, axisBase),
      series: [{
        name: '年租金回报率', type: 'bar', barMaxWidth: 34, color: accent,
        data: [4.3, 4.5, 4.0, 3.6, 4.4, 4.6, 4.4, 3.4, 3.0, 2.9],
        label: { show: true, position: 'top', color: ink, fontSize: 11, formatter: '{c}%' },
        markLine: {
          symbol: 'none', label: { color: '#b06a18', fontSize: 11, formatter: '无风险参考 2.3–2.6%' },
          lineStyle: { color: '#e08a2e', type: 'dashed', width: 2 },
          data: [{ yAxis: 2.6 }]
        }
      }]
    });
    window.addEventListener('resize', function(){ c3.resize(); });
  }

  // --- Chart 4: 出租易度评分权重 ---
  var el4 = document.getElementById('chart-weight');
  if (el4) {
    var c4 = echarts.init(el4, null, { renderer: 'svg' });
    c4.setOption({
      tooltip: { trigger: 'item', appendToBody: true, backgroundColor: 'rgba(27,35,51,.92)', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 } },
      animation: false,
      grid: { left: 16, right: 40, top: 10, bottom: 10, containLabel: true },
      xAxis: Object.assign({ type: 'value', max: 30, name: '权重 %' }, axisBase),
      yAxis: Object.assign({ type: 'category' }, axisBase, {
        data: ['季节系数', '学区', '板块供需', '房龄与硬件', '交通便捷', '需求与配套']
      }),
      series: [{
        type: 'bar', barMaxWidth: 30,
        data: [
          { value: 5, itemStyle: { color: muted } },
          { value: 10, itemStyle: { color: 'rgba(26,102,255,.55)' } },
          { value: 15, itemStyle: { color: accent2 } },
          { value: 20, itemStyle: { color: accent } },
          { value: 25, itemStyle: { color: accent } },
          { value: 25, itemStyle: { color: accent } }
        ],
        label: { show: true, position: 'right', color: ink, fontSize: 11, formatter: '{c}%' }
      }]
    });
    window.addEventListener('resize', function(){ c4.resize(); });
  }
})();