(function () {
  'use strict';

  function pageHead(title, description, actions) {
    return '<div class="page-head">' +
      '<div><h1 class="page-head__title">' + AppCommon.escapeHtml(title) + '</h1>' +
      '<p class="page-head__desc">' + AppCommon.escapeHtml(description || '') + '</p></div>' +
      '<div class="page-head__actions">' + (actions || '') + '</div></div>';
  }

  function placeholder(title, description) {
    return '<section class="page">' + pageHead(title, description) +
      '<div class="placeholder-grid">' +
      '<div class="card placeholder-panel"><h2>页面数据正在接入</h2><p>该页面将从本地 FastAPI 读取真实运行数据。</p>' +
      '<div class="scope-notice">本期同时支持原创增长草案与热点源内容加热草案，流程止于人工审批，不包含正式下发、任务执行与结果回流。</div></div>' +
      '<div class="card placeholder-panel"><h2>当前数据边界</h2><p>公开搜索用于发现线索；没有平台原生指标和连续快照时，热点结论为不可判定。</p></div>' +
      '</div></section>';
  }

  window.Layout = { pageHead: pageHead, placeholder: placeholder };
})();
