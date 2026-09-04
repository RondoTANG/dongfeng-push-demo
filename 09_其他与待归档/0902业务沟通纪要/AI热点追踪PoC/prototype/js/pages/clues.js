(function () {
  'use strict';

  var state = { items: [], filtered: [], events: [], loading: true, error: null };
  var platformNames = {
    brand_official_website: '品牌官方网站', government_or_central_media: '政府或央媒', industry_media: '行业媒体',
    weibo: '微博', douyin: '抖音', news_aggregator: '新闻聚合平台', wechat_official_account: '微信公众号',
    wechat_channels: '微信视频号', other_website: '其他网站', unknown: '待识别来源'
  };

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在读取来源数据</div>';
    if (state.error) return UI.errorState(state.error, true);
    var options = [{ value: '', label: '全部平台' }].concat(Object.keys(platformNames).map(function (key) { return { value: key, label: platformNames[key] }; }));
    var filters = Filters.render([
      { key: 'keyword', label: '关键词', placeholder: '标题或摘要' },
      { key: 'platform', label: '来源平台', type: 'select', options: options },
      { key: 'status', label: '处理状态', type: 'select', options: [
        { value: '', label: '全部状态' }, { value: 'valid', label: '有效线索' }, { value: 'pending_review', label: '待判定' }, { value: 'fetch_failed', label: '获取失败' }
      ] }
    ], '<button class="btn" data-reset-filters>重置</button><button class="btn btn-primary" data-apply-filters>查询</button>');
    var columns = [
      { label: '公开信息线索', render: function (row) { return '<div class="cell-title line-clamp-2">' + AppCommon.escapeHtml(row.title) + '</div><div class="cell-sub mono">' + AppCommon.escapeHtml(row.source_id) + '</div>'; } },
      { label: '来源', width: '170px', render: function (row) { return '<strong>' + AppCommon.escapeHtml(platformNames[row.source_platform] || row.source_platform) + '</strong><div class="cell-sub">' + AppCommon.escapeHtml(row.source_site_name || row.domain || '未识别站点') + '</div>'; } },
      { label: '发布时间', width: '150px', render: function (row) { return AppCommon.formatTime(row.published_at, '时间不明') + '<div class="cell-sub">置信度 ' + AppCommon.escapeHtml(row.published_time_confidence) + '</div>'; } },
      { label: '状态', width: '110px', render: function (row) { return AppCommon.statusTag(row.source_status); } },
      { label: '关联事件', width: '150px', render: function (row) { return row.event_id ? '<button class="btn btn-text btn-sm" data-open-event="' + row.event_id + '">' + AppCommon.escapeHtml(row.event_id) + '</button>' : '<span class="text-muted">待聚合／列表页多事件</span>'; } },
      { label: '操作', width: '105px', render: function (row) { return '<button class="btn btn-text btn-sm" data-source-detail="' + row.source_id + '">详情</button>'; } }
    ];
    return '<section class="card" data-anno="clues-workbench"><div class="card-body">' + filters +
      '<div class="table-summary"><span>主工作台仅展示有效与待判定线索</span><strong>' + state.filtered.length + ' 条</strong></div>' +
      DataTable.render(columns, state.filtered, { emptyTitle: '没有符合条件的线索', emptyText: '自动无效结果可在“无效与审计记录”查看' }) + '</div></section>';
  }

  function render() {
    return '<section class="page">' + Layout.pageHead('信息线索工作台', '公开搜索结果统一处理后进入主工作台；自动无效结果单独留痕') +
      '<div class="boundary-banner"><strong>线索不等于热点</strong><span>这里展示“搜到并可追溯的公开信息”，不以搜索排名、转载数或 AI 分数判断真实热度。</span></div>' +
      '<div id="clues-content">' + renderContent() + '</div></section>';
  }

  async function load() {
    state.loading = true; state.error = null; update();
    try {
      var results = await Promise.all([AppCommon.api('/api/sources?limit=500'), AppCommon.api('/api/events?limit=500')]);
      state.items = results[0].items.filter(function (item) { return item.source_status !== 'invalid'; });
      state.filtered = state.items.slice(); state.events = results[1].items;
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  function update() { var root = document.getElementById('clues-content'); if (root) root.innerHTML = renderContent(); }

  function applyFilters() {
    var root = document.getElementById('clues-content');
    var values = Filters.values(root);
    var keyword = (values.keyword || '').trim().toLowerCase();
    state.filtered = state.items.filter(function (item) {
      return (!keyword || ((item.title || '') + ' ' + (item.snippet || '')).toLowerCase().indexOf(keyword) >= 0) &&
        (!values.platform || item.source_platform === values.platform) && (!values.status || item.source_status === values.status);
    });
    update();
  }

  function showSource(sourceId) {
    var item = state.items.find(function (source) { return source.source_id === sourceId; });
    if (!item) return;
    UI.openDrawer({
      title: '线索详情',
      body: '<div class="detail-grid"><div><span>线索编号</span><strong class="mono">' + item.source_id + '</strong></div><div><span>来源平台</span><strong>' + AppCommon.escapeHtml(platformNames[item.source_platform] || item.source_platform) + '</strong></div><div><span>站点／账号</span><strong>' + AppCommon.escapeHtml(item.source_site_name || item.source_account || '未识别') + '</strong></div><div><span>发布时间</span><strong>' + AppCommon.formatTime(item.published_at, '时间不明') + '</strong></div></div><h3 class="section-title">' + AppCommon.escapeHtml(item.title) + '</h3><div class="evidence-text">' + AppCommon.escapeHtml(item.snippet || '未返回正文摘要').replace(/\n/g, '<br>') + '</div><div class="source-url"><span>规范链接</span><a href="' + AppCommon.escapeHtml(item.original_url) + '" target="_blank" rel="noopener">打开原始来源</a></div>',
      footer: '<button class="btn" data-drawer-close>关闭</button>' + (item.event_id ? '<button class="btn btn-primary" data-open-event="' + item.event_id + '">查看关联事件</button>' : '')
    });
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = function (event) {
      if (event.target.closest('[data-apply-filters]')) return applyFilters();
      if (event.target.closest('[data-reset-filters]')) { state.filtered = state.items.slice(); return update(); }
      if (event.target.closest('[data-retry-action]')) return load();
      var sourceButton = event.target.closest('[data-source-detail]');
      if (sourceButton) return showSource(sourceButton.dataset.sourceDetail);
      var eventButton = event.target.closest('[data-open-event]');
      if (eventButton) { window.AppContext = { eventId: eventButton.dataset.openEvent }; App.navigate('event-detail'); }
    };
  }

  window.Pages.clues = { render: render, init: function () { bind(); load(); } };
})();
