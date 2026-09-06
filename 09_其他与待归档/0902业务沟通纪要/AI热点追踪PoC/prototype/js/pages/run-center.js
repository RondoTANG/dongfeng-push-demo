(function () {
  'use strict';

  var state = { runs: [], total: 0, page: 1, pageSize: 20, events: [], automation: null, cooldown: {}, loading: true, error: null };

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
      metric('双路任务覆盖', String(coverage.executed_job_count || coverage.executed || 0) + ' / ' + String(coverage.planned_job_count || coverage.planned || 0), latest.mode === 'full' ? String(Math.ceil((coverage.planned_job_count || 0) / 2)) + '条查询 × 2个搜索工具' : '快速双路验证') +
      metric('有效线索', String(sourceSummary.valid || 0), '自动无效 ' + String(sourceSummary.invalid || 0) + ' 条') +
      metric('待处理事件', String(state.events.filter(function (item) { return item.event_status === 'pending_review'; }).length), '搜索事件热点均不可判定') +
      '</div>';
    var columns = [
      { label: '运行批次', width: '190px', render: function (row) { return '<div class="cell-title mono">' + AppCommon.escapeHtml(row.run_id) + '</div><div class="cell-sub">' + AppCommon.escapeHtml(row.trigger_type) + ' · ' + AppCommon.escapeHtml(row.mode) + '</div>'; } },
      { label: '开始时间', width: '160px', render: function (row) { return AppCommon.formatTime(row.started_at); } },
      { label: '任务覆盖', width: '125px', render: function (row) { var item = row.query_coverage || {}; return '<strong>' + (item.executed_job_count || item.executed || 0) + '</strong> / ' + (item.planned_job_count || item.planned || 0); } },
      { label: '来源处理', width: '160px', render: function (row) { var item = row.step_summary && row.step_summary.source_processing || {}; return '<span class="text-positive">有效 ' + (item.valid || 0) + '</span><span class="cell-separator">／</span><span class="text-muted">无效 ' + (item.invalid || 0) + '</span>'; } },
      { label: '运行状态', width: '120px', render: function (row) { return AppCommon.statusTag(row.status); } },
      { label: '操作', width: '130px', render: function (row) { return '<button class="btn btn-text btn-sm" data-run-detail="' + row.run_id + '">查看详情</button>'; } }
    ];
    var automation = state.automation || {};
    var automationConfig = automation.config || {};
    var lastManual = automation.last_manual_run || {}, lastScheduled = automation.last_scheduled_run || {};
    var enabledQueries = automation.enabled_query_count || 0;
    var automationPanel = '<section class="automation-control card" data-anno="local-automation"><div class="automation-control__summary"><div><span>自动采集</span><strong class="' + (automationConfig.enabled ? 'text-positive' : 'text-muted') + '">' + (automationConfig.enabled ? '运行中' : '已停止') + '</strong></div><div><span>采集周期</span><strong>每 ' + (automationConfig.interval_hours || 3) + ' 小时</strong></div><div><span>下次执行</span><strong>' + (automationConfig.next_run_at ? AppCommon.formatTime(automationConfig.next_run_at) : '未安排') + '</strong></div><div><span>最近自动批次</span><strong>' + AppCommon.escapeHtml(lastScheduled.run_id || '暂无') + '</strong></div></div><div class="automation-control__actions"><label>周期（小时）<input class="form-control" type="number" min="1" max="168" value="' + (automationConfig.interval_hours || 3) + '" data-auto-interval></label><button class="btn ' + (automationConfig.enabled ? 'btn-danger' : 'btn-primary') + '" data-toggle-automation="' + (automationConfig.enabled ? 'false' : 'true') + '">' + (automationConfig.enabled ? '停止自动采集' : '开启自动采集') + '</button></div><p>开启后首次执行安排在一个完整周期后；每次执行当前启用的 ' + enabledQueries + ' 条查询，并分别调用豆包和 Codex。修改周期会重新计算下次执行时间；定时与手工完整运行共用3小时冷却，周期短于3小时时会顺延；访客浏览不会触发搜索。</p></section>';
    return metrics + automationPanel + '<section class="card table-card" data-anno="run-center-batches"><div class="card-header"><div><h2>运行批次</h2><span>实际执行记录，不以配置条数代替</span></div><button class="btn btn-sm" data-refresh-runs>刷新</button></div>' +
      DataTable.render(columns, state.runs, { emptyTitle: '还没有运行批次', emptyText: '可发起一次双路快速验证或完整搜索' }) + DataTable.pagination(state.page, state.pageSize, state.total, 'data-run-page') + '</section>';
  }

  function render() {
    var actions = '<button class="btn" data-run-mode="full">完整双路运行</button>' +
      '<button class="btn btn-primary" data-run-mode="quick">快速双路验证（2项）</button>';
    return '<section class="page">' + Layout.pageHead('运行中心', '每个批次记录实际查询、来源处理、失败与配置快照', actions) +
      '<div class="boundary-banner"><strong>公开信息线索 PoC</strong><span>豆包与 Codex 用于发现和补证；没有平台原生指标与连续快照时，不输出真实热点结论。</span></div>' +
      '<div id="run-center-content">' + renderContent() + '</div></section>';
  }

  async function load() {
    state.loading = true; state.error = null; update();
    try {
      var results = await Promise.all([
        AppCommon.api('/api/runs?page=' + state.page + '&page_size=' + state.pageSize),
        AppCommon.api('/api/events?page=1&page_size=100'), AppCommon.api('/api/automation/status'),
        AppCommon.api('/api/runs/cooldown/full'), AppCommon.api('/api/runs/cooldown/quick')
      ]);
      state.runs = results[0].items; state.total = results[0].total || 0;
      state.events = results[1].items; state.automation = results[2];
      state.cooldown = { full: results[3], quick: results[4] };
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  function update() {
    var root = document.getElementById('run-center-content');
    if (root) root.innerHTML = renderContent();
  }

  async function executeRun(mode, button, drawer) {
    var original = button.textContent;
    button.disabled = true; button.textContent = '已提交，正在执行';
    try {
      await AppCommon.api('/api/runs', { method: 'POST', body: JSON.stringify({ mode: mode, trigger_type: 'manual', idempotency_key: 'ui-' + mode + '-' + Date.now() }) });
      if (drawer) drawer.close();
      var count = state.automation.enabled_query_count || 0;
      AppCommon.showToast(mode === 'full' ? '完整双路运行已开始：' + count + '条查询 × 2个工具' : '快速双路验证已开始：豆包1项＋Codex 1项', 'success');
      window.setTimeout(load, 1200);
    } catch (error) { AppCommon.showToast(error.message, 'error'); }
    window.setTimeout(function () { button.disabled = false; button.textContent = original; }, 1600);
  }

  function startRun(mode, button) {
    var cooldown = state.cooldown[mode] || {};
    if (cooldown.allowed === false) {
      return AppCommon.showToast('仍在冷却期，剩余约 ' + Math.ceil((cooldown.remaining_seconds || 0) / 60) + ' 分钟', 'error');
    }
    var full = mode === 'full';
    var queryCount = state.automation.enabled_query_count || 0;
    var drawer = UI.openDrawer({
      title: full ? '确认完整双路运行' : '确认快速双路验证',
      body: '<div class="review-summary"><strong>' + (full ? queryCount + '条启用查询 × 豆包、Codex = ' + (queryCount * 2) + '项' : '1条查询 × 豆包、Codex = 2项') + '</strong><p>豆包为计费搜索；Codex使用服务运行环境中的登录态执行公开网页搜索。本次结果仅作为信息线索，不输出真实热点结论。</p></div><div class="detail-grid"><div><span>豆包预计调用</span><strong>' + (full ? queryCount + '次' : '1次') + '</strong></div><div><span>Codex查询任务</span><strong>' + (full ? queryCount + '项' : '1项') + '</strong></div><div><span>内容时间范围</span><strong>主要24小时，最迟72小时</strong></div><div><span>再次运行限制</span><strong>' + (full ? '3小时' : '10分钟') + '</strong></div></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-confirm-run>确认并开始</button>'
    });
    drawer.element.querySelector('[data-confirm-run]').onclick = function (event) { executeRun(mode, event.currentTarget, drawer); };
  }

  async function showRun(runId) {
    try {
      var run = await AppCommon.api('/api/runs/' + runId);
      var columns = [
        { label: '查询', render: function (row) { return '<div class="cell-title">' + AppCommon.escapeHtml(row.query_text) + '</div><div class="cell-sub mono">' + AppCommon.escapeHtml(row.query_id) + ' · ' + AppCommon.escapeHtml(AppCommon.providerName(row.provider_id)) + '</div>'; } },
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
      var detailButton = event.target.closest('[data-run-detail]');
      if (detailButton) return showRun(detailButton.dataset.runDetail);
      if (event.target.closest('[data-refresh-runs]') || event.target.closest('[data-retry-action]')) return load();
      var automationButton = event.target.closest('[data-toggle-automation]');
      if (automationButton) {
        var interval = Number(document.querySelector('[data-auto-interval]').value);
        if (!Number.isInteger(interval) || interval < 1 || interval > 168) return AppCommon.showToast('采集周期需为1—168小时整数', 'error');
        automationButton.disabled = true;
        try { var changed = await AppCommon.api('/api/automation/config', { method: 'PATCH', body: JSON.stringify({ enabled: automationButton.dataset.toggleAutomation === 'true', interval_hours: interval }) }); AppCommon.showToast(changed.message, 'success'); await load(); }
        catch (error) { AppCommon.showToast(error.message, 'error'); automationButton.disabled = false; }
        return;
      }
      var pageButton = event.target.closest('[data-run-page]');
      if (pageButton) { state.page += pageButton.dataset.runPage === 'next' ? 1 : -1; return load(); }
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
