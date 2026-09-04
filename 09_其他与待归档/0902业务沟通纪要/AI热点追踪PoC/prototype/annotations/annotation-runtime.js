(function () {
  'use strict';

  var visible = true;
  var activePopup = null;
  var currentAnno = null;
  var dragState = null;
  var markerDragState = null;
  var observer = null;

  var sectionFields = [
    ['functionName', '功能名称'],
    ['functionDesc', '功能说明'],
    ['permissionScope', '权限范围'],
    ['dataSource', '数据来源'],
    ['valueLogic', '取值逻辑'],
    ['fieldDesc', '字段说明'],
    ['interactionDesc', '交互说明'],
    ['judgeRule', '判断规则'],
    ['exceptionRule', '异常规则'],
    ['otherDesc', '其他说明']
  ];

  function getConfig() {
    return window.AnnotationConfig || {};
  }

  function getPageKey() {
    var cfg = getConfig();
    if (typeof cfg.page === 'function') return cfg.page();
    if (cfg.page) return cfg.page;
    var active = document.querySelector('.nav-sub-item.active');
    return active && active.id ? active.id : 'index';
  }

  function getRawAnnotations() {
    var cfg = getConfig();
    var page = getPageKey();
    if (cfg.dataKey && Array.isArray(window[cfg.dataKey])) {
      return window[cfg.dataKey].filter(function (item) { return item.page === page; });
    }
    if (window.AnnotationData && Array.isArray(window.AnnotationData[page])) {
      return window.AnnotationData[page];
    }
    return [];
  }

  function storageKey() {
    var cfg = getConfig();
    var projectId = cfg.projectId || window.location.pathname || 'default-project';
    var dataVersion = cfg.dataVersion || '1';
    return ['prototype_annotations', projectId, dataVersion, getPageKey()].join('_');
  }

  function loadCached() {
    try {
      var raw = window.localStorage.getItem(storageKey());
      return raw ? JSON.parse(raw) : [];
    } catch (err) {
      return [];
    }
  }

  function saveCached(items) {
    try {
      window.localStorage.setItem(storageKey(), JSON.stringify(items));
    } catch (err) {
      showToast('保存到浏览器缓存失败');
    }
  }

  function getAnnotations() {
    var source = getRawAnnotations();
    if (!source.length) return [];
    var cached = loadCached();
    var cachedMap = {};
    cached.forEach(function (item) {
      if (item && item.id != null) cachedMap[item.id] = item;
    });
    return source.map(function (item) {
      return clone(cachedMap[item.id] || item);
    }).sort(function (a, b) {
      return Number(a.id) - Number(b.id);
    });
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value || {}));
  }

  function ensureToggle() {
    var buttons = document.querySelectorAll('#anno-toggle-btn');
    buttons.forEach(function (btn, index) {
      if (index > 0) btn.remove();
    });
    var btn = document.getElementById('anno-toggle-btn');
    if (!btn) {
      btn = document.createElement('button');
      btn.id = 'anno-toggle-btn';
      btn.type = 'button';
      btn.title = '显示或隐藏产品说明标注';
      btn.setAttribute('aria-label', '显示或隐藏产品说明标注');
      btn.textContent = '产品标注';
      btn.addEventListener('click', function () {
        visible = !visible;
        btn.classList.toggle('anno-hidden', !visible);
        closePopup();
        render();
      });
      document.body.appendChild(btn);
    }
    placeToggle(btn);
  }

  function placeToggle(btn) {
    var topBar = document.querySelector('.top-bar');
    var sideMenu = document.querySelector('.side-menu, .sidebar, .nav-panel');
    var top = topBar ? topBar.getBoundingClientRect().bottom + 12 : 16;
    var left = sideMenu ? sideMenu.getBoundingClientRect().right + 16 : 16;
    btn.style.top = Math.max(16, top) + 'px';
    btn.style.left = Math.max(16, left) + 'px';
  }

  function ensureOverlay() {
    var overlay = document.getElementById('anno-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'anno-overlay';
      document.body.appendChild(overlay);
    }
    return overlay;
  }

  function render() {
    ensureToggle();
    var overlay = ensureOverlay();
    overlay.innerHTML = '';
    if (!visible) return;
    getAnnotations().forEach(function (anno, index) {
      var target = resolveTarget(anno.target);
      if (!target) return;
      var marker = document.createElement('button');
      marker.type = 'button';
      marker.className = 'anno-marker';
      marker.textContent = anno.id || String(index + 1);
      marker.title = anno.title || '';

      // 绑定 mousedown 处理拖拽
      marker.addEventListener('mousedown', function (event) {
        event.stopPropagation();
        var startX = event.clientX;
        var startY = event.clientY;
        var rect = marker.getBoundingClientRect();
        markerDragState = {
          marker: marker,
          anno: anno,
          target: target,
          offsetX: startX - rect.left,
          offsetY: startY - rect.top,
          moved: false,
          startX: startX,
          startY: startY
        };
        event.preventDefault();
      });

      marker.addEventListener('click', function (event) {
        event.stopPropagation();
        // 拖拽结束后，防止误触发弹窗
        if (marker.getAttribute('data-dragged') === 'true') {
          marker.removeAttribute('data-dragged');
          return;
        }
        openPopup(anno, marker);
      });
      overlay.appendChild(marker);
      positionMarker(marker, target, anno.position);
    });
  }

  function resolveTarget(selector) {
    if (!selector) return null;
    try {
      var nodes = document.querySelectorAll(selector);
      if (nodes.length > 1) {
        console.warn('[AnnotationRuntime] target selector is not unique:', selector, nodes.length);
      }
      return nodes.length === 1 ? nodes[0] : null;
    } catch (err) {
      return null;
    }
  }

  function positionMarker(marker, target, position) {
    var rect = target.getBoundingClientRect();
    var pos = position || {};
    var placement = pos.placement || 'top-right';
    var x = rect.right;
    var y = rect.top;
    if (placement.indexOf('left') >= 0) x = rect.left;
    if (placement.indexOf('bottom') >= 0) y = rect.bottom;
    if (placement.indexOf('center') >= 0) y = rect.top + rect.height / 2;
    marker.style.left = Math.round(x + Number(pos.offsetX || 0) - 10) + 'px';
    marker.style.top = Math.round(y + Number(pos.offsetY || 0) - 10) + 'px';
  }

  function openPopup(anno, marker) {
    closePopup();
    currentAnno = clone(anno);
    currentAnno.desc = currentAnno.desc || generateDesc(currentAnno.sections);
    activePopup = document.createElement('div');
    activePopup.className = 'anno-popup';
    activePopup.innerHTML = buildViewHTML(currentAnno);
    document.body.appendChild(activePopup);
    positionPopup(activePopup, marker);
    bindViewEvents();
    bindDrag();
  }

  function positionPopup(popup, marker) {
    var rect = marker.getBoundingClientRect();
    var popupWidth = popup.offsetWidth;
    var popupHeight = popup.offsetHeight;
    var left = rect.right + 12;
    var top = rect.top;
    if (left + popupWidth > window.innerWidth - 16) {
      left = rect.left - popupWidth - 12;
    }
    left = Math.max(16, Math.min(left, window.innerWidth - popupWidth - 16));
    top = Math.max(16, Math.min(top, window.innerHeight - popupHeight - 16));
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
  }

  function fitPopupToViewport(popup) {
    if (!popup) return;
    var rect = popup.getBoundingClientRect();
    var left = Math.max(16, Math.min(rect.left, window.innerWidth - rect.width - 16));
    var top = Math.max(16, Math.min(rect.top, window.innerHeight - rect.height - 16));
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
  }

  function buildViewHTML(anno) {
    return ''
      + '<div class="anno-popup-header">'
      + '  <div class="anno-popup-title">' + escapeHTML(anno.title || '未命名标注') + '</div>'
      + '  <button class="anno-popup-close" type="button" title="关闭">&times;</button>'
      + '</div>'
      + '<div class="anno-popup-body"><div class="anno-popup-desc">' + (anno.desc || generateDesc(anno.sections)) + '</div></div>'
      + '<div class="anno-popup-footer">'
      + '  <button class="anno-btn anno-copy" type="button">复制数据</button>'
      + '  <button class="anno-btn anno-btn-primary anno-edit" type="button">编辑</button>'
      + '</div>';
  }

  function buildEditHTML(anno) {
    var sections = anno.sections || {};
    var fields = sectionFields.map(function (field) {
      return ''
        + '<div class="anno-edit-field">'
        + '  <label class="anno-edit-label">' + field[1] + '</label>'
        + '  <textarea class="anno-edit-textarea" data-section="' + field[0] + '">' + escapeHTML(sections[field[0]] || '') + '</textarea>'
        + '</div>';
    }).join('');
    return ''
      + '<div class="anno-popup-header">'
      + '  <div class="anno-popup-title">编辑标注</div>'
      + '  <button class="anno-popup-close" type="button" title="关闭">&times;</button>'
      + '</div>'
      + '<div class="anno-popup-body">'
      + '  <div class="anno-edit-field">'
      + '    <label class="anno-edit-label">标注标题</label>'
      + '    <input class="anno-edit-input" id="anno-edit-title" value="' + escapeHTML(anno.title || '') + '">'
      + '  </div>'
      + fields
      + '</div>'
      + '<div class="anno-popup-footer">'
      + '  <button class="anno-btn anno-cancel" type="button">取消</button>'
      + '  <button class="anno-btn anno-copy" type="button">复制数据</button>'
      + '  <button class="anno-btn anno-btn-primary anno-save" type="button">保存</button>'
      + '</div>';
  }

  function bindViewEvents() {
    activePopup.querySelector('.anno-popup-close').addEventListener('click', closePopup);
    activePopup.querySelector('.anno-copy').addEventListener('click', copyCurrent);
    activePopup.querySelector('.anno-edit').addEventListener('click', function () {
      activePopup.innerHTML = buildEditHTML(currentAnno);
      bindEditEvents();
      bindDrag();
      fitPopupToViewport(activePopup);
    });
  }

  function bindEditEvents() {
    activePopup.querySelector('.anno-popup-close').addEventListener('click', closePopup);
    activePopup.querySelector('.anno-cancel').addEventListener('click', function () {
      activePopup.innerHTML = buildViewHTML(currentAnno);
      bindViewEvents();
      bindDrag();
      fitPopupToViewport(activePopup);
    });
    activePopup.querySelector('.anno-copy').addEventListener('click', copyCurrent);
    activePopup.querySelector('.anno-save').addEventListener('click', saveEdit);
  }

  function saveEdit() {
    currentAnno.title = activePopup.querySelector('#anno-edit-title').value.trim();
    currentAnno.sections = {};
    activePopup.querySelectorAll('[data-section]').forEach(function (field) {
      currentAnno.sections[field.getAttribute('data-section')] = field.value.trim();
    });
    sectionFields.forEach(function (field) {
      if (!(field[0] in currentAnno.sections)) currentAnno.sections[field[0]] = '';
    });
    currentAnno.desc = generateDesc(currentAnno.sections);
    var items = getAnnotations();
    var found = false;
    items = items.map(function (item) {
      if (item.id === currentAnno.id) {
        found = true;
        return clone(currentAnno);
      }
      return item;
    });
    if (!found) items.push(clone(currentAnno));
    saveCached(items);
    activePopup.innerHTML = buildViewHTML(currentAnno);
    bindViewEvents();
    bindDrag();
    fitPopupToViewport(activePopup);
    showToast('已保存到浏览器缓存');
  }

  function copyCurrent() {
    if (!currentAnno) return;
    var latest = getAnnotations().filter(function (item) { return item.id === currentAnno.id; })[0];
    var dataToCopy = latest || currentAnno;
    copyText(JSON.stringify(dataToCopy, null, 2));
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { showToast('数据已复制'); });
      return;
    }
    var input = document.createElement('textarea');
    input.value = text;
    input.style.position = 'fixed';
    input.style.left = '-9999px';
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    input.remove();
    showToast('数据已复制');
  }

  function bindDrag() {
    var header = activePopup.querySelector('.anno-popup-header');
    header.addEventListener('mousedown', function (event) {
      if (event.target.closest('button')) return;
      var rect = activePopup.getBoundingClientRect();
      dragState = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      event.preventDefault();
    });
  }

  function closePopup() {
    if (activePopup) activePopup.remove();
    activePopup = null;
    currentAnno = null;
    dragState = null;
  }

  function generateDesc(sections) {
    var data = sections || {};
    return sectionFields.map(function (field, index) {
      return (index + 1) + '. ' + field[1] + '：' + escapeHTML(data[field[0]] || '待确认');
    }).join('<br>');
  }

  function escapeHTML(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function showToast(text) {
    var old = document.querySelector('.anno-toast');
    if (old) old.remove();
    var toast = document.createElement('div');
    toast.className = 'anno-toast';
    toast.textContent = text;
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 1800);
  }

  document.addEventListener('mousemove', function (event) {
    if (markerDragState) {
      var ds = markerDragState;
      var dx = event.clientX - ds.startX;
      var dy = event.clientY - ds.startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        ds.moved = true;
        ds.marker.setAttribute('data-dragged', 'true');
      }
      if (ds.moved) {
        var left = event.clientX - ds.offsetX;
        var top = event.clientY - ds.offsetY;

        // 边界限制
        left = Math.max(0, Math.min(left, window.innerWidth - ds.marker.offsetWidth));
        top = Math.max(0, Math.min(top, window.innerHeight - ds.marker.offsetHeight));

        ds.marker.style.left = left + 'px';
        ds.marker.style.top = top + 'px';
      }
      return;
    }

    if (!dragState || !activePopup) return;
    var x = Math.max(8, Math.min(event.clientX - dragState.x, window.innerWidth - activePopup.offsetWidth - 8));
    var y = Math.max(8, Math.min(event.clientY - dragState.y, window.innerHeight - activePopup.offsetHeight - 8));
    activePopup.style.left = x + 'px';
    activePopup.style.top = y + 'px';
  });

  document.addEventListener('mouseup', function () {
    if (markerDragState) {
      var ds = markerDragState;
      markerDragState = null;
      if (ds.moved) {
        var rect = ds.target.getBoundingClientRect();
        var markerRect = ds.marker.getBoundingClientRect();

        var pos = ds.anno.position || {};
        var placement = pos.placement || 'top-right';

        var x = rect.right;
        var y = rect.top;
        if (placement.indexOf('left') >= 0) x = rect.left;
        if (placement.indexOf('bottom') >= 0) y = rect.bottom;
        if (placement.indexOf('center') >= 0) y = rect.top + rect.height / 2;

        var newOffsetX = Math.round(markerRect.left + 10 - x);
        var newOffsetY = Math.round(markerRect.top + 10 - y);

        var items = getAnnotations();
        var found = false;
        items = items.map(function (item) {
          if (item.id === ds.anno.id) {
            found = true;
            var updated = clone(item);
            updated.position = updated.position || {};
            updated.position.offsetX = newOffsetX;
            updated.position.offsetY = newOffsetY;
            return updated;
          }
          return item;
        });
        if (found) {
          saveCached(items);
          showToast('锚点位置已更新并保存');
        }

        setTimeout(function () {
          ds.marker.removeAttribute('data-dragged');
        }, 50);
      } else {
        ds.marker.removeAttribute('data-dragged');
      }
      return;
    }

    dragState = null;
    fitPopupToViewport(activePopup);
  });

  window.addEventListener('resize', function () {
    render();
    fitPopupToViewport(activePopup);
  });
  window.addEventListener('scroll', render, true);

  function observeChanges() {
    var root = document.body;
    var _lastRender = 0;
    var _rafPending = false;

    function scheduleRender() {
      var now = Date.now();
      // Burst protection: skip if we rendered within the last 200 ms.
      if (now - _lastRender < 200) return;
      if (_rafPending) return;
      _rafPending = true;
      window.requestAnimationFrame(function () {
        _rafPending = false;
        _lastRender = Date.now();
        render();
      });
    }

    observer = new MutationObserver(function (mutations) {
      // Skip entirely when annotations are hidden.
      if (!visible) return;

      var shouldRender = false;
      for (var i = 0; i < mutations.length; i++) {
        var target = mutations[i].target;
        if (target && target.closest && target.closest('#anno-overlay, #anno-toggle-btn, .anno-popup, .anno-toast')) {
          continue;
        }
        shouldRender = true;
        break;
      }
      if (!shouldRender) return;

      window.clearTimeout(observer._debounceTimer);
      observer._debounceTimer = window.setTimeout(scheduleRender, 300);
    });
    observer.observe(root, { childList: true, subtree: true });
  }

  function init() {
    try {
      ensureToggle();
      ensureOverlay();
      render();
      observeChanges();
    } catch (err) {
      console.warn('[AnnotationRuntime] init failed:', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.AnnotationRuntime = {
    refresh: render,
    getPageKey: getPageKey,
    getAnnotations: getAnnotations,
    close: closePopup
  };
})();
