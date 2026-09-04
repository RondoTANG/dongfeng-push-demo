(function () {
  'use strict';

  function openDrawer(options) {
    var root = document.getElementById('overlay-root');
    if (!root) return null;
    root.innerHTML = '<div class="drawer-mask" role="presentation"><section class="drawer" role="dialog" aria-modal="true">' +
      '<header class="drawer__header"><strong>' + AppCommon.escapeHtml(options.title || '详情') + '</strong><button class="btn btn-sm" data-drawer-close>关闭</button></header>' +
      '<div class="drawer__body">' + (options.body || '') + '</div>' +
      '<footer class="drawer__footer">' + (options.footer || '') + '</footer></section></div>';
    var mask = root.querySelector('.drawer-mask');
    requestAnimationFrame(function () { mask.classList.add('is-open'); });
    function close() {
      mask.classList.remove('is-open');
      window.setTimeout(function () { root.innerHTML = ''; }, 180);
    }
    mask.addEventListener('click', function (event) { if (event.target === mask || event.target.closest('[data-drawer-close]')) close(); });
    return { element: mask, close: close };
  }

  function errorState(message, retryAction) {
    return '<div class="error-state"><strong>页面数据加载失败</strong><span>' + AppCommon.escapeHtml(message) + '</span>' +
      (retryAction ? '<button class="btn" data-retry-action>重新加载</button>' : '') + '</div>';
  }

  window.UI = { openDrawer: openDrawer, errorState: errorState };
})();
