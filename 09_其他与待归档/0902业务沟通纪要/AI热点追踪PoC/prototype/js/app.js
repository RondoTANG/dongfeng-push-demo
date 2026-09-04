(function () {
  'use strict';

  var pages = window.Pages = window.Pages || {};
  var PAGE_META = {
    'run-center': ['运行中心', '查看采集批次、查询覆盖和处理状态'],
    clues: ['信息线索工作台', '处理公开来源、有效线索和事件关联'],
    'event-detail': ['事件审核', '核验证据、存疑原因和事件结论'],
    drafts: ['作业草案与审批', '处理原创增长、原创发布后追加加热与热点关联内容直接加热草案'],
    effects: ['原创后效追踪', '主闭环：回收原创链接与指标快照，判断是否需要追加加热'],
    config: ['配置管理', '查看品牌、查询、来源和处理规则'],
    audit: ['无效与审计记录', '追溯自动过滤、人工审核和配置操作']
  };

  Object.keys(PAGE_META).forEach(function (key) {
    if (!pages[key]) {
      pages[key] = {
        render: function () { return Layout.placeholder(PAGE_META[key][0], PAGE_META[key][1]); },
        init: function () {}
      };
    }
  });

  function pageFromHash() {
    var match = window.location.hash.match(/^#page=([a-z-]+)$/);
    return match && PAGE_META[match[1]] ? match[1] : 'run-center';
  }

  function renderPage(pageKey, options) {
    var page = pages[pageKey] || pages['run-center'];
    var app = document.getElementById('app');
    if (!app) return;
    app.innerHTML = page.render();
    if (typeof page.init === 'function') page.init(options || {});
    var meta = PAGE_META[pageKey] || PAGE_META['run-center'];
    var breadcrumb = document.getElementById('breadcrumbs');
    if (breadcrumb) breadcrumb.innerHTML = '<span>AI 热点线索</span><i>／</i><strong>' + AppCommon.escapeHtml(meta[0]) + '</strong>';
    document.title = meta[0] + '｜东风护卫军';
    document.dispatchEvent(new CustomEvent('app:navigated', { detail: { pageKey: pageKey } }));
  }

  function navigate(pageKey, options) {
    if (!PAGE_META[pageKey]) pageKey = 'run-center';
    if (!(options && options.keepHash)) window.history.pushState({ pageKey: pageKey }, '', '#page=' + pageKey);
    renderPage(pageKey, options);
  }

  async function checkService() {
    var element = document.getElementById('service-status');
    if (!element) return;
    try {
      await AppCommon.api('/api/health');
      element.className = 'service-status is-online';
      element.querySelector('.service-status__text').textContent = '本地服务正常';
    } catch (error) {
      element.className = 'service-status is-offline';
      element.querySelector('.service-status__text').textContent = '本地服务未连接';
    }
  }

  window.App = { navigate: navigate, renderPage: renderPage, pageMeta: PAGE_META, checkService: checkService };
  window.addEventListener('popstate', function () { renderPage(pageFromHash()); });
  document.addEventListener('DOMContentLoaded', function () { checkService(); renderPage(pageFromHash(), { keepHash: true }); });
})();
