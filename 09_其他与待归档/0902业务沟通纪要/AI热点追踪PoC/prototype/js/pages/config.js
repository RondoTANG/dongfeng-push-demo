(function () {
  'use strict';

  var state = { data: null, loading: true, error: null, tab: 'brands' };
  var tabs = [
    ['brands', '品牌与实体'], ['queries', '查询目录'], ['sources', '来源识别'],
    ['processing', '处理规则'], ['drafts', '作业草案'], ['hotspot', '热点数据准入']
  ];
  var capabilityNames = {
    platform_content_id: '平台内容标识', native_engagement_metrics: '平台原生互动指标',
    metric_timeseries: '连续时间快照', author_or_unique_ugc_identity: '作者／独立UGC标识',
    platform_coverage_and_collected_at: '覆盖范围与采集时间', search_rank: '搜索排名',
    total_search_result_count: '搜索结果数', media_repost_count: '媒体转载数',
    provider_authority_level: '搜索提供方权重', ai_subjective_score: 'AI主观评分'
  };
  var platformNames = {
    weibo: '微博', douyin: '抖音', wechat_official_account: '微信公众号', wechat_channels: '微信视频号',
    public_web: '公开网页', public_pages_partial: '公开页面部分覆盖', known_url_metrics: '已知链接指标查询',
    not_guaranteed: '不保证覆盖', unknown: '待确认'
  };

  function boolTag(value, yes, no) {
    return value ? '<span class="status-tag status-green">' + (yes || '已启用') + '</span>' : '<span class="status-tag status-neutral">' + (no || '未启用') + '</span>';
  }

  function renderMetrics() {
    var s = state.data.summary;
    var items = [
      ['启用品牌', s.active_brand_count + ' 个', '9个品牌全量检索'],
      ['基础查询', (s.brand_query_count + s.topic_query_count) + ' 条', s.brand_query_count + '品牌＋' + s.topic_query_count + '行业主题'],
      ['来源规则', s.domain_rule_count + ' 条', s.platform_count + '类平台定义'],
      ['豆包搜索凭证', s.credential_configured ? '已配置' : '未配置', '仅显示状态，不读取密钥内容']
    ];
    return '<div class="metrics-grid config-metrics">' + items.map(function (item, index) {
      return '<article class="metric-card' + (index === 3 && !s.credential_configured ? ' tone-red' : '') + '"><span>' + item[0] + '</span><strong>' + item[1] + '</strong><small>' + item[2] + '</small></article>';
    }).join('') + '</div>';
  }

  function renderBrands() {
    var data = state.data.brands;
    var columns = [
      { label: '品牌', width: '180px', render: function (row) { return '<div class="cell-title">' + AppCommon.escapeHtml(row.canonical_name) + '</div><div class="cell-sub mono">' + row.brand_id + '</div>'; } },
      { label: '确定性别名', render: function (row) { return AppCommon.escapeHtml((row.exact_aliases || []).join('、') || '—'); } },
      { label: '弱别名／上下文', render: function (row) { return AppCommon.escapeHtml((row.weak_aliases || []).join('、') || '—') + '<div class="cell-sub">' + AppCommon.escapeHtml((row.weak_alias_context_terms || []).join('、')) + '</div>'; } },
      { label: '官方域名', render: function (row) { return '<span class="mono">' + AppCommon.escapeHtml((row.official_domains || []).join('、') || '待补充') + '</span>'; } },
      { label: '状态', width: '90px', render: function () { return '<span class="status-tag status-green">启用</span>'; } }
    ];
    return '<div class="rule-note"><strong>识别原则</strong><ul>' + data.rules.map(function (item) { return '<li>' + AppCommon.escapeHtml(item) + '</li>'; }).join('') + '</ul></div>' + DataTable.render(columns, data.items);
  }

  function renderQueries() {
    var execution = state.data.queries.execution;
    var columns = [
      { label: '编号', width: '80px', render: function (row) { return '<span class="mono">' + row.query_id + '</span>'; } },
      { label: '类型', width: '120px', key: 'group_name' },
      { label: '目标品牌', width: '140px', render: function (row) { return AppCommon.escapeHtml(row.brand_name || '行业线索'); } },
      { label: '实际查询词', key: 'query' },
      { label: '状态', width: '90px', render: function (row) { return boolTag(row.enabled); } }
    ];
    return '<div class="config-policy-strip"><div><span>每次完整运行</span><strong>' + (execution.full_coverage_each_run ? '全量执行17条' : '按当前配置执行') + '</strong></div><div><span>基础时间窗口</span><strong>' + execution.lookback_hours + '小时／延迟线索' + execution.late_signal_hours + '小时</strong></div><div><span>行业事件品牌验证</span><strong>全量9品牌，不轮换</strong></div></div><p class="section-caption">' + AppCommon.escapeHtml(execution.provider_failure_policy) + '</p>' + DataTable.render(columns, state.data.queries.items);
  }

  function renderSources() {
    var data = state.data.sources;
    var providers = '<div class="provider-grid">' + data.providers.map(function (item) {
      return '<article class="provider-card"><div class="provider-card__head"><div><strong>' + AppCommon.escapeHtml(item.display_name) + '</strong><span class="mono">' + AppCommon.escapeHtml(item.provider_id) + '</span></div>' + (item.can_judge_hotspot ? '<span class="status-tag status-green">可判热点</span>' : '<span class="status-tag status-neutral">不判热点</span>') + '</div><p>' + AppCommon.escapeHtml(item.role) + '</p><div class="capability-row"><span>' + (item.can_discover ? '可发现内容' : '仅已知链接') + '</span><span>原生指标：' + (item.has_native_metrics === true ? '支持' : item.has_native_metrics === false ? '不支持' : '按平台部分支持') + '</span></div></article>';
    }).join('') + '</div>';
    var columns = [
      { label: '域名', width: '190px', render: function (row) { return '<span class="mono">' + AppCommon.escapeHtml(row.domain) + '</span>'; } },
      { label: '站点名称', key: 'site_name' },
      { label: '识别平台', width: '170px', render: function (row) { return AppCommon.escapeHtml(row.platform); } },
      { label: '品牌关系', render: function (row) { return AppCommon.escapeHtml((row.related_brands || []).join('、') || '不由域名直接确认'); } }
    ];
    return providers + '<h3 class="section-title">已配置站点识别规则</h3>' + DataTable.render(columns, data.domains) + '<p class="section-caption">未命中域名规则的来源保留为“待识别来源”，不会因 AI 猜测自动升级为官方来源。</p>';
  }

  function renderProcessing() {
    var data = state.data.processing;
    var invalid = '<div class="rule-card-grid">' + data.invalid_rules.map(function (rule) {
      return '<article class="rule-card"><div><span class="mono">' + rule.rule_id + '</span><strong>' + AppCommon.escapeHtml(rule.name) + '</strong></div><p>' + AppCommon.escapeHtml(rule.condition) + '</p><footer>命中后自动记入无效日志，不交给运营审核</footer></article>';
    }).join('') + '</div>';
    var dedup = data.deduplication.map(function (item) { return '<div class="process-step"><span>' + AppCommon.escapeHtml(item.level) + '</span><p>' + AppCommon.escapeHtml(item.action) + '</p></div>'; }).join('');
    return '<h3 class="section-title">自动无效规则</h3>' + invalid + '<h3 class="section-title">去重与事件聚合</h3><div class="process-list">' + dedup + '<div class="process-step is-emphasis"><span>事件聚合</span><p>' + AppCommon.escapeHtml(data.event_clustering.aggregation_rule) + '</p></div><div class="process-step"><span>独立来源</span><p>' + AppCommon.escapeHtml(data.event_clustering.independent_source_rule) + '</p></div></div>';
  }

  function renderDrafts() {
    var data = state.data.drafts;
    var stage = state.data.stage;
    return '<div class="stage-card"><div><span>当前有效流程</span><strong>' + AppCommon.escapeHtml(stage.scope) + '</strong></div><div class="stage-stop"><span>明确暂不进入</span><strong>' + stage.deferred.join('、') + '</strong></div></div>' +
      '<div class="config-two-columns"><section><h3>双路草案生成与审批</h3><div class="plain-list"><p><span>原创增长</span>基于事件证据生成原创评论／内容方向</p><p><span>源内容加热</span>绑定事件中的具体文章或视频，生成点赞、正向评论等动作</p><p><span>草案状态</span>待审批、已通过、已驳回</p><p><span>审批要求</span>两类草案分别审批，均不自动下发</p><p><span>用户匹配</span>' + AppCommon.escapeHtml(data.member_label_source) + '</p></div></section><section><h3>建议目标平台</h3><div class="tag-row">' + data.target_platforms.map(function (item) { return '<span class="mini-tag">' + (platformNames[item] || item) + '</span>'; }).join('') + '</div><h3 class="section-title">源内容加热动作</h3><div class="tag-row">' + data.boost_actions.map(function (item) { return '<span class="mini-tag mono">' + item + '</span>'; }).join('') + '</div><h3 class="section-title">共用必备信息</h3><div class="tag-row">' + data.required_fields.map(function (item) { return '<span class="mini-tag mono">' + item + '</span>'; }).join('') + '</div></section></div><div class="rule-note"><strong>生成约束</strong><p>' + AppCommon.escapeHtml(data.generation_rule) + '</p><p>' + AppCommon.escapeHtml(data.boost_generation_rule) + '</p><p>' + AppCommon.escapeHtml(data.boost_target_rule) + '</p><p>' + AppCommon.escapeHtml(data.hotspot_disclaimer_rule) + '</p></div>';
  }

  function renderHotspot() {
    var data = state.data.hotspot;
    return '<div class="hotspot-boundary"><span>当前系统结论</span><h3>' + AppCommon.escapeHtml(data.current_output) + '</h3><p>' + AppCommon.escapeHtml(data.production_dependency) + '</p></div><div class="config-two-columns"><section><h3>允许判定真实热点前，必须同时具备</h3><ol class="readiness-list">' + data.required_capabilities.map(function (item) { return '<li><span>必须</span>' + (capabilityNames[item] || item) + '</li>'; }).join('') + '</ol></section><section><h3>禁止单独作为热度依据</h3><div class="prohibited-grid">' + data.prohibited_signals.map(function (item) { return '<span>' + (capabilityNames[item] || item) + '</span>'; }).join('') + '</div><div class="non-bypass">该规则没有“强制绕过”开关；数据条件不满足时必须说明具体缺失原因。</div></section></div>';
  }

  function renderPanel() {
    var renderer = { brands: renderBrands, queries: renderQueries, sources: renderSources, processing: renderProcessing, drafts: renderDrafts, hotspot: renderHotspot }[state.tab];
    return '<div class="config-tabs" role="tablist">' + tabs.map(function (item) { return '<button role="tab" class="config-tab' + (state.tab === item[0] ? ' is-active' : '') + '" data-config-tab="' + item[0] + '">' + item[1] + '</button>'; }).join('') + '</div><div class="config-panel">' + renderer() + '</div>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在读取本地配置</div>';
    if (state.error) return UI.errorState(state.error, true);
    return renderMetrics() + renderPanel();
  }

  function render() {
    var actions = '<button class="btn" data-config-versions>查看生效版本</button><button class="btn btn-primary" data-config-reload>重新读取配置</button>';
    return '<section class="page" data-anno="business-config-management">' + Layout.pageHead('配置管理', '以业务语言查看品牌、查询、来源、处理、草案和热点数据规则', actions) + '<div id="config-content">' + renderContent() + '</div></section>';
  }

  async function load() {
    state.loading = true; state.error = null; update();
    try { state.data = await AppCommon.api('/api/config/summary'); }
    catch (error) { state.error = error.message; }
    state.loading = false; update();
  }
  function update() { var root = document.getElementById('config-content'); if (root) root.innerHTML = renderContent(); }

  function openVersions() {
    var body = '<div class="version-list">' + state.data.meta.map(function (item) { return '<article><div><strong>' + AppCommon.escapeHtml(item.display_name) + '</strong><span>负责：' + AppCommon.escapeHtml(item.owner) + ' · 复核：' + AppCommon.escapeHtml(item.reviewer) + ' · 该版本用于 ' + (item.used_by_run_count || 0) + ' 个历史批次</span></div><code>' + AppCommon.escapeHtml(item.version) + '</code></article>'; }).join('') + '</div><div class="scope-notice">运行批次保存当时的版本摘要，之后修改 YAML 不会回写历史批次。</div>';
    UI.openDrawer({ title: '当前生效配置', body: body, footer: '<button class="btn btn-primary" data-drawer-close>知道了</button>' });
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = async function (event) {
      var tab = event.target.closest('[data-config-tab]');
      if (tab) { state.tab = tab.dataset.configTab; return update(); }
      if (event.target.closest('[data-config-versions]')) return openVersions();
      if (event.target.closest('[data-retry-action]')) return load();
      var reload = event.target.closest('[data-config-reload]');
      if (reload) {
        reload.disabled = true;
        try { var result = await AppCommon.api('/api/config/reload', { method: 'POST' }); state.data = result.config; update(); AppCommon.showToast(result.message, 'success'); }
        catch (error) { AppCommon.showToast(error.message, 'error'); }
        reload.disabled = false;
      }
    };
  }

  window.Pages.config = { render: render, init: function () { bind(); load(); } };
})();
