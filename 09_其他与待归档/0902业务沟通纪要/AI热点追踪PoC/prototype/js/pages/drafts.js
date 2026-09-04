(function () {
  'use strict';

  var state = { drafts: [], selected: null, loading: true, error: null, status: '', purpose: '', page: 1, pageSize: 20, total: 0 };
  var platformNames = { weibo: '微博', douyin: '抖音', wechat_official_account: '公众号', wechat_channels: '视频号', toutiao: '今日头条', xiaohongshu: '小红书', bilibili: 'B站', autohome: '汽车之家', dongchedi: '懂车帝' };
  var purposeNames = { original_growth: '原创增长', original_post_boost: '原创发布后追加加热', source_content_boost: '热点关联内容直接加热' };
  var actionNames = { like: '点赞', positive_comment: '正向评论', repost: '转发', favorite: '收藏' };
  var actionsByPlatform = {
    weibo: ['like', 'positive_comment', 'repost'], douyin: ['like', 'positive_comment'],
    wechat_official_account: ['like', 'positive_comment'], wechat_channels: ['like', 'positive_comment'],
    toutiao: ['like', 'positive_comment'], xiaohongshu: ['like', 'favorite', 'positive_comment'],
    bilibili: ['like', 'positive_comment'], autohome: ['like', 'positive_comment'], dongchedi: ['like', 'positive_comment']
  };

  function renderList() {
    var items = state.drafts.filter(function (item) {
      return (!state.status || item.task_status === state.status) && (!state.purpose || item.draft_purpose === state.purpose);
    });
    return '<aside class="draft-list"><div class="event-queue__head draft-queue-head"><strong>作业草案</strong><select class="form-control" data-draft-purpose-filter><option value="">全部方向</option><option value="original_growth">原创增长</option><option value="original_post_boost">原创发布后追加加热</option><option value="source_content_boost">热点关联内容直接加热</option></select><select class="form-control" data-draft-status-filter><option value="">全部状态</option><option value="draft_pending_review">待审批</option><option value="approved">已通过</option><option value="rejected">已驳回</option></select></div><div class="event-queue__list">' +
      (items.length ? items.map(function (draft) { return '<button class="draft-list__item' + (state.selected && state.selected.task_draft_id === draft.task_draft_id ? ' is-active' : '') + '" data-select-draft="' + draft.task_draft_id + '"><span class="event-queue__title">' + AppCommon.escapeHtml(draft.task_title) + '</span><span class="event-queue__meta"><span class="draft-purpose">' + AppCommon.escapeHtml(purposeNames[draft.draft_purpose] || draft.draft_purpose) + '</span>' + AppCommon.statusTag(draft.task_status) + '</span><span class="event-queue__heat">' + AppCommon.escapeHtml((draft.recommended_platforms || []).map(function (item) { return platformNames[item] || item; }).join('、') || '平台待运营确认') + '</span></button>'; }).join('') : '<div class="empty-state compact"><span>当前筛选下暂无草案</span></div>') + '</div>' + DataTable.pagination(state.page, state.pageSize, state.total, 'data-draft-page') + '</aside>';
  }

  function listBlock(title, items, emptyText) {
    return '<div class="draft-block"><span>' + AppCommon.escapeHtml(title) + '</span>' + ((items || []).length ? '<ul>' + items.map(function (item) { return '<li>' + AppCommon.escapeHtml(item) + '</li>'; }).join('') + '</ul>' : '<p class="text-muted">' + AppCommon.escapeHtml(emptyText) + '</p>') + '</div>';
  }

  function renderDetail() {
    var draft = state.selected;
    if (!draft) return '<section class="draft-detail"><div class="empty-state"><strong>暂无作业草案</strong><span>事件审核通过后，系统将在这里生成可编辑草案</span></div></section>';
    var canEdit = draft.task_status === 'draft_pending_review';
    var event = draft.event || {};
    var isBoost = draft.draft_purpose === 'source_content_boost' || draft.draft_purpose === 'original_post_boost';
    var targetLabel = draft.draft_purpose === 'original_post_boost' ? '已发布原创内容' : '热点源文章／视频';
    var targetContent = isBoost ? '<div class="target-content"><span>' + targetLabel + '</span><strong>' + AppCommon.escapeHtml(draft.target_content_title || '未命名内容') + '</strong><a href="' + AppCommon.escapeHtml(draft.target_url || '#') + '" target="_blank" rel="noopener">' + AppCommon.escapeHtml(draft.target_url || '缺少目标链接') + '</a></div>' : '';
    return '<section class="draft-detail" data-anno="draft-approval-workbench"><header class="event-detail-head"><div><div class="event-kicker"><span class="mono">' + draft.task_draft_id + '</span><span class="draft-purpose">' + AppCommon.escapeHtml(purposeNames[draft.draft_purpose] || draft.draft_purpose) + '</span>' + AppCommon.statusTag(draft.task_status) + '</div><h2>' + AppCommon.escapeHtml(draft.task_title) + '</h2><div class="tag-row">' + (draft.recommended_platforms || []).map(function (item) { return '<span class="mini-tag">' + AppCommon.escapeHtml(platformNames[item] || item) + '</span>'; }).join('') + '</div></div><div class="page-head__actions">' + (canEdit ? '<button class="btn" data-edit-draft>编辑草案</button><button class="btn btn-primary" data-review-draft>审批草案</button>' : '') + '</div></header>' +
      '<div class="draft-scope"><strong>草案通过 ≠ 自动执行</strong><span>原创增长通过后可登记实际发布链接并进入后效追踪；任何加热草案仍需单独审批，系统不自动执行点赞或评论。</span></div>' +
      '<div class="draft-content"><section>' + targetContent + '<h3>任务简述</h3><div class="draft-brief">' + AppCommon.escapeHtml(draft.task_brief).replace(/\n/g, '<br>') + '</div><h3>事件依据</h3><div class="event-reference"><strong>' + AppCommon.escapeHtml(event.event_title || draft.event_id) + '</strong><span>热点状态：不可判定</span><button class="btn btn-text btn-sm" data-open-draft-event="' + draft.event_id + '">查看事件证据</button></div></section><aside>' +
      (isBoost ? listBlock('互动动作', (draft.engagement_actions || []).map(function (item) { return actionNames[item] || item; }), '待运营选择') : '') +
      listBlock('目标成员标签', draft.target_member_tags, '待运营选择') +
      listBlock('证据来源', draft.evidence_source_ids, '缺少证据') +
      listBlock('禁用表述', draft.prohibited_claims, '暂无明确项，仍需审核') +
      listBlock('风险提示', draft.risk_notes, '暂无明确项，仍需审核') +
      '</aside></div>' +
      (draft.reviewed_at ? '<div class="approval-record"><span>审批记录</span><strong>' + AppCommon.escapeHtml(draft.reviewer || '—') + ' · ' + AppCommon.formatTime(draft.reviewed_at) + '</strong><p>' + AppCommon.escapeHtml(draft.review_note || '未填写备注') + '</p></div>' : '') + '</section>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在加载作业草案</div>';
    if (state.error) return UI.errorState(state.error, true);
    return '<div class="draft-workspace">' + renderList() + renderDetail() + '</div>';
  }

  function render() {
    return '<section class="page page-wide">' + Layout.pageHead('作业草案与审批', '先管理原创增长及其发布后追加加热主链；热点关联内容直接加热作为补充支路') + '<div id="drafts-content">' + renderContent() + '</div></section>';
  }

  async function load(preferredId) {
    state.loading = true; state.error = null; update();
    try {
      var params = new URLSearchParams({ page: state.page, page_size: state.pageSize });
      if (state.status) params.set('status', state.status); if (state.purpose) params.set('purpose', state.purpose);
      var result = await AppCommon.api('/api/drafts?' + params.toString()); state.drafts = result.items; state.total = result.total || 0;
      var draftId = preferredId || (window.AppContext && window.AppContext.draftId) || (state.drafts[0] && state.drafts[0].task_draft_id);
      state.selected = draftId ? await AppCommon.api('/api/drafts/' + draftId) : null;
      window.AppContext = null;
    } catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  async function selectDraft(id) { try { state.selected = await AppCommon.api('/api/drafts/' + id); update(); } catch (error) { AppCommon.showToast(error.message, 'error'); } }
  function update() { var root = document.getElementById('drafts-content'); if (root) root.innerHTML = renderContent(); }

  function openEdit() {
    var draft = state.selected;
    var platforms = draft.recommended_platforms || [];
    var isBoost = draft.draft_purpose === 'source_content_boost' || draft.draft_purpose === 'original_post_boost';
    var allowedActionKeys = isBoost ? Array.from(new Set(platforms.reduce(function (result, platform) { return result.concat(actionsByPlatform[platform] || []); }, []))) : [];
    var actionEditor = isBoost ? '<div class="form-field full"><label>互动动作</label><div class="check-grid">' + allowedActionKeys.map(function (key) { return '<label><input type="checkbox" name="engagement_action" value="' + key + '"' + ((draft.engagement_actions || []).indexOf(key) >= 0 ? ' checked' : '') + '>' + actionNames[key] + '</label>'; }).join('') + '</div><small class="field-help">仅展示目标平台支持的动作，至少保留一项。</small></div>' : '';
    var drawer = UI.openDrawer({
      title: '编辑作业草案',
      body: '<div class="review-form"><div class="form-field full"><label>作业方向</label><div class="review-summary"><strong>' + AppCommon.escapeHtml(purposeNames[draft.draft_purpose] || draft.draft_purpose) + '</strong><p>' + (isBoost ? '加热目标已在事件审核或原创后效判断中确定，编辑时不可替换；如需更换目标，请回到对应业务环节重新生成。' : '围绕事件形成原创表达，不直接复制来源内容。') + '</p></div></div><div class="form-field full"><label>作业标题</label><input class="form-control" name="task_title" value="' + AppCommon.escapeHtml(draft.task_title) + '"></div><div class="form-field full"><label>任务简述</label><textarea class="form-control tall" name="task_brief">' + AppCommon.escapeHtml(draft.task_brief) + '</textarea></div>' + actionEditor + '<div class="form-field full"><label>建议平台</label><div class="check-grid">' + Object.keys(platformNames).map(function (key) { return '<label><input type="checkbox" name="platform" value="' + key + '"' + (platforms.indexOf(key) >= 0 ? ' checked' : '') + (isBoost ? ' disabled' : '') + '>' + platformNames[key] + '</label>'; }).join('') + '</div></div><div class="form-field full"><label>目标成员标签（顿号分隔）</label><input class="form-control" name="target_tags" value="' + AppCommon.escapeHtml((draft.target_member_tags || []).join('、')) + '"></div></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-save-draft>保存修改</button>'
    });
    drawer.element.querySelector('[data-save-draft]').onclick = async function (event) {
      var button = event.currentTarget; button.disabled = true;
      var platformsValue = Array.from(drawer.element.querySelectorAll('[name="platform"]:checked')).map(function (item) { return item.value; });
      var payload = {
        actor_id: '本地运营', task_title: drawer.element.querySelector('[name="task_title"]').value.trim(),
        task_brief: drawer.element.querySelector('[name="task_brief"]').value.trim(), recommended_platforms: isBoost ? platforms : platformsValue,
        target_member_tags: drawer.element.querySelector('[name="target_tags"]').value.split(/[、,，]/).map(function (item) { return item.trim(); }).filter(Boolean)
      };
      if (isBoost) payload.engagement_actions = Array.from(drawer.element.querySelectorAll('[name="engagement_action"]:checked')).map(function (item) { return item.value; });
      try { state.selected = await AppCommon.api('/api/drafts/' + draft.task_draft_id, { method: 'PATCH', body: JSON.stringify(payload) }); drawer.close(); await load(draft.task_draft_id); AppCommon.showToast('草案修改已保存', 'success'); }
      catch (error) { button.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  function openReview() {
    var draft = state.selected;
    var drawer = ReviewDrawer.draftReview(draft);
    async function submit(result) {
      var note = drawer.element.querySelector('[name="draft_review_note"]').value.trim();
      try { state.selected = await AppCommon.api('/api/drafts/' + draft.task_draft_id + '/review', { method: 'POST', body: JSON.stringify({ review_result: result, reviewer: '本地运营', review_note: note || null }) }); drawer.close(); await load(draft.task_draft_id); AppCommon.showToast(result === 'approved' ? '草案已通过，未执行正式下发' : '草案已驳回', 'success'); }
      catch (error) { AppCommon.showToast(error.message, 'error'); }
    }
    drawer.element.querySelector('[data-approve-draft]').onclick = function () { submit('approved'); };
    drawer.element.querySelector('[data-reject-draft]').onclick = function () { submit('rejected'); };
  }

  function bind() {
    var page = document.getElementById('app');
    page.onclick = function (event) {
      var selectButton = event.target.closest('[data-select-draft]'); if (selectButton) return selectDraft(selectButton.dataset.selectDraft);
      if (event.target.closest('[data-edit-draft]')) return openEdit();
      if (event.target.closest('[data-review-draft]')) return openReview();
      if (event.target.closest('[data-retry-action]')) return load();
      var eventButton = event.target.closest('[data-open-draft-event]'); if (eventButton) { window.AppContext = { eventId: eventButton.dataset.openDraftEvent }; App.navigate('event-detail'); }
      var pageButton = event.target.closest('[data-draft-page]'); if (pageButton) { state.page += pageButton.dataset.draftPage === 'next' ? 1 : -1; return load(); }
    };
    page.onchange = function (event) {
      if (event.target.matches('[data-draft-status-filter]')) { state.status = event.target.value; state.page = 1; load(); }
      if (event.target.matches('[data-draft-purpose-filter]')) { state.purpose = event.target.value; state.page = 1; load(); }
    };
  }

  window.Pages.drafts = { render: render, init: function () { bind(); load(); } };
})();
