(function () {
  'use strict';

  function render(fields, actions) {
    return '<div class="filter-bar">' + fields.map(function (field) {
      var control = '';
      if (field.type === 'select') {
        control = '<select class="form-control" data-filter="' + field.key + '">' +
          (field.options || []).map(function (option) {
            return '<option value="' + AppCommon.escapeHtml(option.value) + '">' + AppCommon.escapeHtml(option.label) + '</option>';
          }).join('') + '</select>';
      } else {
        control = '<input class="form-control" data-filter="' + field.key + '" type="' + (field.type || 'text') + '" placeholder="' + AppCommon.escapeHtml(field.placeholder || '') + '">';
      }
      return '<div class="filter-field"><label>' + AppCommon.escapeHtml(field.label) + '</label>' + control + '</div>';
    }).join('') + '<div class="filter-actions">' + (actions || '') + '</div></div>';
  }

  function values(root) {
    var result = {};
    root.querySelectorAll('[data-filter]').forEach(function (element) { result[element.dataset.filter] = element.value; });
    return result;
  }

  window.Filters = { render: render, values: values };
})();
