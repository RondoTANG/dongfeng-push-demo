(function () {
  'use strict';

  var state = { events: [], selected: null, loading: true, error: null, status: '', page: 1, pageSize: 20, total: 0, mobileView: 'list', mobileListScrollTop: 0 };

  function isMobile() { return window.matchMedia('(max-width: 760px)').matches; }
  function scrollRoot() { return document.getElementById('app'); }

  function brandTags(relations) {
    if (!relations || !relations.length) return '<span class="mini-tag">品牌关系待核验</span>';
    return relations.map(function (item) {
      return '<span class="mini-tag" title="' + AppCommon.escapeHtml(item.evidence_excerpt || item.reason || '') + '">' + AppCommon.escapeHtml(item.brand_name || '未识别品牌') + ' · ' + AppCommon.escapeHtml(({direct_mention:'正文直接关联',verified_relation:'证据确认关联',unresolved:'关联待核验'})[item.relation_status] || '关联待核验') + '</span>';
    }).join('');
  }

  function aiErrorMessage(item) {
    var message = item.error_message || 'AI研判未完成，采集和事件数据不受影响。';
    var timeout = message.match(/timed out after\s+(\d+)\s+seconds/i);
    if (timeout) {
      return 'Codex AI研判超过' + timeout[1] + '秒，已停止当前事件；采集和事件数据不受影响，请稍后手工重试。';
    }
    return message;
  }

  function renderAiAnalysis(event) {
    var items = event.work_items || [];
    var item = items.length ? items[items.length - 1] : null;
    if (!item) return '<div class="ai-analysis is-pending"><div><strong>Codex AI研判尚未创建</strong><span>只有完成AI语义研判与作业蓝图后，才能通过事件并生成草案。</span></div></div>';
    var statusNames = { pending: '等待执行', in_progress: '正在分析', completed: '分析完成', failed: '执行失败', cancelled: '已取消' };
    var output = item.output || {};
    var toneNames = { positive: '正向', neutral: '中性', negative: '负向', mixed: '正负混合', unknown: '无法判断' };
    var execution = output.execution || {};
    var retry = ['pending','failed'].indexOf(item.status) >= 0 ? '<button class="btn btn-sm" data-retry-ai="' + item.work_item_id + '">' + (item.status === 'failed' ? '重新执行AI研判' : '执行AI研判') + '</button>' : '';
    return '<div class="ai-analysis is-' + item.status + '"><div class="ai-analysis__head"><div><strong>Codex AI语义研判 · ' + (statusNames[item.status] || item.status) + '</strong><span class="mono">' + AppCommon.escapeHtml(item.work_item_id) + '</span></div>' + retry + '</div>' +
      (item.status === 'completed' ? '<p>' + AppCommon.escapeHtml(output.summary || event.decision_reason || '') + '</p><div class="ai-analysis__meta"><span>内容语气：' + AppCommon.escapeHtml(toneNames[output.content_tone] || '无法判断') + '</span><span>执行器：' + AppCommon.escapeHtml(execution.executor || 'codex_cli') + '</span><span>模型：' + AppCommon.escapeHtml(execution.model || '服务器Codex默认模型') + '</span><span>尝试次数：' + Number(item.attempts || 1) + '</span></div>' : '<p>' + AppCommon.escapeHtml(aiErrorMessage(item)) + '</p><div class="ai-analysis__meta"><span>尝试次数：' + Number(item.attempts || 0) + '</span><span>失败不会影响采集数据，也不会自动重试</span></div>') + '</div>';
  }

  function renderQueue() {
    var items = state.events;
    return '<aside class="event-queue"><div class="event-queue__head"><strong>事件队列</strong><select class="form-control" data-event-status-filter><option value="">全部结论</option>' +
      [['pending_review','待审核'],['brand_content_opportunity','品牌内容机会'],['relevant_event_clue','事件事实成立'],['rejected','已驳回']].map(function (item) { return '<option value="' + item[0] + '"' + (state.status === item[0] ? ' selected' : '') + '>' + item[1] + '</option>'; }).join('') + '</select></div><div class="event-queue__list">' +
      (items.length ? items.map(function (item) {
        return '<button class="event-queue__item' + (state.selected && state.selected.event_id === item.event_id ? ' is-active' : '') + '" data-select-event="' + item.event_id + '"><span class="event-queue__title">' + AppCommon.escapeHtml(item.event_title) + '</span><span class="event-queue__meta">' + AppCommon.escapeHtml(item.event_date || '时间不明') + AppCommon.statusTag(item.event_status) + '</span><span class="event-queue__heat">热点：不可判定</span><span class="event-queue__chevron" aria-hidden="true">›</span></button>';
      }).join('') : '<div class="empty-state compact"><span>当前筛选下暂无事件</span></div>') + '</div>' + DataTable.pagination(state.page, state.pageSize, state.total, 'data-event-page') + '</aside>';
  }

  function renderDetail() {
    var event = state.selected;
    if (!event) return '<section class="event-detail-panel"><div class="empty-state"><strong>请选择事件</strong><span>从左侧事件队列查看证据与审核状态</span></div></section>';
    var canReview = event.event_status !== 'rejected';
    return '<section class="event-detail-panel" data-anno="event-evidence-review">' +
      '<div class="mobile-event-detail-nav"><button class="btn btn-text" type="button" data-mobile-event-back><span aria-hidden="true">←</span> 返回事件列表</button><span>事件详情</span></div>' +
      '<header class="event-detail-head"><div><div class="event-kicker"><span class="mono">' + event.event_id + '</span>' + AppCommon.statusTag(event.event_status) + '</div><h2>' + AppCommon.escapeHtml(event.event_title) + '</h2><div class="tag-row">' + brandTags(event.brand_relations) + '</div></div><div class="page-head__actions">' + (event.can_split ? '<button class="btn" title="将部分来源移到新事件，原事件至少保留一条来源" data-split-event>拆分</button>' : '') + '<button class="btn" title="多条事件实际描述同一事实时合并" data-merge-event>合并</button>' + (canReview ? '<button class="btn" data-evidence-plan>发起补证</button><button class="btn btn-primary" data-review-event>审核事件</button>' : '') + '</div></header>' +
      '<div class="fact-grid"><div><span>事件时间</span><strong>' + AppCommon.escapeHtml(event.event_date || '时间不明') + '</strong></div><div><span>来源／独立来源</span><strong>' + event.source_count + ' / ' + event.independent_source_count + '</strong></div><div><span>覆盖平台</span><strong>' + AppCommon.escapeHtml((event.source_platforms || []).map(AppCommon.platformName).join('、') || '待识别') + '</strong></div><div><span>当前处理</span>' + AppCommon.statusTag(event.event_status) + '</div></div>' +
      renderAiAnalysis(event) +
      '<div class="heat-gate"><div class="heat-gate__title"><span>数据准入未满足</span><strong>热点不可判定</strong></div><p>当前事件由公开搜索线索形成，可支持事实研判，但不能证明哪个平台正在快速发酵。</p><ul>' + (event.hotspot_unavailable_reason || []).map(function (reason) { return '<li>' + AppCommon.escapeHtml(reason) + '</li>'; }).join('') + '</ul></div>' +
      '<div class="detail-columns"><div><section class="detail-section"><h3>证据时间线</h3>' + EvidenceTimeline.render(event.evidence) + '</section></div><div>' +
      '<section class="detail-section"><h3>存疑与风险</h3>' +
        '<div class="info-block"><span>动态实体存疑</span>' + ((event.entity_uncertainties || []).length ? event.entity_uncertainties.map(function (item) { return '<p>' + AppCommon.escapeHtml(item.entity_name_raw || item.entity_name || '未命名实体') + '：' + AppCommon.escapeHtml(item.uncertainty_reason) + '</p>'; }).join('') : '<p class="text-muted">暂无动态实体存疑</p>') + '</div>' +
        '<div class="info-block"><span>风险标签</span><div class="tag-row">' + ((event.risk_tags || []).length ? (event.risk_labels || event.risk_tags).map(function (tag) { return '<span class="mini-tag">' + AppCommon.escapeHtml(tag) + '</span>'; }).join('') : '<span class="text-muted">未识别明确风险标签</span>') + '</div></div></section>' +
      '<section class="detail-section"><h3>当前判断</h3><p class="decision-copy">' + AppCommon.escapeHtml(event.decision_reason || '等待运营审核；如现有证据不足，可先发起定向补证。') + '</p></section>' +
      '<section class="detail-section"><h3>补证记录</h3>' + ((event.evidence_requests || []).length ? event.evidence_requests.map(function (item) { return '<div class="info-block"><span>' + AppCommon.escapeHtml(item.question) + '</span><p>' + AppCommon.statusTag(item.status) + ' ' + AppCommon.escapeHtml(item.result_summary || '方案已生成，等待确认') + '</p></div>'; }).join('') : '<p class="text-muted">尚未发起定向补证</p>') + '</section>' +
      '</div></div></section>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在加载事件和证据</div>';
    if (state.error) return UI.errorState(state.error, true);
    return '<div class="event-workspace' + (state.mobileView === 'detail' ? ' is-mobile-detail' : ' is-mobile-list') + '">' + renderQueue() + renderDetail() + '</div>';
  }

  function render() {
    return '<section class="page page-wide event-review-page">' + Layout.pageHead('事件审核', '仅研判通过东风关联筛选的事件；核验证据并决定是否生成作业草案') + '<div id="event-detail-content">' + renderContent() + '</div></section>';
  }

  async function load(preferredId) {
    state.loading = true; state.error = null; update();
    try {
      var query = '/api/events?page=' + state.page + '&page_size=' + state.pageSize + (state.status ? '&status=' + encodeURIComponent(state.status) : '');
      var result = await AppCommon.api(query);
      state.events = result.items; state.total = result.total || 0;
      var contextId = window.AppContext && window.AppContext.eventId;
      var eventId = preferredId || contextId || (state.events[0] && state.events[0].event_id);
      state.selected = eventId ? await AppCommon.api('/api/events/' + eventId) : null;
      if (isMobile() && (preferredId || contextId)) state.mobileView = 'detail';
      window.AppContext = null;
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
    if (isMobile() && state.mobileView === 'detail') requestAnimationFrame(function () { var root = scrollRoot(); if (root) root.scrollTop = 0; });
  }

  async function selectEvent(eventId) {
    try {
      var root = scrollRoot();
      if (isMobile() && root) state.mobileListScrollTop = root.scrollTop;
      state.selected = await AppCommon.api('/api/events/' + eventId);
      if (isMobile()) state.mobileView = 'detail';
      update();
      if (isMobile()) requestAnimationFrame(function () { var target = scrollRoot(); if (target) target.scrollTop = 0; });
    }
    catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function showMobileList() {
    state.mobileView = 'list';
    update();
    requestAnimationFrame(function () { var root = scrollRoot(); if (root) root.scrollTop = state.mobileListScrollTop; });
  }

  function update() {
    var root = document.getElementById('event-detail-content');
    if (root) root.innerHTML = renderContent();
    var page = document.querySelector('.event-review-page');
    if (page) page.classList.toggle('is-showing-mobile-detail', isMobile() && state.mobileView === 'detail');
  }

  function openSplit() {
    var selected = state.selected;
    if (!selected || !selected.can_split) return;
    var sources = selected.sources || [];
    var drawer = UI.openDrawer({
      title: '拆分事件来源',
      body: '<div class="review-summary"><strong>仅用于把误聚合的不同事实分开</strong><p>选择要移至新事件的来源，并填写新事件标题。原事件至少保留一条来源；不能把同一篇文章按段落拆分。拆分后两个事件均需重新审核，不会执行搜索或生成作业。</p></div>' +
        '<label class="form-field">新事件标题<input class="form-control" name="split_title" minlength="4" maxlength="160" placeholder="请概括所选来源描述的独立事实"></label>' +
        '<div class="split-source-list">' + sources.map(function (source) {
          return '<label class="split-source-option"><input type="checkbox" name="split_source" value="' + AppCommon.escapeHtml(source.source_id) + '"><span><strong>' + AppCommon.escapeHtml(source.title) + '</strong><small>' + AppCommon.escapeHtml(AppCommon.platformName(source.source_platform)) + ' · ' + AppCommon.formatTime(source.published_at, '时间不明') + '</small></span></label>';
        }).join('') + '</div><p data-split-feedback>请选择至少一条来源，原事件至少保留一条。</p>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-confirm-split disabled>确认拆分</button>'
    });
    var button = drawer.element.querySelector('[data-confirm-split]');
    var getIds = function () { return Array.from(drawer.element.querySelectorAll('[name="split_source"]:checked')).map(function (input) { return input.value; }); };
    var getTitle = function () { return drawer.element.querySelector('[name="split_title"]').value.trim(); };
    drawer.element.oninput = function () {
      var count = getIds().length;
      button.disabled = count < 1 || count >= sources.length || getTitle().length < 4;
      drawer.element.querySelector('[data-split-feedback]').textContent = '移至新事件 ' + count + ' 条，原事件保留 ' + (sources.length - count) + ' 条。' + (count === sources.length ? '不能移走全部来源。' : '');
    };
    button.onclick = async function () {
      button.disabled = true;
      try {
        var result = await AppCommon.api('/api/events/' + selected.event_id + '/split', { method: 'POST', body: JSON.stringify({ source_ids: getIds(), new_title: getTitle(), actor_id: '本地运营' }) });
        drawer.close(); await load(result.event_id);
        AppCommon.showToast('拆分完成，已打开新事件；两个事件均待审核', 'success');
      } catch (error) { drawer.element.oninput(); AppCommon.showToast(error.message, 'error'); }
    };
  }

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
        risk_summary: value('risk_summary'), recommended_action: actionPaths.length ? '生成：' + actionPaths.join('、') : '不生成作业草案',
        action_paths: actionPaths,
        boost_source_ids: actionPaths.indexOf('source_content_boost') >= 0 && boostSource ? [boostSource.value] : []
      };
      try {
        var result = await AppCommon.api('/api/events/' + state.selected.event_id + '/review', { method: 'POST', body: JSON.stringify(payload) });
        drawer.close(); state.selected = result.event;
        await load(state.selected.event_id);
        var count = (result.drafts || []).length;
        AppCommon.showToast(count ? '事件已通过并生成 ' + count + ' 份作业草案' : '事件结论已保存', 'success');
      } catch (error) { button.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  async function openEvidencePlan() {
    try {
      var plan = await AppCommon.api('/api/events/' + state.selected.event_id + '/evidence-plan', { method: 'POST', body: JSON.stringify({}) });
      var queries = plan.search_queries || [];
      var unresolved = plan.unresolved_items || [];
      var drawer = UI.openDrawer({
        title: '确认定向补证方案',
        body: '<div class="review-summary"><strong>' + AppCommon.escapeHtml(plan.question) + '</strong><p>创建方案不会产生搜索调用；只有点击“确认并开始补证”后才会执行所选工具。默认同时使用 Codex 与豆包，运营可在确认前取消不需要的工具。</p></div><div class="draft-block"><span>待解决的不确定项</span><ul>' + unresolved.map(function (item) { return '<li>' + AppCommon.escapeHtml(item) + '</li>'; }).join('') + '</ul></div><div class="draft-block"><span>搜索词与时间范围</span><ul>' + queries.map(function (item) { return '<li>' + AppCommon.escapeHtml(item) + '</li>'; }).join('') + '</ul><p>回看最近 ' + plan.lookback_hours + ' 小时</p></div><div class="check-grid"><label><input type="checkbox" name="evidence_method" value="codex_web_search" checked>Codex定向搜索与网页核验（预计' + ((plan.estimated_calls || {}).codex_web_search || queries.length) + '项）</label><label><input type="checkbox" name="evidence_method" value="doubao_global_search" checked>豆包定向搜索（计费，预计' + ((plan.estimated_calls || {}).doubao_global_search || queries.length) + '次）</label><label><input type="checkbox" name="evidence_method" value="existing_url_parse">重新解析已有证据URL（不搜索）</label></div>',
        footer: '<button class="btn" data-drawer-close>暂不执行</button><button class="btn btn-primary" data-confirm-evidence>确认并开始补证</button>'
      });
      drawer.element.querySelector('[data-confirm-evidence]').onclick = async function (event) {
        var methods = Array.from(drawer.element.querySelectorAll('[name="evidence_method"]:checked')).map(function (item) { return item.value; });
        event.currentTarget.disabled = true;
        try {
          await AppCommon.api('/api/evidence-requests/' + plan.evidence_request_id + '/confirm', { method: 'POST', body: JSON.stringify({ methods: methods, confirmed_by: '本地运营' }) });
          drawer.close(); AppCommon.showToast('定向补证已进入执行队列', 'success'); window.setTimeout(function () { selectEvent(state.selected.event_id); }, 1200);
        } catch (error) { event.currentTarget.disabled = false; AppCommon.showToast(error.message, 'error'); }
      };
    } catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = function (event) {
      var selectButton = event.target.closest('[data-select-event]');
      if (selectButton) return selectEvent(selectButton.dataset.selectEvent);
      if (event.target.closest('[data-mobile-event-back]')) return showMobileList();
      if (event.target.closest('[data-review-event]')) return openReview();
      var retryAi = event.target.closest('[data-retry-ai]');
      if (retryAi) {
        retryAi.disabled = true;
        AppCommon.api('/api/codex/work-items/' + retryAi.dataset.retryAi + '/process', { method: 'POST' }).then(function () {
          AppCommon.showToast('Codex AI研判已重新进入执行队列', 'success');
          window.setTimeout(function () { selectEvent(state.selected.event_id); }, 1500);
        }).catch(function (error) { retryAi.disabled = false; AppCommon.showToast(error.message, 'error'); });
        return;
      }
      if (event.target.closest('[data-evidence-plan]')) return openEvidencePlan();
      if (event.target.closest('[data-retry-action]')) return load();
      if (event.target.closest('[data-merge-event]')) return AppCommon.showToast('合并接口已就绪；请先在后续批量选择交互中选择至少两个事件');
      if (event.target.closest('[data-split-event]')) return openSplit();
      var pageButton = event.target.closest('[data-event-page]');
      if (pageButton) { state.page += pageButton.dataset.eventPage === 'next' ? 1 : -1; state.mobileView = 'list'; return load(); }
    };
    page.onchange = function (event) { if (event.target.matches('[data-event-status-filter]')) { state.status = event.target.value; state.page = 1; state.mobileView = 'list'; load(); } };
  }

  window.Pages['event-detail'] = { render: render, init: function () { state.mobileView = 'list'; state.mobileListScrollTop = 0; bind(); load(); } };
})();
