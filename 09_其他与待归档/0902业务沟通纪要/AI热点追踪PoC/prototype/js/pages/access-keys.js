(function () {
  'use strict';
  var state = { items: [], loading: true, error: null };

  function status(row) {
    var label = { active: '生效中', revoked: '已停用', expired: '已过期' }[row.status] || row.status;
    var tone = row.status === 'active' ? 'green' : 'neutral';
    return '<span class="status-tag status-' + tone + '">' + label + '</span>';
  }

  function renderContent() {
    if (state.loading) return '<div class="page-loading"><span class="spinner"></span>正在读取访问密钥</div>';
    if (state.error) return UI.errorState(state.error, true);
    return '<div class="access-key-summary"><div><strong>管理员密钥</strong><span>由服务器环境变量或本机受保护文件提供，不在页面显示。</span></div><div><strong>访客密钥</strong><span>仅可查看业务数据，不能采集、审核、编辑，也看不到本页面。</span></div></div>' +
      '<section class="card table-card"><div class="card-header"><div><h2>已生成的访客密钥</h2><span>列表默认隐藏完整密钥；管理员可再次验证身份后查看和复制</span></div></div>' +
      DataTable.render([
        { label: '用途名称', render: function (row) { return '<div class="cell-title">' + AppCommon.escapeHtml(row.label) + '</div><div class="cell-sub mono">' + AppCommon.escapeHtml(row.access_key_id) + '</div>'; } },
        { label: '密钥标识', width: '120px', render: function (row) { return '<span class="mono">VIS-••••' + AppCommon.escapeHtml(row.key_suffix) + '</span>'; } },
        { label: '有效期', width: '160px', render: function (row) { return row.expires_at ? AppCommon.formatTime(row.expires_at) : '长期有效'; } },
        { label: '最近使用', width: '160px', render: function (row) { return AppCommon.formatTime(row.last_used_at, '尚未使用'); } },
        { label: '状态', width: '90px', render: status },
        { label: '操作', width: '150px', render: function (row) {
          var reveal = row.can_reveal ? '<button class="btn btn-text btn-sm" data-reveal-key="' + row.access_key_id + '">查看／复制</button>' : '<span class="cell-sub" title="旧版密钥未保存可恢复密文">不可查看</span>';
          var revoke = row.status === 'active' ? '<button class="btn btn-text btn-sm text-danger" data-revoke-key="' + row.access_key_id + '">停用</button>' : '';
          return '<div class="inline-actions">' + reveal + revoke + '</div>';
        } }
      ], state.items, { emptyTitle: '还没有访客密钥', emptyText: '生成后可将密钥单独发送给需要查看原型的人' }) + '</section>';
  }

  function render() {
    var actions = '<button class="btn btn-primary" data-create-access-key>生成访客密钥</button>';
    return '<section class="page">' + Layout.pageHead('访问密钥管理', '控制谁可以进入系统；访客只读，管理员保留业务操作权', actions) +
      '<div class="boundary-banner access-security-banner"><strong>权限隔离</strong><span>隐藏菜单只是界面表现，服务端同时校验角色；停用密钥后，其现有登录会话立即失效。</span></div>' +
      '<div id="access-keys-content">' + renderContent() + '</div></section>';
  }

  function update() { var root = document.getElementById('access-keys-content'); if (root) root.innerHTML = renderContent(); }
  async function load() {
    state.loading = true; state.error = null; update();
    try { state.items = (await AppCommon.api('/api/access-keys')).items || []; }
    catch (error) { state.error = error.message; }
    state.loading = false; update();
  }

  function createKey() {
    var drawer = UI.openDrawer({ title: '生成访客密钥', body: '<div class="review-form"><div class="form-field full"><label>用途名称</label><input class="form-control" name="key_label" placeholder="例如：业务评审组" maxlength="80"></div><div class="form-field full"><label>有效期</label><select class="form-control" name="expires_days"><option value="7">7天</option><option value="30" selected>30天</option><option value="90">90天</option><option value="365">1年</option></select></div><div class="scope-notice">该密钥只能查看页面和数据，不能触发豆包搜索、审核事件或修改草案。</div></div>', footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-confirm-create-key>生成密钥</button>' });
    drawer.element.querySelector('[data-confirm-create-key]').onclick = async function (event) {
      var label = drawer.element.querySelector('[name="key_label"]').value.trim();
      if (label.length < 2) return AppCommon.showToast('请填写至少2个字的用途名称', 'error');
      event.currentTarget.disabled = true;
      try {
        var result = await AppCommon.api('/api/access-keys', { method: 'POST', body: JSON.stringify({ label: label, expires_in_days: Number(drawer.element.querySelector('[name="expires_days"]').value) }) });
        drawer.element.querySelector('.drawer__body').innerHTML = '<div class="generated-key"><span>现在可直接复制；以后也可在管理页再次验证管理员密钥后查看</span><code>' + AppCommon.escapeHtml(result.access_key) + '</code><button class="btn" data-copy-generated-key>复制访问密钥</button><p>用途：' + AppCommon.escapeHtml(result.label) + '；到期时间：' + AppCommon.formatTime(result.expires_at) + '</p></div>';
        drawer.element.querySelector('.drawer__footer').innerHTML = '<button class="btn btn-primary" data-drawer-close>完成</button>';
        drawer.element.querySelector('[data-copy-generated-key]').onclick = async function () { await navigator.clipboard.writeText(result.access_key); AppCommon.showToast('访问密钥已复制', 'success'); };
        await load();
      } catch (error) { event.currentTarget.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
  }

  function revealKey(id) {
    var row = state.items.find(function (item) { return item.access_key_id === id; });
    var drawer = UI.openDrawer({
      title: '查看访客密钥',
      body: '<div class="review-form"><div class="review-summary"><strong>需要再次验证管理员身份</strong><p>完整密钥只会在本次验证后的页面中显示，查看动作会写入审计记录。访客无法使用此接口。</p></div><div class="form-field full"><label>管理员密钥</label><div class="secret-input"><input type="password" name="admin_key" autocomplete="current-password" placeholder="输入当前管理员密钥"><button type="button" data-toggle-reveal-secret>显示</button></div></div><div class="scope-notice">用途：' + AppCommon.escapeHtml(row ? row.label : id) + '</div></div>',
      footer: '<button class="btn" data-drawer-close>取消</button><button class="btn btn-primary" data-confirm-reveal-key>验证并查看</button>'
    });
    var input = drawer.element.querySelector('[name="admin_key"]');
    drawer.element.querySelector('[data-toggle-reveal-secret]').onclick = function (event) {
      var show = input.type === 'password'; input.type = show ? 'text' : 'password'; event.currentTarget.textContent = show ? '隐藏' : '显示';
    };
    drawer.element.querySelector('[data-confirm-reveal-key]').onclick = async function (event) {
      if (!input.value.trim()) return AppCommon.showToast('请输入管理员密钥', 'error');
      event.currentTarget.disabled = true;
      try {
        var result = await AppCommon.api('/api/access-keys/' + id + '/reveal', { method: 'POST', body: JSON.stringify({ admin_key: input.value.trim() }) });
        drawer.element.querySelector('.drawer__body').innerHTML = '<div class="generated-key"><span>管理员身份已验证</span><code>' + AppCommon.escapeHtml(result.access_key) + '</code><button class="btn" data-copy-revealed-key>复制访问密钥</button><p>用途：' + AppCommon.escapeHtml(result.label) + '；状态：' + AppCommon.escapeHtml(status(result).replace(/<[^>]+>/g, '')) + '</p></div>';
        drawer.element.querySelector('.drawer__footer').innerHTML = '<button class="btn btn-primary" data-drawer-close>关闭</button>';
        drawer.element.querySelector('[data-copy-revealed-key]').onclick = async function () { await navigator.clipboard.writeText(result.access_key); AppCommon.showToast('访问密钥已复制', 'success'); };
      } catch (error) { event.currentTarget.disabled = false; AppCommon.showToast(error.message, 'error'); }
    };
    input.focus();
  }

  async function revoke(id) {
    if (!window.confirm('停用后，使用该密钥的现有会话会立即退出。确认停用？')) return;
    try { await AppCommon.api('/api/access-keys/' + id + '/revoke', { method: 'POST' }); await load(); AppCommon.showToast('访问密钥已停用', 'success'); }
    catch (error) { AppCommon.showToast(error.message, 'error'); }
  }

  function bind() {
    document.getElementById('app').onclick = function (event) {
      if (event.target.closest('[data-create-access-key]')) return createKey();
      var revealButton = event.target.closest('[data-reveal-key]'); if (revealButton) return revealKey(revealButton.dataset.revealKey);
      var button = event.target.closest('[data-revoke-key]'); if (button) return revoke(button.dataset.revokeKey);
      if (event.target.closest('[data-retry-action]')) return load();
    };
  }
  window.Pages['access-keys'] = { render: render, init: function () { bind(); load(); } };
})();
