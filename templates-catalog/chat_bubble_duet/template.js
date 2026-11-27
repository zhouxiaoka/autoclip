(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'PingFang SC', 'Noto Sans SC', 'ACSpace', sans-serif";
  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }
  function measureW(text, sz) {
    mctx.font = '700 ' + sz + 'px ' + SANS;
    return Math.max(1, mctx.measureText(text).width);
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function spring(age) {
    var p = clamp01(age / 0.28);
    if (p >= 1) return 1;
    return 1 - Math.exp(-7.5 * p) * Math.cos(9.5 * p);
  }
  function cueText(m, lang) {
    if (!m || !m.zh || !m.zh.length) return '';
    return m.zh.map(function (x) { return x.s || ''; }).join(lang === 'en' ? ' ' : '').trim();
  }
  function drawBubble(text, isRight, yTop, scale, opacity) {
    var fz = text.length > 26 ? 36 : 42;
    var tw = Math.min(760, measureW(text, fz));
    var bw = Math.max(180, tw + 56);
    var bh = 86;
    var bx = isRight ? (1080 - 78 - bw) : 78;
    var bg = isRight ? '#95EC69' : '#FFFFFF';
    var fg = '#14151A';
    var cx = bx + bw / 2;
    var cy = yTop + bh / 2;
    var tail = isRight
      ? '<polygon points="' + (bx + bw - 8) + ',' + (yTop + 28) + ' ' + (bx + bw + 14) + ',' + (yTop + 42) + ' ' + (bx + bw - 8) + ',' + (yTop + 56) + '" fill="' + bg + '"/>'
      : '<polygon points="' + (bx + 8) + ',' + (yTop + 28) + ' ' + (bx - 14) + ',' + (yTop + 42) + ' ' + (bx + 8) + ',' + (yTop + 56) + '" fill="' + bg + '"/>';
    return (
      '<g opacity="' + opacity.toFixed(3) + '" transform="translate(' + cx.toFixed(1) + ',' + cy.toFixed(1) + ') scale(' + scale.toFixed(3) + ') translate(' + (-cx).toFixed(1) + ',' + (-cy).toFixed(1) + ')" filter="url(#bsh)">' +
      tail +
      '<rect x="' + bx.toFixed(1) + '" y="' + yTop + '" width="' + bw.toFixed(1) + '" height="' + bh + '" rx="22" fill="' + bg + '"/>' +
      '<text x="' + (bx + 28).toFixed(1) + '" y="' + (yTop + 56) + '" font-family="' + SANS + '" font-size="' + fz + '" font-weight="700" fill="' + fg + '">' + esc(text) + '</text>' +
      '</g>'
    );
  }
  window.setData = function (fill) { state = fill || {}; };
  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'zh';
    var list = (window.ACTemplate && window.ACTemplate.moments) ? window.ACTemplate.moments(state) : [];
    var idx = -1;
    for (var i = 0; i < list.length; i++) {
      var a = list[i].t0 != null ? list[i].t0 : list[i].start;
      var b = list[i].t1 != null ? list[i].t1 : list[i].end;
      if (t >= a && t < b) { idx = i; break; }
    }
    if (idx < 0) {
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"></svg>';
      return 'CHAT_IDLE';
    }
    var cur = list[idx];
    var curTxt = cueText(cur, lang);
    var prevTxt = idx > 0 ? cueText(list[idx - 1], lang) : '';
    var mStart = cur.t0 != null ? cur.t0 : cur.start;
    var sc = 0.84 + 0.16 * spring(Math.max(0, t - mStart));
    var op = clamp01((t - mStart) / 0.14);
    var parts = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">',
      '<defs><filter id="bsh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000" flood-opacity="0.32"/></filter></defs>'
    ];
    if (prevTxt) {
      parts.push(drawBubble(prevTxt, ((idx - 1) % 2) === 1, 1320, 0.94, 0.62));
    }
    parts.push(drawBubble(curTxt, (idx % 2) === 1, 1434, sc, op));
    parts.push('</svg>');
    root.innerHTML = parts.join('');
    return 'CHAT_' + idx + '_' + Math.round(sc * 100);
  };
  window.occupiedRects = function () { return []; };
})();
