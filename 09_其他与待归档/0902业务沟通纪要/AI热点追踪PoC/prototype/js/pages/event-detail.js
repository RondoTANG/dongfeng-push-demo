(function () {
  'use strict';

  var state = { events: [], selected: null, loading: true, error: null, status: '' };

  function brandTags(relations) {
    if (!relations || !relations.length) return '<span class="mini-tag">品牌关系待核验</span>';
    return relations.map(function (item) {
      return '<span class="mini-tag">' + AppCommon.escapeHtml(item.brand_name || '未识别品牌') + ' · ' + AppCommon.escapeHtml(item.relation_status) + '</span>';
    }).join('');
  }

  function renderQueue() {
    var items = state.status ? state.events.filter(function (item) { return item.event_status === state.status; }) : state.events;
    return '<aside class="event-queue"><div class="event-queue__head"><strong>事件队列</strong><select class="form-control" data-event-status-filter><option value="">全部结论</option>' +
      [['needs_evidence','待补证'],['pending_review','待审核'],['manual_review','人工研判'],['brand_content_opportunity','品牌内容机会'],['relevant_event_clue','相关事件线索'],['watch','观察'],['rejected','已驳回']].map(function (item) { return '<option value="' + item[0] + '"' + (state.status === item[0] ? ' selected' : '') + '>' + item[1] + '</option>'; }).join('') + '</select></div><div class="event-queue__list">' +
      (items.length ? items.map(function (item) {
        return '<button class="event-queue__item' + (state.selected && state.selected.event_id === item.event_id ? ' is-active' : '') + '" data-select-event="' + item.event_id + '"><span class="event-queue__title">' + AppCommon.escapeHtml(item.event_title) + '</span><span class="event-queue__meta">' + AppCommon.escapeHtml(item.event_date || '时间不明') + AppCommon.statusTag(item.event_status) + '</span><span class="event-queue__heat">热点：不可判定</span></button>';
      }).join('') : '<div class="empty-state compact"><span>当前筛选下暂无事件</span></div>') + '</div></aside>';
  }

  function renderDetail() {
    var event = state.selected;
    if (!event) return '<section class="event-detail-panel"><div class="empty-state"><strong>请选择事件</strong><span>从左侧事件队列查看证据与审核状态</span></div></section>';
    var workItem = (event.work_items || [])[0];
    var canReview = event.event_status !== 'rejected';
    return '<section class="event-detail-panel" data-anno="event-evidence-review">' +
      '<header class="event-detail-head"><div><div class="event-kicker"><span class="mono">' + event.event_id + '</span>' + AppCommon.statusTag(event.event_status) + '</div><h2>' + AppCommon.escapeHtml(event.event_title) + '</h2><div class="tag-row">' + brandTags(event.brand_relations) + '</div></div><div class="page-head__actions"><button class="btn" data-split-event>拆分</button><button class="btn" data-merge-event>合并</button>' + (canReview ? '<button class="btn btn-primary" data-review-event>审核事件</button>' : '') + '</div></header>' +
      '<div class="fact-grid"><div><span>事件时间</span><strong>' + AppCommon.escapeHtml(event.event_date || '时间不明') + '</strong></div><div><span>来源／独立来源</span><strong>' + event.source_count + ' / ' + event.independent_source_count + '</strong></div><div><span>覆盖平台</span><strong>' + AppCommon.escapeHtml((event.source_platforms || []).join('、') || '待识别') + '</strong></div><div><span>Codex 工作项</span>' + (workItem ? AppCommon.statusTag(workItem.status) : '<span class="mini-tag">无工作项</span>') + '</div></div>' +
      '<div class="heat-gate"><div class="heat-gate__title"><span>数据准入未满足</span><strong>热点不可判定</strong></div><p>当前事件由公开搜索线索形成，可支持事实研判，但不能证明哪个平台正在快速发酵。</p><ul>' + (event.hotspot_unavailable_reason || []).map(function (reason) { return '<li>' + AppCommon.escapeHtml(reason) + '</li>'; }).join('') + '</ul></div>' +
      '<div class="detail-columns"><div><section class="detail-section"><h3>证据时间线</h3>' + EvidenceTimeline.render(event.evidence) + '</section></div><div>' +
      '<section class="detail-section"><h3>存疑与风险</h3>' +
        '<div class="info-block"><span>动态实体存疑</span>' + ((event.entity_uncertainties || []).length ? event.entity_uncertainties.map(function (item) { return '<p>' + AppCommon.escapeHtml(item.entity_name_raw || item.entity_name || '未命名实体') + '：' + AppCommon.escapeHtml(item.uncertainty_reason) + '</p>'; }).join('') : '<p class="text-muted">暂无动态实体存疑</p>') + '</div>' +
        '<div class="info-block"><span>风险标签</span><div class="tag-row">' + ((event.risk_tags || []).length ? event.risk_tags.map(function (tag) { return '<span class="mini-tag">' + AppCommon.escapeHtml(tag) + '</span>'; }).join('') : '<span class="text-muted">未识别明确风险标签</span>') + '</div></div></section>' +
      '<section class="detail-section"><h3>当前判断</h3><p class="decision-copy">' + AppCommon.escapeHtml(event.decision_reason || '等待 Codex 补证或运营审核。') + '</p></section>' +
      '</div></div></section>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在加载事件和证据</div>';
    if (state.error) return UI.errorState(state.error, true);
    return '<div class="event-workspace">' + renderQueue() + renderDetail() + '</div>';
  }

  function render() {
    return '<section class="page page-wide">' + Layout.pageHead('事件审核', '从事件事实、证据和数据缺口出发形成运营结论') + '<div id="event-detail-content">' + renderContent() + '</div></section>';
  }

  async function load(preferredId) {
    state.loading = true; state.error = null; update();
    try {
      var result = await AppCommon.api('/api/events?limit=500');
      state.events = result.items;
      var eventId = preferredId || (window.AppContext && window.AppContext.eventId) || (state.events[0] && state.events[0].event_id);
      state.selected = eventId ? await AppCommon.api('/api/events/' + eventId) : null;
      window.AppContext = null;
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  async function selectEvent(eventId) {
    try { state.selected = await AppCommon.api('/api/events/' + eventId); update(); }
    catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function update() { var root = document.getElementById('event-detail-content'); if (root) root.innerHTML = renderContent(); }

  function openReview() {
    var drawer = ReviewDrawer.eventReview(state.selected);
    drawer.element.querySelector('[data-submit-event-review]').onclick = async function (event) {
      var button = event.currentTarget; button.disabled = true;
      var root = drawer.element.querySelector('[data-event-review-form]');
      var value = function (name) { return root.querySelector('[name="' + name + '"]').value.trim(); };
      var actionPaths = Array.from(root.querySelectorAll('[name="action_path"]:checked')).map(function (item) { return item.value; });
      var boostSource = root.querySelector('[name="boost_source_id"]:checked');
      var payload = {
        review_result: value('review_result'), event_status: value('event_status'), reviewer: '本地运营',
        review_note: value('review_note') || null, evidence_summary: value('evidence_summary'),
        risk_summary: value('risk_summary'), recommended_action: value('recommended_action'),
        action_paths: actionPaths,
        boost_source_ids: actionPaths.indexOf('source_content_boost') >= 0 && boostSource ? [boostSource.value] : []
      };
      try {
        var result = await AppCommon.api('/api/events/' + state.selected.event_id + '/review', { method: 'POST', body: JSON.stringify(payload) });
        drawer.close(); state.selected = result.event;
        state.events = (await AppCommon.api('/api/events?limit=500')).items; update();
        var count = (result.drafts || []).length;
        AppCommon.showToast(count ? '事件已通过并生成 ' + count + ' 份作业草案' : '事件结论已保存', 'success');
      } catch (error) { button.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = function (event) {
      var selectButton = event.target.closest('[data-select-event]');
      if (selectButton) return selectEvent(selectButton.dataset.selectEvent);
      if (event.target.closest('[data-review-event]')) return openReview();
      if (event.target.closest('[data-retry-action]')) return load();
      if (event.target.closest('[data-merge-event]')) return AppCommon.showToast('合并接口已就绪；请先在后续批量选择交互中选择至少两个事件');
      if (event.target.closest('[data-split-event]')) return AppCommon.showToast('拆分需选择当前事件中的来源证据，接口已保留审计');
    };
    page.onchange = function (event) { if (event.target.matches('[data-event-status-filter]')) { state.status = event.target.value; update(); } };
  }

  window.Pages['event-detail'] = { render: render, init: function () { bind(); load(); } };
})();
