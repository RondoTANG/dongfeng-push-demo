(function () {
  'use strict';

  var STATUS_META = {
    pending: ['待开始', 'neutral'], running: ['执行中', 'blue'], partial_success: ['部分成功', 'amber'],
    success: ['成功', 'green'], failed: ['失败', 'red'], no_result: ['无结果', 'neutral'],
    valid: ['有效线索', 'green'], invalid: ['自动无效', 'neutral'], fetch_failed: ['获取失败', 'red'],
    pending_review: ['待审核', 'amber'], needs_evidence: ['待补证', 'violet'], manual_review: ['人工研判', 'amber'],
    relevant_event_clue: ['相关事件线索', 'blue'], brand_content_opportunity: ['品牌内容机会', 'green'],
    watch: ['观察', 'neutral'], rejected: ['已驳回', 'red'], unknown: ['不可判定', 'neutral'],
    draft_pending_review: ['草案待审批', 'amber'], approved: ['已通过', 'green'],
    completed: ['已完成', 'green'], in_progress: ['处理中', 'blue'], cancelled: ['已取消', 'neutral']
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
    statusMeta: STATUS_META,
    showToast: showToast
  };
  window.showToast = showToast;
})();
