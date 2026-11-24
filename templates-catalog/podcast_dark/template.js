/* 暗黑播客. Powered by ACTemplate SDK; pure function of (fill, t). */
(function () {
  var state = {};
  function $(id) { return document.getElementById(id); }

  window.setData = function (fill) {
    state = fill || {};
    var L = ACTemplate.labels(state);
    var series = String(state.kicker || state.issue || '');
    $('series').textContent = series;
    $('series').hidden = !series;
    $('title').textContent = (state.title_lines || []).join('\n');
    var g = state.guest;
    $('guest').textContent = g && g.name ? (g.role ? g.name + ' · ' + g.role : g.name) : '';
    $('note').textContent = state.translated ? L.excerpt + ' · ' + L.translated : L.excerpt;
  };

  window.renderFrame = function (t) {
    var active = ACTemplate.momentAt(state, t);
    var zhHtml = ACTemplate.zhHtml(state, active, { highlightClass: 'hl', maxLines: 2, hostPrefix: true });
    var enText = ACTemplate.enText(state, active, { onlyTranslated: true });
    $('zh').innerHTML = zhHtml;
    $('en').textContent = enText;
    return zhHtml + '|' + enText;
  };

  window.occupiedRects = function () {
    return ACTemplate.occupiedRects(['head', 'subtitle', 'foot']);
  };
})();
