(function () {
  'use strict';

  var STATUS_META = {
    pending: ['待开始', 'neutral'], running: ['执行中', 'blue'], partial_success: ['部分成功', 'amber'],
    success: ['成功', 'green'], failed: ['失败', 'red'], no_result: ['无结果', 'neutral'],
    valid: ['有效线索', 'green'], invalid: ['自动无效', 'neutral'], fetch_failed: ['获取失败', 'red'],
    pending_review: ['待审核', 'amber'], needs_evidence: ['待补证', 'violet'], manual_review: ['人工研判', 'amber'],
    relevant_event_clue: ['事件事实成立', 'blue'], brand_content_opportunity: ['品牌内容机会', 'green'],
    watch: ['观察', 'neutral'], rejected: ['已驳回', 'red'], unknown: ['不可判定', 'neutral'],
    draft_pending_review: ['草案待审批', 'amber'], approved: ['已通过', 'green'],
    completed: ['已完成', 'green'], in_progress: ['处理中', 'blue'], running: ['执行中', 'blue'], cancelled: ['已取消', 'neutral'],
    pending_confirmation: ['补证方案待确认', 'violet'], plan_pending_confirmation: ['历史补证方案待确认', 'violet'], confirmed: ['已确认待执行', 'blue'],
    tracking: ['后效追踪中', 'blue'], ready_for_evaluation: ['可后效判断', 'amber'],
    boost_draft_created: ['已生成二次加热草案', 'green'], closed: ['本次追踪已结束', 'neutral'],
    growth_observed: ['观察到增长', 'green'], no_growth_observed: ['未观察到增长', 'neutral'],
    data_anomaly: ['指标异常', 'red']
  };

  async function api(path, options) {
    var config = Object.assign({ headers: {} }, options || {});
    config.headers = Object.assign({ 'Content-Type': 'application/json' }, config.headers || {});
    var response;
    try {
      response = await fetch(path, config);
    } catch (error) {
      var networkError = new Error('本地服务不可达，请确认 FastAPI 已启动');
      networkError.cause = error;
      networkError.status = 0;
      throw networkError;
    }
    var payload = null;
    var contentType = response.headers.get('content-type') || '';
    if (contentType.indexOf('application/json') >= 0) payload = await response.json();
    else payload = await response.text();
    if (!response.ok) {
      var detail = payload && payload.detail ? payload.detail : ('请求失败（HTTP ' + response.status + '）');
      if (Array.isArray(detail)) detail = detail.map(function (item) { return item.msg; }).join('；');
      if (detail && typeof detail === 'object') detail = detail.message || JSON.stringify(detail);
      var error = new Error(detail);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function formatTime(value, fallback) {
    if (!value) return fallback || '—';
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return escapeHtml(value);
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false
    }).format(date).replace(/\//g, '-');
  }

  function statusTag(status) {
    var meta = STATUS_META[status] || [status || '未定义', 'neutral'];
    return '<span class="status-tag status-' + meta[1] + '">' + escapeHtml(meta[0]) + '</span>';
  }

  function providerName(provider) {
    return ({ doubao_global_search: '豆包搜索', codex_web_search: 'Codex搜索', existing_url_parse: '已有网页解析', manual_link: '人工补充链接' })[provider] || provider || '未知来源';
  }

  function platformName(platform) {
    return ({ brand_official_website: '品牌官方网站', government_or_central_media: '政府或央媒',
      industry_media: '行业媒体', news_aggregator: '新闻聚合平台', weibo: '微博', douyin: '抖音',
      xiaohongshu: '小红书', toutiao: '今日头条', bilibili: '哔哩哔哩', kuaishou: '快手',
      wechat_official_account: '微信公众号', wechat_channels: '微信视频号',
      general_web: '公开网页', other_website: '其他网站', unknown: '待识别平台' })[platform] || '待识别平台';
  }

  function searchRecord(row) {
    return '<div class="search-query-record"><div><strong>' + escapeHtml(providerName(row.provider_id)) +
      '</strong><span>搜索时间：' + formatTime(row.retrieved_at) + '</span></div>' +
      '<small>真实搜索内容</small><p class="actual-search-query">' + escapeHtml(row.query_text || '未记录实际查询词') +
      '</p><small>配置编号：' + escapeHtml(row.query_id || '未记录') + '（不属于搜索词）</small></div>';
  }

  function renderRelationEvidence(relation) {
    var groups = [];
    (relation.relations || []).forEach(function (row) {
      var excerpt = String(row.evidence_excerpt || row.reason || '').trim();
      var normalized = excerpt.replace(/\s+/g, '');
      var group = groups.find(function (candidate) {
        var left = candidate.normalized, right = normalized;
        if (left === right) return true;
        // 同段证据因命中位置截断相差少量字，只在长前缀完全一致时归并显示。
        return Math.min(left.length, right.length) >= 100 &&
          Math.abs(left.length - right.length) <= 40 &&
          (left.startsWith(right) || right.startsWith(left));
      });
      if (!group) { group = { normalized: normalized, excerpt: excerpt, brands: [] }; groups.push(group); }
      if (normalized.length > group.normalized.length) { group.normalized = normalized; group.excerpt = excerpt; }
      var brand = row.brand_name || '待核验品牌';
      if (group.brands.indexOf(brand) < 0) group.brands.push(brand);
    });
    return '<section class="source-search-context relation-context"><h3>东风业务关联依据</h3><p class="relation-summary">' +
      escapeHtml(relation.reason || '未保存关联依据') + '</p>' + groups.map(function (group) {
        return '<article class="relation-evidence-group"><div class="tag-row"><span class="relation-label">关联品牌</span>' +
          group.brands.map(function (brand) { return '<span class="mini-tag">' + escapeHtml(brand) + '</span>'; }).join('') +
          '</div><blockquote>' + escapeHtml(group.excerpt || '未保存证据片段') + '</blockquote></article>';
      }).join('') + '</section>';
  }

  function renderTaskBrief(value) {
    var sections = [], current = { title: '', lines: [] };
    sections.push(current);
    String(value || '').split(/\r?\n/).forEach(function (line) {
      var heading = line.trim().match(/^([一二三四五六七八九十]+)[、．.]\s*(.+)$/);
      if (heading) { current = { title: heading[1] + '、' + heading[2], lines: [] }; sections.push(current); }
      else current.lines.push(line);
    });
    function bodyLine(line) {
      var trimmed = line.trim();
      if (!trimmed) return '';
      var item = trimmed.match(/^(\d+[.、]|[-•・])\s*(.*)$/);
      var text = item ? item[2] : trimmed;
      var label = text.match(/^([^：:]{1,20})[：:](.*)$/);
      var content = label ? '<strong class="brief-item-label">' + escapeHtml(label[1]) + '：</strong>' + escapeHtml(label[2]) : escapeHtml(text);
      return '<p class="brief-line' + (item ? ' brief-line--item' : '') + '">' +
        (item ? '<span class="brief-marker">' + escapeHtml(item[1]) + '</span>' : '') +
        '<span>' + content + '</span></p>';
    }
    return sections.map(function (section) {
      if (!section.title && !section.lines.some(function (line) { return line.trim(); })) return '';
      return '<section class="' + (section.title ? 'brief-section' : 'brief-intro') + '">' +
        (section.title ? '<h4>' + escapeHtml(section.title) + '</h4>' : '') +
        section.lines.map(bodyLine).join('') + '</section>';
    }).join('');
  }

  function showToast(message, type) {
    var root = document.getElementById('toast-root');
    if (!root) return;
    var toast = document.createElement('div');
    toast.className = 'toast' + (type ? ' is-' + type : '');
    toast.textContent = message;
    root.appendChild(toast);
    window.setTimeout(function () { toast.remove(); }, 3800);
  }

  window.AppCommon = {
    api: api,
    escapeHtml: escapeHtml,
    formatTime: formatTime,
    statusTag: statusTag,
    providerName: providerName,
    platformName: platformName,
    searchRecord: searchRecord,
    renderRelationEvidence: renderRelationEvidence,
    renderTaskBrief: renderTaskBrief,
    statusMeta: STATUS_META,
    showToast: showToast
  };
  window.showToast = showToast;
})();
