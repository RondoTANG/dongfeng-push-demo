(function () {
  'use strict';

  var state = { data: null, loading: true, error: null, tab: 'brands' };
  var tabs = [
    ['brands', '品牌与实体'], ['queries', '查询目录'], ['sources', '来源识别'],
    ['processing', '处理规则'], ['risks', '风险标签'], ['drafts', '作业草案'], ['hotspot', '热点数据准入']
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

  function canEdit() { return window.Auth && Auth.canWrite(); }
  function listValue(value) { return (value || []).join('、'); }
  function parseList(value) { return String(value || '').split(/[、,，\n]/).map(function (item) { return item.trim(); }).filter(Boolean); }
  function editButton(kind, id) { return canEdit() ? '<button class="btn btn-text btn-sm" data-edit-config="' + kind + '" data-config-id="' + AppCommon.escapeHtml(id) + '">编辑</button><button class="btn btn-text btn-sm text-danger" data-delete-config="' + kind + '" data-config-id="' + AppCommon.escapeHtml(id) + '">删除</button>' : '—'; }

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
      { label: '状态', width: '90px', render: function (row) { return boolTag(row.status === 'active', '启用', '停用'); } },
      { label: '操作', width: '130px', render: function (row) { return editButton('brand', row.brand_id); } }
    ];
    return '<div class="config-section-head"><div class="rule-note"><strong>识别原则</strong><ul>' + data.rules.map(function (item) { return '<li>' + AppCommon.escapeHtml(item) + '</li>'; }).join('') + '</ul></div>' + (canEdit() ? '<button class="btn btn-primary" data-add-config="brand">新增品牌</button>' : '') + '</div>' + DataTable.render(columns, data.items);
  }

  function renderQueries() {
    var execution = state.data.queries.execution;
    var columns = [
      { label: '编号', width: '80px', render: function (row) { return '<span class="mono">' + row.query_id + '</span>'; } },
      { label: '类型', width: '120px', key: 'group_name' },
      { label: '目标品牌', width: '140px', render: function (row) { return AppCommon.escapeHtml(row.brand_name || '行业线索'); } },
      { label: '实际查询词', key: 'query' },
      { label: '状态', width: '90px', render: function (row) { return boolTag(row.enabled); } },
      { label: '操作', width: '130px', render: function (row) { return editButton('query', row.query_id); } }
    ];
    var activeCount = state.data.queries.items.filter(function (item) { return item.enabled; }).length;
    return '<div class="config-section-actions">' + (canEdit() ? '<button class="btn btn-primary" data-add-config="query">新增查询</button>' : '') + '</div><div class="config-policy-strip"><div><span>每次完整运行</span><strong>执行当前启用的' + activeCount + '条</strong></div><div><span>基础时间窗口</span><strong>' + execution.lookback_hours + '小时／延迟线索' + execution.late_signal_hours + '小时</strong></div><div><span>行业事件品牌验证</span><strong>按当前启用品牌核验</strong></div></div><p class="section-caption">' + AppCommon.escapeHtml(execution.provider_failure_policy) + '</p>' + DataTable.render(columns, state.data.queries.items);
  }

  function renderSources() {
    var data = state.data.sources;
    var providers = '<div class="provider-grid">' + data.providers.map(function (item) {
      return '<article class="provider-card"><div class="provider-card__head"><div><strong>' + AppCommon.escapeHtml(item.display_name) + '</strong><span class="mono">' + AppCommon.escapeHtml(item.provider_id) + '</span></div>' + (item.can_judge_hotspot ? '<span class="status-tag status-green">可判热点</span>' : '<span class="status-tag status-neutral">不判热点</span>') + '</div><p>' + AppCommon.escapeHtml(item.role) + '</p><div class="capability-row"><span>' + (item.can_discover ? '可发现内容' : '仅已知链接') + '</span><span>原生指标：' + (item.has_native_metrics === true ? '支持' : item.has_native_metrics === false ? '不支持' : '按平台部分支持') + '</span></div></article>';
    }).join('') + '</div>';
    var platformColumns = [
      { label: '平台名称', render: function (row) { return '<div class="cell-title">' + AppCommon.escapeHtml(row.display_name) + '</div><div class="cell-sub mono">' + AppCommon.escapeHtml(row.platform_id) + '</div>'; } },
      { label: '账号字段', width: '120px', render: function (row) { return boolTag(row.account_supported, '支持', '不支持'); } },
      { label: 'PoC覆盖方式', render: function (row) { return AppCommon.escapeHtml(platformNames[row.poc_coverage] || row.poc_coverage); } },
      { label: '操作', width: '130px', render: function (row) { return editButton('platform', row.platform_id); } }
    ];
    var columns = [
      { label: '域名', width: '190px', render: function (row) { return '<span class="mono">' + AppCommon.escapeHtml(row.domain) + '</span>'; } },
      { label: '站点名称', key: 'site_name' },
      { label: '识别平台', width: '170px', render: function (row) { var found = data.platforms.find(function (item) { return item.platform_id === row.source_platform; }); return AppCommon.escapeHtml(found ? found.display_name : row.source_platform); } },
      { label: '品牌关系', render: function (row) { return AppCommon.escapeHtml((row.related_brands || []).join('、') || '不由域名直接确认'); } },
      { label: '操作', width: '130px', render: function (row) { return editButton('domain', row.domain); } }
    ];
    return '<div class="config-source-explain"><strong>来源识别分三层</strong><span>采集器能力用于说明豆包、Codex等服务边界，只读；来源平台定义和域名识别规则来自《来源平台字典》，可由管理员维护。</span></div>' + providers + '<div class="config-section-title"><h3 class="section-title">来源平台定义</h3>' + (canEdit() ? '<button class="btn" data-add-config="platform">新增平台</button>' : '') + '</div>' + DataTable.render(platformColumns, data.platforms) + '<div class="config-section-title"><h3 class="section-title">站点与域名识别规则</h3>' + (canEdit() ? '<button class="btn btn-primary" data-add-config="domain">新增域名规则</button>' : '') + '</div>' + DataTable.render(columns, data.domains) + '<p class="section-caption">未命中域名规则的来源保留为“待识别来源”，不会因 AI 猜测自动升级为官方来源。</p>';
  }

  function renderProcessing() {
    var data = state.data.processing;
    var invalid = '<div class="rule-card-grid">' + data.invalid_rules.map(function (rule) {
      return '<article class="rule-card"><div><span class="mono">' + rule.rule_id + '</span><strong>' + AppCommon.escapeHtml(rule.name) + '</strong></div><p>' + AppCommon.escapeHtml(rule.condition) + '</p><footer>命中后自动记入无效日志，不交给运营审核</footer></article>';
    }).join('') + '</div>';
    var dedup = data.deduplication.map(function (item) { return '<div class="process-step"><span>' + AppCommon.escapeHtml(item.level) + '</span><p>' + AppCommon.escapeHtml(item.action) + '</p></div>'; }).join('');
    return '<h3 class="section-title">自动无效规则</h3>' + invalid + '<h3 class="section-title">去重与事件聚合</h3><div class="process-list">' + dedup + '<div class="process-step is-emphasis"><span>事件聚合</span><p>' + AppCommon.escapeHtml(data.event_clustering.aggregation_rule) + '</p></div><div class="process-step"><span>独立来源</span><p>' + AppCommon.escapeHtml(data.event_clustering.independent_source_rule) + '</p></div></div>';
  }

  function renderRisks() {
    var rules = state.data.processing.risk_rules || [];
    return '<p class="section-caption">风险标签由清洗聚合与判定规则配置驱动。命中关键词仅提示需要核验，不代表事件为负面；此处展示生效配置，修改配置文件后重新加载生效。</p>' + DataTable.render([
      {label:'风险标签',key:'name'}, {label:'触发关键词',render:function(row){return AppCommon.escapeHtml((row.keywords || []).join('、') || '证据核验／人工确认');}},
      {label:'核验要求',key:'description'}, {label:'状态',render:function(row){return boolTag(row.enabled);}}
    ], rules);
  }

  function renderDrafts() {
    var data = state.data.drafts;
    var stage = state.data.stage;
    return '<div class="stage-card"><div><span>当前有效流程</span><strong>' + AppCommon.escapeHtml(stage.scope) + '</strong></div><div class="stage-stop"><span>明确暂不进入</span><strong>' + stage.deferred.join('、') + '</strong></div></div>' +
      '<div class="config-two-columns"><section><h3>原创主链与关联内容支路</h3><div class="plain-list"><p><span>原创增长</span>基于事件证据生成原创评论／内容方向，实际发布后继续追踪后效</p><p><span>关联内容直加</span>只在事件存在可执行文章或视频时，绑定目标生成点赞、正向评论等动作</p><p><span>草案状态</span>待审批、已通过、已驳回</p><p><span>审批要求</span>三类草案分别审批，均不自动下发</p><p><span>用户匹配</span>' + AppCommon.escapeHtml(data.member_label_source) + '</p></div></section><section><h3>建议目标平台</h3><div class="tag-row">' + data.target_platforms.map(function (item) { return '<span class="mini-tag">' + (platformNames[item] || item) + '</span>'; }).join('') + '</div><h3 class="section-title">关联内容直加动作</h3><div class="tag-row">' + data.boost_actions.map(function (item) { return '<span class="mini-tag mono">' + item + '</span>'; }).join('') + '</div><h3 class="section-title">共用必备信息</h3><div class="tag-row">' + data.required_fields.map(function (item) { return '<span class="mini-tag mono">' + item + '</span>'; }).join('') + '</div></section></div><div class="rule-note"><strong>生成约束</strong><p>' + AppCommon.escapeHtml(data.generation_rule) + '</p><p>' + AppCommon.escapeHtml(data.boost_generation_rule) + '</p><p>' + AppCommon.escapeHtml(data.boost_target_rule) + '</p><p>' + AppCommon.escapeHtml(data.hotspot_disclaimer_rule) + '</p></div>';
  }

  function renderHotspot() {
    var data = state.data.hotspot;
    return '<div class="hotspot-boundary"><span>当前系统结论</span><h3>' + AppCommon.escapeHtml(data.current_output) + '</h3><p>' + AppCommon.escapeHtml(data.production_dependency) + '</p></div><div class="config-two-columns"><section><h3>允许判定真实热点前，必须同时具备</h3><ol class="readiness-list">' + data.required_capabilities.map(function (item) { return '<li><span>必须</span>' + (capabilityNames[item] || item) + '</li>'; }).join('') + '</ol></section><section><h3>禁止单独作为热度依据</h3><div class="prohibited-grid">' + data.prohibited_signals.map(function (item) { return '<span>' + (capabilityNames[item] || item) + '</span>'; }).join('') + '</div><div class="non-bypass">该规则没有“强制绕过”开关；数据条件不满足时必须说明具体缺失原因。</div></section></div>';
  }

  function renderPanel() {
    var renderer = { brands: renderBrands, queries: renderQueries, sources: renderSources, processing: renderProcessing, risks: renderRisks, drafts: renderDrafts, hotspot: renderHotspot }[state.tab];
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

  function field(label, name, value, options) {
    options = options || {};
    if (options.type === 'select') return '<div class="form-field"><label>' + label + '</label><select class="form-control" name="' + name + '">' + options.items.map(function (item) { return '<option value="' + AppCommon.escapeHtml(item.value) + '"' + (item.value === value ? ' selected' : '') + '>' + AppCommon.escapeHtml(item.label) + '</option>'; }).join('') + '</select></div>';
    return '<div class="form-field' + (options.full ? ' full' : '') + '"><label>' + label + '</label><input class="form-control" name="' + name + '" value="' + AppCommon.escapeHtml(value || '') + '"' + (options.readonly ? ' readonly' : '') + '></div>';
  }

  function openEditor(kind, item) {
    item = item || {};
    var isNew = !Object.keys(item).length;
    var body = '', title = '', endpoint = '', method = isNew ? 'POST' : 'PUT';
    if (kind === 'brand') {
      title = isNew ? '新增品牌' : '编辑品牌'; endpoint = '/api/config/brands' + (isNew ? '' : '/' + encodeURIComponent(item.brand_id));
      body = field('品牌编号', 'brand_id', item.brand_id, { readonly: !isNew }) + field('品牌标准名称', 'canonical_name', item.canonical_name) +
        field('状态', 'status', item.status || 'active', { type: 'select', items: [{value:'active',label:'启用'}, {value:'inactive',label:'停用'}] }) +
        field('确定性别名（顿号分隔）', 'exact_aliases', listValue(item.exact_aliases), { full: true }) + field('弱别名（顿号分隔）', 'weak_aliases', listValue(item.weak_aliases), { full: true }) +
        field('弱别名所需汽车语境（顿号分隔）', 'weak_alias_context_terms', listValue(item.weak_alias_context_terms), { full: true }) + field('官方域名（顿号分隔）', 'official_domains', listValue(item.official_domains), { full: true });
    } else if (kind === 'query') {
      title = isNew ? '新增查询' : '编辑查询'; endpoint = '/api/config/queries' + (isNew ? '' : '/' + encodeURIComponent(item.query_id));
      var brandOptions = state.data.brands.items.map(function (brand) { return { value: brand.brand_id, label: brand.canonical_name + '（' + brand.brand_id + '）' }; });
      body = field('查询编号', 'query_id', item.query_id, { readonly: !isNew }) + field('查询类型', 'query_group', item.query_group || 'brand', { type: 'select', items: [{value:'brand',label:'品牌查询'}, {value:'topic',label:'行业主题查询'}] }) +
        field('关联品牌', 'brand_id', item.brand_id || (brandOptions[0] || {}).value, { type: 'select', items: brandOptions }) + field('主题编号', 'topic_id', item.topic_id || '') +
        field('真实搜索内容', 'query', item.query, { full: true }) + field('状态', 'enabled', item.enabled === false ? 'false' : 'true', { type: 'select', items: [{value:'true',label:'启用'}, {value:'false',label:'停用'}] });
    } else if (kind === 'platform') {
      title = isNew ? '新增来源平台' : '编辑来源平台'; endpoint = '/api/config/platforms' + (isNew ? '' : '/' + encodeURIComponent(item.platform_id));
      body = field('平台编号', 'platform_id', item.platform_id, { readonly: !isNew }) + field('平台名称', 'display_name', item.display_name) +
        field('支持账号字段', 'account_fields_supported', item.account_supported ? 'true' : 'false', { type: 'select', items: [{value:'true',label:'支持'}, {value:'false',label:'不支持'}] }) +
        field('PoC覆盖方式', 'poc_coverage', item.poc_coverage || 'public_web', { type: 'select', items: [{value:'public_web',label:'公开网页'}, {value:'public_pages_partial',label:'公开页面部分覆盖'}, {value:'known_url_metrics',label:'已知链接指标查询'}, {value:'not_guaranteed',label:'不保证覆盖'}, {value:'unknown',label:'待确认'}] });
    } else {
      title = isNew ? '新增域名识别规则' : '编辑域名识别规则'; endpoint = '/api/config/domains' + (isNew ? '' : '/' + encodeURIComponent(item.domain));
      var platformOptions = state.data.sources.platforms.map(function (platform) { return { value: platform.platform_id, label: platform.display_name }; });
      body = field('域名（不含协议和路径）', 'domain', item.domain, { readonly: !isNew }) + field('站点名称', 'source_site_name', item.site_name) +
        field('识别平台', 'source_platform', item.source_platform || (platformOptions[0] || {}).value, { type: 'select', items: platformOptions }) +
        field('发布者类型', 'publisher_type', item.publisher_type || 'media') + field('关联品牌编号（顿号分隔）', 'related_brand_ids', listValue(item.related_brand_ids), { full: true }) +
        field('状态', 'status', item.status || 'active', { type: 'select', items: [{value:'active',label:'启用'}, {value:'inactive',label:'停用'}] });
    }
    var drawer = UI.openDrawer({ title: title, body: '<form class="review-form config-edit-form" data-config-form data-kind="' + kind + '" data-endpoint="' + endpoint + '" data-method="' + method + '">' + body + '</form>', footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-save-config>保存配置</button>' });
    drawer.element.querySelector('[data-save-config]').onclick = async function (event) {
      var form = drawer.element.querySelector('[data-config-form]'), values = Object.fromEntries(new FormData(form).entries()), payload;
      if (kind === 'brand') payload = { brand_id: values.brand_id, canonical_name: values.canonical_name, status: values.status, entity_type: item.entity_type || 'brand', exact_aliases: parseList(values.exact_aliases), weak_aliases: parseList(values.weak_aliases), weak_alias_context_terms: parseList(values.weak_alias_context_terms), official_domains: parseList(values.official_domains), official_accounts: item.official_accounts || [] };
      if (kind === 'query') payload = { query_id: values.query_id, query_group: values.query_group, query: values.query, brand_id: values.query_group === 'brand' ? values.brand_id : null, topic_id: values.query_group === 'topic' ? values.topic_id : null, enabled: values.enabled === 'true' };
      if (kind === 'platform') payload = { platform_id: values.platform_id, display_name: values.display_name, account_fields_supported: values.account_fields_supported === 'true', poc_coverage: values.poc_coverage };
      if (kind === 'domain') payload = { domain: values.domain, source_site_name: values.source_site_name, source_platform: values.source_platform, publisher_type: values.publisher_type, related_brand_ids: parseList(values.related_brand_ids), status: values.status };
      event.currentTarget.disabled = true;
      try { var result = await AppCommon.api(form.dataset.endpoint, { method: form.dataset.method, body: JSON.stringify(payload) }); state.data = result.config; drawer.close(); update(); AppCommon.showToast('配置已保存，新运行批次立即使用', 'success'); }
      catch (error) { AppCommon.showToast(error.message, 'error'); event.currentTarget.disabled = false; }
    };
  }

  async function removeConfig(kind, id) {
    var names = { brand: '品牌', query: '查询', platform: '来源平台', domain: '域名规则' };
    if (!window.confirm('确认删除该' + names[kind] + '？已产生的历史批次不会被改写。')) return;
    try { var result = await AppCommon.api('/api/config/' + ({brand:'brands',query:'queries',platform:'platforms',domain:'domains'}[kind]) + '/' + encodeURIComponent(id), { method: 'DELETE' }); state.data = result.config; update(); AppCommon.showToast('已删除并记录审计', 'success'); }
    catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = async function (event) {
      var tab = event.target.closest('[data-config-tab]');
      if (tab) { state.tab = tab.dataset.configTab; return update(); }
      if (event.target.closest('[data-config-versions]')) return openVersions();
      if (event.target.closest('[data-retry-action]')) return load();
      var add = event.target.closest('[data-add-config]');
      if (add) return openEditor(add.dataset.addConfig);
      var edit = event.target.closest('[data-edit-config]');
      if (edit) {
        var kind = edit.dataset.editConfig, id = edit.dataset.configId, item;
        if (kind === 'brand') item = state.data.brands.items.find(function (row) { return row.brand_id === id; });
        if (kind === 'query') item = state.data.queries.items.find(function (row) { return row.query_id === id; });
        if (kind === 'platform') item = state.data.sources.platforms.find(function (row) { return row.platform_id === id; });
        if (kind === 'domain') item = state.data.sources.domains.find(function (row) { return row.domain === id; });
        return openEditor(kind, item);
      }
      var remove = event.target.closest('[data-delete-config]');
      if (remove) return removeConfig(remove.dataset.deleteConfig, remove.dataset.configId);
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
