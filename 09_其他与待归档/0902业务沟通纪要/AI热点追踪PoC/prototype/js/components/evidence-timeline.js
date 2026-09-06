(function () {
  'use strict';

  function render(evidence) {
    if (!evidence || !evidence.length) return '<div class="empty-state compact"><span>暂无可用证据</span></div>';
    return '<div class="evidence-timeline">' + evidence.map(function (item) {
      return '<article class="evidence-item"><span class="evidence-item__dot"></span><div class="evidence-item__meta">' +
        '<strong>' + AppCommon.escapeHtml(item.evidence_type === 'source_excerpt' ? '公开来源证据' : 'Codex 补充证据') + '</strong>' +
        '<span>' + AppCommon.escapeHtml(({source_pipeline:'来源处理服务',codex:'Codex补充分析',codex_web_search:'Codex搜索',doubao_global_search:'豆包搜索',operator:'运营补充',manual:'人工补充'})[item.provided_by] || '证据处理服务') + ' · ' + AppCommon.formatTime(item.created_at) + '</span></div>' +
        '<p>' + AppCommon.escapeHtml(item.evidence_text) + '</p>' +
        (item.evidence_url ? '<a href="' + AppCommon.escapeHtml(item.evidence_url) + '" target="_blank" rel="noopener">打开原始证据</a>' : '') + '</article>';
    }).join('') + '</div>';
  }

  window.EvidenceTimeline = { render: render };
})();
