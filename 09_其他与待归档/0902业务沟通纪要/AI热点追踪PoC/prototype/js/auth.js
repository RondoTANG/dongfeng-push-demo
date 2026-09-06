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
      '<p class="login-hint">本地首次启动的管理员密钥保存在 <code>prototype/data/admin_access.key</code>；服务器部署时由环境变量单独配置。</p>' +
      '</section><aside class="login-aside"><strong>当前运行方式</strong><p>管理员可手工运行，也可配置自动采集周期；访客浏览不会触发搜索。</p><ul><li>公开线索与热点严格区分</li><li>业务操作全部记录审计</li><li>访客无法查看访问密钥管理</li></ul></aside></main>';
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
