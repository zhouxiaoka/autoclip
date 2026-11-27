(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var SERIF = "'Songti SC', 'STSong', 'Noto Serif CJK SC', 'ACInstrument', Georgia, serif";
  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutQuint(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 5); }
  function hasCJK(s) { return /[\u4e00-\u9fff]/.test(s || ''); }
  function pickVerticalWord(state, moment) {
    var tl = (state.title_lines || []).join('').trim();
    if (tl && hasCJK(tl)) return tl.replace(/[，。！？、\s]/g, '').slice(0, 5);
    var raw = '';
    if (moment && moment.zh) {
      for (var i = 0; i < moment.zh.length; i++) raw += (moment.zh[i].s || '') + ' ';
    }
    raw = raw.trim();
    if (hasCJK(raw)) return raw.replace(/[，。！？、\s]/g, '').slice(0, 4);
    var words = (tl || raw || 'ZEN').split(/\s+/).filter(Boolean);
    var best = words[0] || 'ZEN';
    for (var j = 0; j < words.length; j++) {
      if (words[j].replace(/[^A-Za-z]/g, '').length >= best.replace(/[^A-Za-z]/g, '').length) best = words[j];
    }
    return best.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 6) || 'ZEN';
  }
  window.setData = function (fill) { state = fill || {}; };
  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var word = pickVerticalWord(state, moment);
    var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
    var mAge = Math.max(0, t - mStart);
    var p = easeOutQuint(mAge / 0.48);
    var yShift = (1 - p) * 36;
    var op = 0.25 + 0.72 * p;
    var cjk = hasCJK(word);
    var chars = word.split('');
    var fz = cjk ? (chars.length <= 4 ? 156 : 136) : (chars.length <= 5 ? 148 : 122);
    var step = cjk ? Math.round(fz * 1.08) : Math.round(fz * 0.94);
    var startY = 230;
    var xCol = 910;
    var parts = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">',
      '<defs><filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="16" flood-color="#000" flood-opacity="0.52"/></filter></defs>',
      '<g opacity="' + op.toFixed(3) + '" transform="translate(0,' + yShift.toFixed(1) + ')" filter="url(#sh)">',
      '<line x1="' + (xCol - 92) + '" y1="190" x2="' + (xCol - 92) + '" y2="' + (startY + chars.length * step) + '" stroke="#F5EFE4" stroke-opacity="0.38" stroke-width="2.5"/>',
      '<rect x="' + (xCol - 26) + '" y="168" width="52" height="52" rx="7" fill="#D93829"/>',
      '<text x="' + xCol + '" y="206" text-anchor="middle" font-family="' + SERIF + '" font-size="30" font-weight="700" fill="#FFF8EE">印</text>'
    ];
    for (var i = 0; i < chars.length; i++) {
      var cy = startY + i * step + fz * 0.75;
      parts.push(
        '<text x="' + xCol + '" y="' + cy.toFixed(1) + '" text-anchor="middle" font-family="' + SERIF + '" font-size="' + fz + '" font-weight="700" fill="#FAF6EE" fill-opacity="0.95">' + esc(chars[i]) + '</text>'
      );
    }
    parts.push('</g></svg>');
    root.innerHTML = parts.join('');
    return 'VZ_B_' + word + '_' + Math.round(p * 20);
  };
  window.occupiedRects = function () { return []; };
})();
