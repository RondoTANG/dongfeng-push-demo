(function () {
  'use strict';

  var identity = null;
  var observerStarted = false;
  var writeSelectors = [
    '[data-run-mode]', '[data-confirm-run]', '[data-aggregate-run]', '[data-config-reload]',
    '[data-toggle-automation]', '[data-add-config]', '[data-edit-config]', '[data-delete-config]', '[data-save-config]',
    '[data-merge-event]', '[data-split-event]', '[data-confirm-split]', '[data-review-event]',
    '[data-submit-event-review]', '[data-evidence-plan]', '[data-confirm-evidence]',
    '[data-edit-draft]', '[data-save-draft]', '[data-review-draft]', '[data-approve-draft]', '[data-reject-draft]',
    '[data-create-publication]', '[data-submit-publication]', '[data-add-snapshot]', '[data-submit-snapshot]',
    '[data-evaluate-publication]', '[data-submit-evaluation]'
  ].join(',');

  function permissions() { return identity && identity.permissions || {}; }
  function isAdmin() { return !!permissions().can_manage_keys; }
  function canWrite() { return !!permissions().can_write; }

  function updateIdentityUI() {
    document.body.classList.toggle('is-viewer', !!identity && !canWrite());
    var name = document.querySelector('[data-operator-name]');
    var role = document.querySelector('[data-operator-role]');
    var avatar = document.querySelector('.operator-avatar');
    if (name) name.textContent = identity ? identity.display_name : '未登录';
    if (role) role.textContent = identity && identity.role === 'admin' ? '系统管理员' : '只读查看者';
    if (avatar) avatar.textContent = identity && identity.role === 'admin' ? '管' : '访';
  }

  function enforcePermissions(root) {
    if (!root || canWrite()) return;
    root.querySelectorAll(writeSelectors).forEach(function (button) {
      button.disabled = true;
      button.classList.add('permission-disabled');
      button.title = '当前访问密钥仅允许查看';
      button.setAttribute('aria-disabled', 'true');
    });
  }

  function startPermissionObserver() {
    if (observerStarted) return;
    observerStarted = true;
    var roots = [document.getElementById('app'), document.getElementById('overlay-root')].filter(Boolean);
    roots.forEach(function (root) {
      new MutationObserver(function () { enforcePermissions(root); }).observe(root, { childList: true, subtree: true });
    });
  }

  function showShell() {
    var gate = document.getElementById('auth-gate');
    var shell = document.getElementById('app-shell');
    if (gate) { gate.innerHTML = ''; gate.hidden = true; }
    if (shell) shell.hidden = false;
    updateIdentityUI();
  }

  function renderLogin(message) {
    var gate = document.getElementById('auth-gate');
    var shell = document.getElementById('app-shell');
    if (shell) shell.hidden = true;
    gate.hidden = false;
    gate.innerHTML = '<main class="login-shell"><section class="login-panel">' +
      '<div class="login-brand"><span class="brand-mark">DF</span><div><strong>东风护卫军</strong><span>AI 热点线索与作业联动</span></div></div>' +
      '<div class="login-copy"><span>受控访问</span><h1>输入访问密钥</h1><p>管理员可管理访问密钥并执行采集与审核；访客密钥仅可查看，不会产生搜索费用或修改业务数据。</p></div>' +
      (message ? '<div class="login-error">' + AppCommon.escapeHtml(message) + '</div>' : '') +
      '<form data-login-form><label for="access-key">访问密钥</label><div class="secret-input"><input id="access-key" name="access_key" type="password" autocomplete="current-password" placeholder="ADM-… 或 VIS-…" required><button type="button" data-toggle-secret>显示</button></div>' +
      '<button class="btn btn-primary login-submit" type="submit">进入系统</button></form>' +
      '<p class="login-hint">请向系统管理员获取访问密钥。访客进入后仅可浏览，不会触发搜索或修改业务数据。</p>' +
      '</section><aside class="login-aside" aria-labelledby="poc-conclusion-title">' +
      '<div class="login-conclusion">' +
      '<span class="login-conclusion__eyebrow">阶段性验证结论</span>' +
      '<h2 id="poc-conclusion-title">当前PoC能发现公开线索，<em>但不能判断真实热点</em></h2>' +
      '<p class="login-conclusion__lead">在现有数据输入下，已验证公开搜索、业务关联、事实研判和候选作业草案链路；尚未获得平台热度与传播增长的判断依据。</p>' +
      '<div class="login-conclusion__grid">' +
      '<section class="login-conclusion__card is-verified"><span>已经验证</span><ul><li>发现近72小时公开线索，优先近24小时</li><li>识别东风业务关联、重复内容和事实风险</li><li>AI辅助形成候选原创作业草案</li></ul></section>' +
      '<section class="login-conclusion__card is-unverified"><span>尚未验证</span><ul><li>哪个平台、哪个事件正在快速发酵</li><li>哪篇文章或视频值得直接加热</li><li>原创发布后是否增长及是否需要二次加热</li></ul></section>' +
      '</div>' +
      '<div class="login-conclusion__boundary"><strong>为什么不能判热点</strong><p>当前缺少平台原生播放／阅读／互动指标、1小时／3小时／24小时连续快照及采集覆盖审计。</p></div>' +
      '<div class="login-conclusion__position"><span>当前适用定位</span><strong>公开信息线索与内容机会PoC</strong><p>输出候选传播机会，不输出“正在爆发”“全网热门”等真实热点结论。</p></div>' +
      '</div></aside></main>';
    var form = gate.querySelector('[data-login-form]');
    gate.querySelector('[data-toggle-secret]').onclick = function (event) {
      var input = gate.querySelector('#access-key');
      input.type = input.type === 'password' ? 'text' : 'password';
      event.currentTarget.textContent = input.type === 'password' ? '显示' : '隐藏';
    };
    form.onsubmit = async function (event) {
      event.preventDefault();
      var button = form.querySelector('[type="submit"]');
      button.disabled = true; button.textContent = '正在验证';
      try {
        identity = await AppCommon.api('/api/auth/login', { method: 'POST', body: JSON.stringify({ access_key: form.access_key.value.trim() }) });
        showShell(); startPermissionObserver();
        if (window.Nav) await window.Nav.init();
        if (window.App) window.App.start();
      } catch (error) { renderLogin(error.message); }
    };
  }

  async function bootstrap() {
    try {
      var status = await AppCommon.api('/api/auth/status');
      if (!status.authenticated) { renderLogin(); return false; }
      identity = status; showShell(); startPermissionObserver(); return true;
    } catch (error) { renderLogin('服务暂不可用，请确认本地服务已经启动'); return false; }
  }

  function requireLogin(message) {
    identity = null;
    updateIdentityUI();
    renderLogin(message);
  }

  async function logout() {
    try { await AppCommon.api('/api/auth/logout', { method: 'POST' }); } catch (error) {}
    identity = null; renderLogin();
  }

  window.Auth = { bootstrap: bootstrap, logout: logout, isAdmin: isAdmin, canWrite: canWrite,
    enforcePermissions: enforcePermissions, identity: function () { return identity; }, requireLogin: requireLogin };
})();
