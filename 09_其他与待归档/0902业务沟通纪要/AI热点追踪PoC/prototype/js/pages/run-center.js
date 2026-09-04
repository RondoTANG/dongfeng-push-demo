(function () {
  'use strict';

  var state = { runs: [], sources: [], events: [], invalid: [], automation: null, loading: true, error: null };

  function metric(label, value, hint, tone) {
    return '<article class="metric-card ' + (tone || '') + '"><span>' + AppCommon.escapeHtml(label) + '</span><strong>' + AppCommon.escapeHtml(value) + '</strong><small>' + AppCommon.escapeHtml(hint || '') + '</small></article>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在读取真实运行数据</div>';
    if (state.error) return UI.errorState(state.error, true);
    var latest = state.runs[0] || {};
    var coverage = latest.query_coverage || {};
    var sourceSummary = latest.step_summary && latest.step_summary.source_processing || {};
    var metrics = '<div class="metrics-grid" data-anno="run-center-metrics">' +
      metric('最近运行', latest.status ? (AppCommon.statusMeta[latest.status] || [latest.status])[0] : '暂无运行', latest.run_id || '等待首次执行', latest.status === 'failed' ? 'tone-red' : '') +
      metric('实际查询覆盖', String(coverage.executed || 0) + ' / ' + String(coverage.planned || 0), latest.mode === 'full' ? '完整模式' : '快速或导入模式') +
      metric('有效线索', String(sourceSummary.valid || 0), '自动无效 ' + String(sourceSummary.invalid || 0) + ' 条') +
      metric('待处理事件', String(state.events.filter(function (item) { return ['needs_evidence','pending_review','manual_review'].indexOf(item.event_status) >= 0; }).length), '搜索事件热点均不可判定') +
      '</div>';
    var columns = [
      { label: '运行批次', width: '190px', render: function (row) { return '<div class="cell-title mono">' + AppCommon.escapeHtml(row.run_id) + '</div><div class="cell-sub">' + AppCommon.escapeHtml(row.trigger_type) + ' · ' + AppCommon.escapeHtml(row.mode) + '</div>'; } },
      { label: '开始时间', width: '160px', render: function (row) { return AppCommon.formatTime(row.started_at); } },
      { label: '查询覆盖', width: '125px', render: function (row) { var item = row.query_coverage || {}; return '<strong>' + (item.executed || 0) + '</strong> / ' + (item.planned || 0); } },
      { label: '来源处理', width: '160px', render: function (row) { var item = row.step_summary && row.step_summary.source_processing || {}; return '<span class="text-positive">有效 ' + (item.valid || 0) + '</span><span class="cell-separator">／</span><span class="text-muted">无效 ' + (item.invalid || 0) + '</span>'; } },
      { label: '运行状态', width: '120px', render: function (row) { return AppCommon.statusTag(row.status); } },
      { label: '操作', width: '130px', render: function (row) { return '<button class="btn btn-text btn-sm" data-run-detail="' + row.run_id + '">查看详情</button>'; } }
    ];
    var automation = state.automation || {};
    var automationConfig = automation.config || {};
    var lastScheduled = automation.last_scheduled_run || {};
    var automationPanel = '<section class="automation-strip" data-anno="local-automation"><div><span>本地自动化</span><strong>' + (automationConfig.enabled ? '已启用 · 每3小时' : '未启用') + '</strong></div><div><span>最近定时批次</span><strong>' + AppCommon.escapeHtml(lastScheduled.run_id || '暂无') + '</strong></div><div><span>Codex 待处理工作项</span><strong>' + String(automation.pending_work_item_count || 0) + ' 条</strong></div><div class="automation-strip__note"><strong>当前接法</strong><span>本地脚本＋HTTP／SQLite 契约，不依赖 MCP；MCP 仅是后续与业务系统联动的可选路径。</span></div></section>';
    return metrics + automationPanel + '<section class="card table-card" data-anno="run-center-batches"><div class="card-header"><div><h2>运行批次</h2><span>实际执行记录，不以配置条数代替</span></div><button class="btn btn-sm" data-refresh-runs>刷新</button></div>' +
      DataTable.render(columns, state.runs, { emptyTitle: '还没有运行批次', emptyText: '可先导入真实样本，或发起一次豆包快速运行' }) + '</section>';
  }

  function render() {
    var actions = '<button class="btn" data-import-sample>导入真实样本</button>' +
      '<button class="btn" data-run-mode="full">完整运行（17条）</button>' +
      '<button class="btn btn-primary" data-run-mode="quick">快速验证（1条）</button>';
    return '<section class="page">' + Layout.pageHead('运行中心', '每个批次记录实际查询、来源处理、失败与配置快照', actions) +
      '<div class="boundary-banner"><strong>公开信息线索 PoC</strong><span>豆包与 Codex 用于发现和补证；没有平台原生指标与连续快照时，不输出真实热点结论。</span></div>' +
      '<div id="run-center-content">' + renderContent() + '</div></section>';
  }

  async function load() {
    state.loading = true; state.error = null; update();
    try {
      var results = await Promise.all([
        AppCommon.api('/api/runs'), AppCommon.api('/api/sources?limit=500'),
        AppCommon.api('/api/events?limit=500'), AppCommon.api('/api/invalid-records?limit=500'),
        AppCommon.api('/api/automation/status')
      ]);
      state.runs = results[0].items; state.sources = results[1].items;
      state.events = results[2].items; state.invalid = results[3].items;
      state.automation = results[4];
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  function update() {
    var root = document.getElementById('run-center-content');
    if (root) root.innerHTML = renderContent();
  }

  async function startRun(mode, button) {
    var original = button.textContent;
    button.disabled = true; button.textContent = '已提交，正在执行';
    try {
      await AppCommon.api('/api/runs', { method: 'POST', body: JSON.stringify({ mode: mode, trigger_type: 'manual', idempotency_key: 'ui-' + mode + '-' + Date.now() }) });
      AppCommon.showToast(mode === 'full' ? '完整运行已开始，17 条查询将在后台依次执行' : '快速验证已开始', 'success');
      window.setTimeout(load, 1200);
    } catch (error) { AppCommon.showToast(error.message, 'error'); }
    window.setTimeout(function () { button.disabled = false; button.textContent = original; }, 1600);
  }

  async function importSample(button) {
    button.disabled = true;
    try {
      var run = await AppCommon.api('/api/runs/import-real-sample', { method: 'POST' });
      await AppCommon.api('/api/runs/' + run.run_id + '/aggregate', { method: 'POST' });
      AppCommon.showToast('真实豆包样本已导入并完成事件聚合', 'success');
      await load();
    } catch (error) { AppCommon.showToast(error.message, 'error'); }
    button.disabled = false;
  }

  async function showRun(runId) {
    try {
      var run = await AppCommon.api('/api/runs/' + runId);
      var columns = [
        { label: '查询', render: function (row) { return '<div class="cell-title">' + AppCommon.escapeHtml(row.query_text) + '</div><div class="cell-sub mono">' + AppCommon.escapeHtml(row.query_id) + '</div>'; } },
        { label: '结果数', width: '90px', key: 'result_count' },
        { label: '状态', width: '110px', render: function (row) { return AppCommon.statusTag(row.status); } },
        { label: '失败原因', render: function (row) { return AppCommon.escapeHtml(row.error_message || '—'); } }
      ];
      UI.openDrawer({
        title: '运行详情 · ' + run.run_id,
        body: '<div class="detail-grid"><div><span>触发方式</span><strong>' + AppCommon.escapeHtml(run.trigger_type) + '</strong></div><div><span>开始时间</span><strong>' + AppCommon.formatTime(run.started_at) + '</strong></div><div><span>状态</span>' + AppCommon.statusTag(run.status) + '</div><div><span>配置快照</span><strong>' + Object.keys(run.config_versions || {}).length + ' 组</strong></div></div><h3 class="section-title">查询任务</h3>' + DataTable.render(columns, run.query_jobs || []),
        footer: '<button class="btn" data-drawer-close>关闭</button><button class="btn btn-primary" data-aggregate-run="' + run.run_id + '">生成／刷新事件</button>'
      });
    } catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = async function (event) {
      var runButton = event.target.closest('[data-run-mode]');
      if (runButton) return startRun(runButton.dataset.runMode, runButton);
      var importButton = event.target.closest('[data-import-sample]');
      if (importButton) return importSample(importButton);
      var detailButton = event.target.closest('[data-run-detail]');
      if (detailButton) return showRun(detailButton.dataset.runDetail);
      if (event.target.closest('[data-refresh-runs]') || event.target.closest('[data-retry-action]')) return load();
      var aggregateButton = event.target.closest('[data-aggregate-run]');
      if (aggregateButton) {
        try {
          var result = await AppCommon.api('/api/runs/' + aggregateButton.dataset.aggregateRun + '/aggregate', { method: 'POST' });
          AppCommon.showToast('事件处理完成：新增 ' + result.events_created + ' 个事件', 'success');
          document.querySelector('[data-drawer-close]').click(); await load();
        } catch (error) { AppCommon.showToast(error.message, 'error'); }
      }
    };
  }

  window.Pages['run-center'] = { render: render, init: function () { bind(); load(); } };
})();
