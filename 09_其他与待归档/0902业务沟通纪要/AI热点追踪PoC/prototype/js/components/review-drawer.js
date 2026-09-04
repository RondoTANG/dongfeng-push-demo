(function () {
  'use strict';

  function sourcePlatform(source) {
    var platform = source.source_platform;
    var direct = ['weibo','douyin','wechat_official_account','wechat_channels','toutiao','xiaohongshu','bilibili','autohome','dongchedi'];
    if (direct.indexOf(platform) >= 0) return platform;
    var site = source.source_site_name || '';
    var domain = source.domain || '';
    if (site.indexOf('今日头条') >= 0 || domain.indexOf('toutiao.com') >= 0) return 'toutiao';
    if (site.indexOf('汽车之家') >= 0 || domain.indexOf('autohome.com') >= 0) return 'autohome';
    if (site.indexOf('懂车帝') >= 0 || domain.indexOf('dongchedi.com') >= 0) return 'dongchedi';
    if (site.indexOf('小红书') >= 0 || domain.indexOf('xiaohongshu.com') >= 0) return 'xiaohongshu';
    if (site.indexOf('哔哩哔哩') >= 0 || domain.indexOf('bilibili.com') >= 0) return 'bilibili';
    return '';
  }

  function eventReview(event) {
    var current = ['relevant_event_clue', 'brand_content_opportunity', 'manual_review', 'watch'].indexOf(event.event_status) >= 0 ? event.event_status : 'relevant_event_clue';
    var boostableSources = (event.sources || []).filter(function (source) { return sourcePlatform(source); });
    var sourceOptions = boostableSources.length ? boostableSources.map(function (source, index) {
      return '<label class="source-choice"><input type="radio" name="boost_source_id" value="' + source.source_id + '"' + (index === 0 ? ' checked' : '') + '><span><strong>' + AppCommon.escapeHtml(source.title || source.source_id) + '</strong><small>' + AppCommon.escapeHtml(source.source_site_name || sourcePlatform(source)) + ' · ' + AppCommon.escapeHtml(source.original_url || source.canonical_url || '') + '</small></span></label>';
    }).join('') : '<p class="text-muted">当前事件没有识别到可直接执行点赞／评论的文章或视频来源。官网、普通网页或平台不明链接不能生成加热草案。</p>';
    var drawer = UI.openDrawer({
      title: '事件结论审核',
      body: '<div class="review-form" data-event-review-form>' +
        '<div class="form-field"><label>审核结果</label><select class="form-control" name="review_result"><option value="approved">通过</option><option value="approved_after_edit">修改后通过</option><option value="rejected">驳回</option></select></div>' +
        '<div class="form-field"><label>事件结论</label><select class="form-control" name="event_status">' +
          [['relevant_event_clue','相关事件线索'],['brand_content_opportunity','品牌内容机会'],['manual_review','继续人工研判'],['watch','进入观察']].map(function (item) { return '<option value="' + item[0] + '"' + (current === item[0] ? ' selected' : '') + '>' + item[1] + '</option>'; }).join('') + '</select></div>' +
        '<div class="form-field full"><label>证据与判断依据</label><textarea class="form-control" name="evidence_summary">' + AppCommon.escapeHtml(event.decision_reason || '公开来源可以支持事件事实，但不能证明平台真实热度。') + '</textarea></div>' +
        '<div class="form-field full"><label>风险说明</label><textarea class="form-control" name="risk_summary">' + AppCommon.escapeHtml((event.risk_tags || []).length ? '存在风险标签：' + event.risk_tags.join('、') : '未发现需要阻断草案生成的明确风险，仍需遵守证据边界。') + '</textarea></div>' +
        '<div class="form-field full"><label>本次行动方向</label><div class="action-paths"><label><input type="checkbox" name="action_path" value="original_growth" checked><span><strong>原创增长</strong><small>围绕事件生成原创评论或内容作业草案</small></span></label><label class="' + (boostableSources.length ? '' : 'is-disabled') + '"><input type="checkbox" name="action_path" value="source_content_boost"' + (boostableSources.length ? '' : ' disabled') + '><span><strong>热点源内容加热</strong><small>直接对事件中的目标文章／视频组织点赞、正向评论等作业</small></span></label></div></div>' +
        '<div class="form-field full" data-boost-source-field><label>加热目标内容</label><div class="source-choice-list">' + sourceOptions + '</div></div>' +
        '<div class="form-field full"><label>建议动作</label><textarea class="form-control" name="recommended_action">分别判断是否生成原创增长草案，以及是否对热点源文章或视频生成加热草案。</textarea></div>' +
        '<div class="form-field full"><label>审核备注</label><textarea class="form-control" name="review_note" placeholder="驳回时必填"></textarea></div>' +
        '</div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-submit-event-review>提交审核</button>'
    });
    var boostToggle = drawer.element.querySelector('[name="action_path"][value="source_content_boost"]');
    var boostField = drawer.element.querySelector('[data-boost-source-field]');
    var syncBoostField = function () {
      if (boostField) boostField.classList.toggle('is-hidden', !boostToggle || !boostToggle.checked);
    };
    if (boostToggle) boostToggle.addEventListener('change', syncBoostField);
    syncBoostField();
    return drawer;
  }

  function draftReview(draft) {
    return UI.openDrawer({
      title: '草案审批',
      body: '<div class="review-summary"><strong>' + AppCommon.escapeHtml(draft.task_title) + '</strong><p>审批通过后仅记录为已确认草案，不会自动下发到护卫军系统。</p></div>' +
        '<div class="form-field"><label>审批备注</label><textarea class="form-control" name="draft_review_note" placeholder="说明修改意见或通过依据"></textarea></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn" data-reject-draft>驳回</button><button class="btn btn-primary" data-approve-draft>通过草案</button>'
    });
  }

  window.ReviewDrawer = { eventReview: eventReview, draftReview: draftReview };
})();
