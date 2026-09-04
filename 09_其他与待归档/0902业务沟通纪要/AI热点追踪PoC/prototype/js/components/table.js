(function () {
  'use strict';

  function render(columns, rows, options) {
    options = options || {};
    if (!rows.length) return '<div class="empty-state"><strong>' + AppCommon.escapeHtml(options.emptyTitle || '暂无数据') + '</strong><span>' + AppCommon.escapeHtml(options.emptyText || '请调整筛选条件或发起一次运行') + '</span></div>';
    return '<div class="table-shell"><table class="data-table"><thead><tr>' +
      columns.map(function (column) { return '<th' + (column.width ? ' style="width:' + column.width + '"' : '') + '>' + AppCommon.escapeHtml(column.label) + '</th>'; }).join('') +
      '</tr></thead><tbody>' + rows.map(function (row) {
        return '<tr' + (options.rowAttr ? ' ' + options.rowAttr(row) : '') + '>' + columns.map(function (column) {
          var value = column.render ? column.render(row) : AppCommon.escapeHtml(row[column.key] == null ? '—' : row[column.key]);
          return '<td>' + value + '</td>';
        }).join('') + '</tr>';
      }).join('') + '</tbody></table></div>';
  }

  function pagination(page, pageSize, total, attr) {
    var pages = Math.max(1, Math.ceil((total || 0) / pageSize));
    return '<div class="table-pagination"><span>共 ' + Number(total || 0) + ' 条 · 第 ' + page + ' / ' + pages + ' 页</span><div><button class="btn btn-sm" ' + attr + '="prev"' + (page <= 1 ? ' disabled' : '') + '>上一页</button><button class="btn btn-sm" ' + attr + '="next"' + (page >= pages ? ' disabled' : '') + '>下一页</button></div></div>';
  }

  window.DataTable = { render: render, pagination: pagination };
})();
