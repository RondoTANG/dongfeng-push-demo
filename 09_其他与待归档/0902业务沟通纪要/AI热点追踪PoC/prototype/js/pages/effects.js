(function () {
  'use strict';

  var state = { publications: [], approvedDrafts: [], selected: null, loading: true, error: null, status: '' };
  var platformNames = { weibo: '微博', douyin: '抖音', wechat_official_account: '公众号', wechat_channels: '视频号', toutiao: '今日头条', xiaohongshu: '小红书', bilibili: 'B站', autohome: '汽车之家', dongchedi: '懂车帝' };
  var metricNames = { view_count: '播放／阅读', like_count: '点赞', comment_count: '评论', share_count: '转发', favorite_count: '收藏' };
  var decisionNames = { create_followup_boost: '生成二次加热草案', watch: '继续观察', no_boost: '无需加热', manual_review: '数据人工核验' };
  var statusNames = { tracking: '追踪中', manual_review: '待核验', boost_draft_created: '已生成加热草案', closed: '已结束' };

  function renderSummary() {
    var count = function (status) { return state.publications.filter(function (item) { return item.tracking_status === status; }).length; };
    return '<div class="metrics-grid effect-metrics">' +
      '<article class="metric-card"><span>原创发布记录</span><strong>' + state.publications.length + '</strong><small>仅来自已审批原创增长草案</small></article>' +
      '<article class="metric-card"><span>后效追踪中</span><strong>' + count('tracking') + '</strong><small>等待更多时间快照或运营判断</small></article>' +
      '<article class="metric-card"><span>待人工核验</span><strong>' + count('manual_review') + '</strong><small>指标异常、缺失或口径不一致</small></article>' +
      '<article class="metric-card"><span>二次加热草案</span><strong>' + count('boost_draft_created') + '</strong><small>已进入独立草案审批</small></article>' +
      '</div>';
  }

  function renderList() {
    var items = state.status ? state.publications.filter(function (item) { return item.tracking_status === state.status; }) : state.publications;
    return '<aside class="effect-list"><div class="event-queue__head"><strong>已发布原创</strong><select class="form-control" data-effect-status-filter><option value="">全部状态</option>' +
      Object.keys(statusNames).map(function (key) { return '<option value="' + key + '"' + (state.status === key ? ' selected' : '') + '>' + statusNames[key] + '</option>'; }).join('') +
      '</select></div><div class="event-queue__list">' +
      (items.length ? items.map(function (item) {
        return '<button class="effect-list__item' + (state.selected && state.selected.publication_id === item.publication_id ? ' is-active' : '') + '" data-select-publication="' + item.publication_id + '">' +
          '<span class="event-queue__title">' + AppCommon.escapeHtml(item.content_title || (item.original_draft || {}).task_title || '未命名原创内容') + '</span>' +
          '<span class="event-queue__meta"><span>' + AppCommon.escapeHtml(platformNames[item.platform] || item.platform) + '</span>' + AppCommon.statusTag(item.tracking_status) + '</span>' +
          '<span class="event-queue__heat">' + (item.snapshots || []).length + ' 个指标快照 · ' + AppCommon.escapeHtml(item.latest_evaluation ? decisionNames[item.latest_evaluation.decision] : '尚未判断') + '</span></button>';
      }).join('') : '<div class="empty-state compact"><span>当前筛选下暂无原创发布记录</span></div>') + '</div></aside>';
  }

  function metricCells(metrics) {
    var keys = Object.keys(metrics || {});
    if (!keys.length) return '<span class="text-muted">本次未获得可用指标</span>';
    return '<div class="snapshot-metrics">' + keys.map(function (key) {
      return '<div><span>' + AppCommon.escapeHtml(metricNames[key] || key) + '</span><strong>' + Number(metrics[key]).toLocaleString('zh-CN') + '</strong></div>';
    }).join('') + '</div>';
  }

  function renderSnapshots(publication) {
    var snapshots = publication.snapshots || [];
    if (!snapshots.length) return '<div class="empty-state compact"><strong>尚无后效数据</strong><span>至少录入两个时间快照，才能计算同一原创内容的传播增量。</span></div>';
    return '<div class="snapshot-timeline">' + snapshots.map(function (item, index) {
      return '<article class="snapshot-card"><header><span>快照 ' + (index + 1) + '</span><strong>' + AppCommon.formatTime(item.captured_at) + '</strong><small>' + AppCommon.escapeHtml(item.data_source) + '</small></header>' +
        metricCells(item.metrics) + (item.unavailable_reason ? '<p class="snapshot-warning">未采到指标：' + AppCommon.escapeHtml(item.unavailable_reason) + '</p>' : '') +
        (item.note ? '<p>' + AppCommon.escapeHtml(item.note) + '</p>' : '') + '</article>';
    }).join('') + '</div>';
  }

  function renderEvaluation(publication) {
    var evaluation = publication.latest_evaluation;
    if (!evaluation) return '<div class="effect-decision is-empty"><strong>尚未形成后效判断</strong><span>系统只计算两个快照之间的增量；是否继续加热由运营结合内容价值、窗口和频控确认。</span></div>';
    return '<div class="effect-decision"><div><span>传播增长观察</span><strong>' + AppCommon.escapeHtml(evaluation.growth_status === 'growth_observed' ? '观察到指标增长' : evaluation.growth_status === 'no_growth_observed' ? '未观察到指标增长' : '指标存在异常') + '</strong></div><div><span>运营结论</span><strong>' + AppCommon.escapeHtml(decisionNames[evaluation.decision] || evaluation.decision) + '</strong></div><div class="full"><span>判断说明</span><p>' + AppCommon.escapeHtml(evaluation.decision_reason) + '</p></div>' +
      metricCells(evaluation.delta_metrics) +
      (evaluation.created_draft_id ? '<button class="btn btn-primary btn-sm" data-open-followup-draft="' + evaluation.created_draft_id + '">查看二次加热草案</button>' : '') + '</div>';
  }

  function renderDetail() {
    var publication = state.selected;
    if (!publication) return '<section class="effect-detail"><div class="empty-state"><strong>登记原创发布结果</strong><span>从已审批原创增长草案回填实际发布链接，开始后效数据追踪。</span><button class="btn btn-primary" data-create-publication>登记发布结果</button></div></section>';
    var draft = publication.original_draft || {};
    var event = publication.event || {};
    return '<section class="effect-detail" data-anno="original-effect-loop"><header class="event-detail-head"><div><div class="event-kicker"><span class="mono">' + publication.publication_id + '</span>' + AppCommon.statusTag(publication.tracking_status) + '</div><h2>' + AppCommon.escapeHtml(publication.content_title || draft.task_title || '未命名原创内容') + '</h2><div class="tag-row"><span class="mini-tag">' + AppCommon.escapeHtml(platformNames[publication.platform] || publication.platform) + '</span><span class="mini-tag">发布：' + AppCommon.formatTime(publication.published_at) + '</span></div></div><div class="page-head__actions"><button class="btn" data-create-publication>登记另一条</button><button class="btn" data-add-snapshot>录入指标快照</button><button class="btn btn-primary" data-evaluate-publication>后效判断</button></div></header>' +
      '<div class="effect-origin"><div><span>关联事件</span><strong>' + AppCommon.escapeHtml(event.event_title || publication.event_id) + '</strong></div><div><span>来源原创草案</span><strong>' + AppCommon.escapeHtml(draft.task_title || publication.original_draft_id) + '</strong></div><div><span>原创链接</span><a href="' + AppCommon.escapeHtml(publication.content_url) + '" target="_blank" rel="noopener">' + AppCommon.escapeHtml(publication.content_url) + '</a></div></div>' +
      '<div class="effect-boundary"><strong>该分支只追踪已发布原创内容</strong><span>热点源内容加热仍直接绑定事件中的外部文章或视频，两者目标内容、触发条件和草案类型互不替代。</span></div>' +
      '<section class="detail-section"><h3>后效指标快照</h3>' + renderSnapshots(publication) + '</section>' +
      '<section class="detail-section"><h3>增长与二次加热判断</h3>' + renderEvaluation(publication) + '</section></section>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在加载原创后效记录</div>';
    if (state.error) return UI.errorState(state.error, true);
    return renderSummary() + '<div class="effect-workspace">' + renderList() + renderDetail() + '</div>';
  }

  function render() {
    return '<section class="page page-wide">' + Layout.pageHead('原创后效追踪', '原创发布后回收链接与指标快照，判断是否需要生成独立的二次加热草案', '<button class="btn btn-primary" data-create-publication>登记原创发布结果</button>') + '<div id="effects-content">' + renderContent() + '</div></section>';
  }

  function update() { var root = document.getElementById('effects-content'); if (root) root.innerHTML = renderContent(); }

  async function load(preferredId) {
    state.loading = true; state.error = null; update();
    try {
      var results = await Promise.all([AppCommon.api('/api/publications?limit=500'), AppCommon.api('/api/drafts?purpose=original_growth&status=approved&limit=500')]);
      state.publications = results[0].items; state.approvedDrafts = results[1].items;
      var id = preferredId || (state.publications[0] && state.publications[0].publication_id);
      state.selected = id ? await AppCommon.api('/api/publications/' + id) : null;
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  async function selectPublication(id) {
    try { state.selected = await AppCommon.api('/api/publications/' + id); update(); }
    catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function localDateTimeValue(date) {
    var pad = function (value) { return String(value).padStart(2, '0'); };
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) + 'T' + pad(date.getHours()) + ':' + pad(date.getMinutes());
  }

  function openCreatePublication() {
    var options = state.approvedDrafts.map(function (draft) { return '<option value="' + draft.task_draft_id + '">' + AppCommon.escapeHtml(draft.task_title) + '</option>'; }).join('');
    var drawer = UI.openDrawer({
      title: '登记原创发布结果',
      body: '<div class="review-form"><div class="form-field full"><label>已审批原创增长草案</label><select class="form-control" name="original_draft_id"><option value="">请选择</option>' + options + '</select><small class="field-help">只有已通过的原创增长草案可以进入后效追踪。</small></div><div class="form-field"><label>发布平台</label><select class="form-control" name="platform">' + Object.keys(platformNames).map(function (key) { return '<option value="' + key + '">' + platformNames[key] + '</option>'; }).join('') + '</select></div><div class="form-field"><label>发布时间</label><input class="form-control" type="datetime-local" name="published_at" value="' + localDateTimeValue(new Date()) + '"></div><div class="form-field full"><label>原创内容标题</label><input class="form-control" name="content_title" placeholder="用于运营识别，可留空"></div><div class="form-field full"><label>原创内容链接</label><input class="form-control" name="content_url" placeholder="https://..."></div><div class="form-field full"><label>平台内容ID</label><input class="form-control" name="platform_content_id" placeholder="如可获得则填写"></div></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-submit-publication>开始追踪</button>'
    });
    drawer.element.querySelector('[data-submit-publication]').onclick = async function (event) {
      var root = drawer.element; var button = event.currentTarget; button.disabled = true;
      var value = function (name) { return root.querySelector('[name="' + name + '"]').value.trim(); };
      try {
        var publication = await AppCommon.api('/api/publications', { method: 'POST', body: JSON.stringify({ original_draft_id: value('original_draft_id'), platform: value('platform'), content_url: value('content_url'), content_title: value('content_title') || null, platform_content_id: value('platform_content_id') || null, published_at: value('published_at'), submitted_by: '本地运营' }) });
        drawer.close(); AppCommon.showToast('原创发布结果已登记，开始后效追踪', 'success'); await load(publication.publication_id);
      } catch (error) { button.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  function openSnapshot() {
    var drawer = UI.openDrawer({
      title: '录入后效指标快照',
      body: '<div class="review-form"><div class="form-field"><label>采集时间</label><input class="form-control" type="datetime-local" name="captured_at" value="' + localDateTimeValue(new Date()) + '"></div><div class="form-field"><label>数据来源</label><select class="form-control" name="data_source"><option value="existing_collector">项目现有采集服务</option><option value="business_push">业务系统推送</option><option value="manual_evidence">人工凭证录入</option></select></div>' + Object.keys(metricNames).map(function (key) { return '<div class="form-field"><label>' + metricNames[key] + '</label><input class="form-control" type="number" min="0" name="' + key + '" placeholder="未采到可留空"></div>'; }).join('') + '<div class="form-field full"><label>不可采原因</label><input class="form-control" name="unavailable_reason" placeholder="全部指标为空时必填，如公众号无法自动采集"></div><div class="form-field full"><label>备注</label><textarea class="form-control" name="note" placeholder="记录截图、口径或异常说明"></textarea></div></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-submit-snapshot>保存快照</button>'
    });
    drawer.element.querySelector('[data-submit-snapshot]').onclick = async function (event) {
      var root = drawer.element; var button = event.currentTarget; button.disabled = true; var metrics = {};
      Object.keys(metricNames).forEach(function (key) { var raw = root.querySelector('[name="' + key + '"]').value; if (raw !== '') metrics[key] = Number(raw); });
      try {
        state.selected = await AppCommon.api('/api/publications/' + state.selected.publication_id + '/snapshots', { method: 'POST', body: JSON.stringify({ captured_at: root.querySelector('[name="captured_at"]').value, data_source: root.querySelector('[name="data_source"]').value, metrics: metrics, unavailable_reason: root.querySelector('[name="unavailable_reason"]').value.trim() || null, note: root.querySelector('[name="note"]').value.trim() || null, actor_id: '本地运营' }) });
        drawer.close(); state.publications = (await AppCommon.api('/api/publications?limit=500')).items; update(); AppCommon.showToast('指标快照已保存', 'success');
      } catch (error) { button.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  function openEvaluation() {
    var count = (state.selected.snapshots || []).filter(function (item) { return Object.keys(item.metrics || {}).length; }).length;
    var drawer = UI.openDrawer({
      title: '原创发布后效判断',
      body: '<div class="review-summary"><strong>当前有 ' + count + ' 个包含指标的快照</strong><p>系统计算首个与最新快照的同口径增量，不使用跨平台统一阈值。运营判断是否继续观察、无需加热，或生成独立二次加热草案。</p></div><div class="review-form"><div class="form-field full"><label>处理结论</label><select class="form-control" name="decision"><option value="create_followup_boost">生成原创后二次加热草案</option><option value="watch">继续观察</option><option value="no_boost">无需进一步加热</option><option value="manual_review">指标需人工核验</option></select></div><div class="form-field full"><label>判断说明</label><textarea class="form-control tall" name="decision_reason" placeholder="说明增长情况、业务价值、时间窗口、指标口径和是否需要加热"></textarea></div></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-submit-evaluation>保存判断</button>'
    });
    drawer.element.querySelector('[data-submit-evaluation]').onclick = async function (event) {
      var root = drawer.element; var button = event.currentTarget; button.disabled = true;
      try {
        var result = await AppCommon.api('/api/publications/' + state.selected.publication_id + '/evaluate', { method: 'POST', body: JSON.stringify({ decision: root.querySelector('[name="decision"]').value, decision_reason: root.querySelector('[name="decision_reason"]').value.trim(), evaluated_by: '本地运营' }) });
        drawer.close(); state.selected = result.publication; state.publications = (await AppCommon.api('/api/publications?limit=500')).items; update(); AppCommon.showToast(result.draft ? '后效判断已保存，并生成二次加热草案' : '后效判断已保存', 'success');
      } catch (error) { button.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = function (event) {
      var item = event.target.closest('[data-select-publication]'); if (item) return selectPublication(item.dataset.selectPublication);
      if (event.target.closest('[data-create-publication]')) return openCreatePublication();
      if (event.target.closest('[data-add-snapshot]')) return openSnapshot();
      if (event.target.closest('[data-evaluate-publication]')) return openEvaluation();
      if (event.target.closest('[data-retry-action]')) return load();
      var draftButton = event.target.closest('[data-open-followup-draft]'); if (draftButton) { window.AppContext = { draftId: draftButton.dataset.openFollowupDraft }; return App.navigate('drafts'); }
    };
    page.onchange = function (event) { if (event.target.matches('[data-effect-status-filter]')) { state.status = event.target.value; update(); } };
  }

  window.Pages.effects = { render: render, init: function () { bind(); load(); } };
})();
