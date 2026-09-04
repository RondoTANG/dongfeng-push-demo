(function () {
  'use strict';

  var state = { tab: 'invalid', invalid: [], audit: [], loading: true, error: null, keyword: '', kind: '', page: 1, pageSize: 20, invalidTotal: 0, auditTotal: 0 };
  var ruleNames = {
    INV001: '无有效链接', INV002: '同名误匹配', INV003: '招投标／行政信息', INV004: '纯促销引流',
    INV005: '旧闻重新索引', INV006: '无实际事件', INV007: '行业事件无品牌关系'
  };
  var actionNames = { create: '创建', update: '修改', review: '审核', claim: '领取', complete: '完成', fail: '失败', merge: '合并', split: '拆分' };
  var objectNames = { task_draft: '作业草案', event: '统一事件', codex_work_item: 'Codex工作项', collection_run: '运行批次', source_item: '来源内容', configuration: '业务配置' };

  function filtered(items, fields) {
    var keyword = state.keyword.toLowerCase();
    return items.filter(function (item) {
      if (state.kind && fields.kind(item) !== state.kind) return false;
      if (!keyword) return true;
      return fields.text(item).toLowerCase().indexOf(keyword) >= 0;
    });
  }

  function renderInvalid() {
    var items = filtered(state.invalid, { kind: function (x) { return x.invalid_rule_id; }, text: function (x) { return [x.invalid_id,x.run_id,x.invalid_reason,x.source_id_or_raw_result_id].join(' '); } });
    var columns = [
      { label: '无效规则', width: '160px', render: function (row) { return '<div class="cell-title">' + (ruleNames[row.invalid_rule_id] || row.invalid_rule_id) + '</div><div class="cell-sub mono">' + row.invalid_rule_id + '</div>'; } },
      { label: '对象', width: '190px', render: function (row) { return '<span class="mono">' + AppCommon.escapeHtml(row.source_id_or_raw_result_id) + '</span>'; } },
      { label: '过滤原因', render: function (row) { return AppCommon.escapeHtml(row.invalid_reason); } },
      { label: '运行批次', width: '170px', render: function (row) { return '<span class="mono">' + row.run_id + '</span>'; } },
      { label: '处理时间', width: '160px', render: function (row) { return AppCommon.formatTime(row.discarded_at); } }
    ];
    return '<div class="audit-explain"><strong>自动无效不等于业务驳回</strong><span>这些记录已命中确定性噪声规则，不进入运营主工作台；保留日志用于抽检误杀。</span></div>' + DataTable.render(columns, items, { emptyTitle: '没有匹配的无效记录' }) + DataTable.pagination(state.page, state.pageSize, state.invalidTotal, 'data-audit-page');
  }

  function renderAudit() {
    var items = filtered(state.audit, { kind: function (x) { return x.object_type; }, text: function (x) { return [x.audit_id,x.actor_id,x.action,x.object_type,x.object_id].join(' '); } });
    var columns = [
      { label: '动作', width: '130px', render: function (row) { return '<div class="cell-title">' + (actionNames[row.action] || row.action) + '</div><div class="cell-sub mono">' + row.action + '</div>'; } },
      { label: '对象', width: '210px', render: function (row) { return '<div class="cell-title">' + (objectNames[row.object_type] || row.object_type) + '</div><div class="cell-sub mono">' + row.object_id + '</div>'; } },
      { label: '操作人', width: '170px', render: function (row) { return AppCommon.escapeHtml(row.actor_id) + '<div class="cell-sub">' + AppCommon.escapeHtml(row.actor_type) + '</div>'; } },
      { label: '时间', width: '170px', render: function (row) { return AppCommon.formatTime(row.created_at); } },
      { label: '变更', render: function (row) { var before = row.before == null ? '无前置值' : '有前置快照'; var after = row.after == null ? '无后置值' : '有后置快照'; return '<button class="btn btn-text btn-sm" data-audit-detail="' + row.audit_id + '">' + before + ' → ' + after + '</button>'; } }
    ];
    return '<div class="audit-explain is-blue"><strong>业务操作可追溯</strong><span>搜索运行、定向补证、事件审核和草案生成／修改都保留对象、操作人、时间和前后快照。</span></div>' + DataTable.render(columns, items, { emptyTitle: '没有匹配的审计记录' }) + DataTable.pagination(state.page, state.pageSize, state.auditTotal, 'data-audit-page');
  }

  function kindOptions() {
    var values = state.tab === 'invalid' ? Object.keys(ruleNames).map(function (key) { return [key, ruleNames[key]]; }) : Object.keys(objectNames).map(function (key) { return [key, objectNames[key]]; });
    return '<option value="">全部类型</option>' + values.map(function (item) { return '<option value="' + item[0] + '"' + (state.kind === item[0] ? ' selected' : '') + '>' + item[1] + '</option>'; }).join('');
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在读取无效与审计记录</div>';
    if (state.error) return UI.errorState(state.error, true);
    return '<div class="audit-tabs"><button class="config-tab' + (state.tab === 'invalid' ? ' is-active' : '') + '" data-audit-tab="invalid">自动无效 <span>' + state.invalidTotal + '</span></button><button class="config-tab' + (state.tab === 'audit' ? ' is-active' : '') + '" data-audit-tab="audit">操作审计 <span>' + state.auditTotal + '</span></button></div><div class="card audit-card"><div class="filter-bar"><div class="filter-field"><label>关键字</label><input class="form-control" data-audit-keyword value="' + AppCommon.escapeHtml(state.keyword) + '" placeholder="搜索对象编号、原因或操作人"></div><div class="filter-field"><label>记录类型</label><select class="form-control" data-audit-kind>' + kindOptions() + '</select></div><div class="filter-actions"><button class="btn" data-audit-reset>重置</button><button class="btn btn-primary" data-audit-query>查询</button></div></div><div class="audit-result">' + (state.tab === 'invalid' ? renderInvalid() : renderAudit()) + '</div></div>';
  }

  function render() { return '<section class="page" data-anno="invalid-and-audit-records">' + Layout.pageHead('无效与审计记录', '把技术噪声与业务决策分开，并保留完整操作痕迹', '<button class="btn" data-audit-refresh>刷新</button>') + '<div id="audit-content">' + renderContent() + '</div></section>'; }
  function update() { var root = document.getElementById('audit-content'); if (root) root.innerHTML = renderContent(); }
  async function load() {
    state.loading = true; state.error = null; update();
    try {
      var invalidParams = new URLSearchParams({ page: state.page, page_size: state.pageSize });
      var auditParams = new URLSearchParams({ page: state.page, page_size: state.pageSize });
      if (state.keyword) { invalidParams.set('keyword', state.keyword); auditParams.set('keyword', state.keyword); }
      if (state.kind) { if (state.tab === 'invalid') invalidParams.set('rule_id', state.kind); else auditParams.set('object_type', state.kind); }
      var result = await Promise.all([AppCommon.api('/api/invalid-records?' + invalidParams.toString()), AppCommon.api('/api/audit?' + auditParams.toString())]);
      state.invalid = result[0].items; state.invalidTotal = result[0].total || 0; state.audit = result[1].items; state.auditTotal = result[1].total || 0;
    }
    catch (error) { state.error = error.message; }
    state.loading = false; update();
  }
  function openAudit(id) {
    var item = state.audit.find(function (row) { return row.audit_id === id; }); if (!item) return;
    var json = function (value) { return AppCommon.escapeHtml(JSON.stringify(value, null, 2) || '无'); };
    UI.openDrawer({ title: '审计详情 · ' + id, body: '<div class="detail-grid"><div><span>对象</span><strong>' + AppCommon.escapeHtml(item.object_type + ' / ' + item.object_id) + '</strong></div><div><span>操作人</span><strong>' + AppCommon.escapeHtml(item.actor_id) + '</strong></div></div><h3 class="section-title">变更前</h3><pre class="json-view">' + json(item.before) + '</pre><h3 class="section-title">变更后</h3><pre class="json-view">' + json(item.after) + '</pre>', footer: '<button class="btn btn-primary" data-drawer-close>关闭</button>' });
  }
  function bind() {
    var page = document.getElementById('app');
    page.onclick = function (event) {
      var tab = event.target.closest('[data-audit-tab]'); if (tab) { state.tab = tab.dataset.auditTab; state.kind = ''; state.page = 1; return load(); }
      if (event.target.closest('[data-audit-refresh]') || event.target.closest('[data-retry-action]')) return load();
      if (event.target.closest('[data-audit-query]')) { state.keyword = page.querySelector('[data-audit-keyword]').value.trim(); state.kind = page.querySelector('[data-audit-kind]').value; state.page = 1; return load(); }
      if (event.target.closest('[data-audit-reset]')) { state.keyword = ''; state.kind = ''; state.page = 1; return load(); }
      var detail = event.target.closest('[data-audit-detail]'); if (detail) return openAudit(detail.dataset.auditDetail);
      var pageButton = event.target.closest('[data-audit-page]'); if (pageButton) { state.page += pageButton.dataset.auditPage === 'next' ? 1 : -1; return load(); }
    };
  }
  window.Pages.audit = { render: render, init: function () { bind(); load(); } };
})();
