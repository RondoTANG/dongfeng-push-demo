(function () {
  'use strict';

  var currentPage = 'run-center';
  var icons = {
    pulse: '<svg viewBox="0 0 24 24"><path d="M3 12h4l2-5 4 10 2-5h6"/></svg>',
    search: '<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>',
    layers: '<svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></svg>',
    document: '<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></svg>',
    sliders: '<svg viewBox="0 0 24 24"><path d="M4 6h8M16 6h4M4 12h3M11 12h9M4 18h10M18 18h2"/><circle cx="14" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="16" cy="18" r="2"/></svg>',
    history: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 2.3-5.6L4 9"/><path d="M4 4v5h5M12 8v5l3 2"/></svg>'
  };

  function render(config) {
    var root = document.getElementById('main-nav');
    if (!root) return;
    root.innerHTML = config.menu.map(function (group) {
      return '<section class="nav-group"><span class="nav-group__label">' + AppCommon.escapeHtml(group.label) + '</span><ul class="nav-list">' +
        group.children.map(function (item) {
          return '<li><a class="nav-link" href="#page=' + item.key + '" data-page="' + item.key + '">' +
            '<span class="nav-icon">' + (icons[item.icon] || '') + '</span><span>' + AppCommon.escapeHtml(item.label) + '</span></a></li>';
        }).join('') + '</ul></section>';
    }).join('');
    root.addEventListener('click', function (event) {
      var link = event.target.closest('[data-page]');
      if (!link) return;
      event.preventDefault();
      App.navigate(link.dataset.page);
    });
    highlight(currentPage);
  }

  function highlight(pageKey) {
    currentPage = pageKey;
    document.querySelectorAll('.nav-link').forEach(function (link) {
      link.classList.toggle('active', link.dataset.page === pageKey);
    });
  }

  async function init() {
    try {
      var response = await fetch('/config/nav.json');
      if (!response.ok) throw new Error('HTTP ' + response.status);
      render(await response.json());
      var match = window.location.hash.match(/^#page=([a-z-]+)$/);
      highlight(match ? match[1] : 'run-center');
    } catch (error) {
      var root = document.getElementById('main-nav');
      if (root) root.innerHTML = '<div class="sidebar-foot"><span class="scope-dot"></span><div><strong>导航加载失败</strong><span>请通过本地服务打开</span></div></div>';
    }
  }

  document.addEventListener('app:navigated', function (event) { highlight(event.detail.pageKey); });
  document.addEventListener('DOMContentLoaded', init);
})();
