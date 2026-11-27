(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var SANS = "'PingFang SC', 'Noto Sans SC', 'ACSpace', sans-serif";
  var SERIF = "'Songti SC', 'Noto Serif CJK SC', 'ACInstrument', Georgia, serif";
  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function cueText(moment, lang) {
    if (!moment || !moment.zh || !moment.zh.length) return '';
    var parts = [];
    for (var i = 0; i < moment.zh.length; i++) if (moment.zh[i].s) parts.push(moment.zh[i].s);
    return parts.join(lang === 'en' ? ' ' : '').trim();
  }
  window.setData = function (fill) { state = fill || {}; };
  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'zh';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var text = cueText(moment, lang);
    if (!text) {
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"></svg>';
      return 'VZ_F_IDLE';
    }
    var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
    var op = clamp01((t - mStart) / 0.22);
    var kicker = (state.kicker || '').trim();
    var svg = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">',
      '<defs><linearGradient id="bgf" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.65"/></linearGradient></defs>',
      '<rect x="0" y="1320" width="1080" height="600" fill="url(#bgf)"/>',
      '<g opacity="' + op.toFixed(3) + '">',
      '<rect x="498" y="1430" width="84" height="3" rx="1.5" fill="#D93829"/>',
      kicker ? '<text x="540" y="1410" text-anchor="middle" font-family="' + SANS + '" font-size="24" letter-spacing="4" fill="#E8E2D8" fill-opacity="0.82">' + esc(kicker.toUpperCase()) + '</text>' : '',
      '<text x="540" y="1504" text-anchor="middle" font-family="' + SERIF + '" font-size="48" font-weight="600" fill="#FAF7F0" stroke="#000" stroke-width="5" paint-order="stroke" stroke-opacity="0.55">' + esc(text) + '</text>',
      '</g></svg>'
    ].join('');
    root.innerHTML = svg;
    return 'VZ_F_' + text + '_' + Math.round(op * 10);
  };
  window.occupiedRects = function () { return []; };
})();
