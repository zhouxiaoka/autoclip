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
    mctx.font = '800 ' + sz + 'px ' + SANS;
    return Math.max(1, mctx.measureText(text).width);
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function cueChunks(moment, lang) {
    if (!moment || !moment.zh || !moment.zh.length) return [];
    var raw = moment.zh.filter(function (x) { return x && x.s; }).map(function (x) { return x.s; });
    if (raw.length === 1 && /[\u4e00-\u9fff]/.test(raw[0]) && raw[0].length > 5) {
      var s = raw[0], out = [];
      for (var i = 0; i < s.length; i += 4) out.push(s.slice(i, i + 4));
      return out;
    }
    return raw;
  }
  window.setData = function (fill) { state = fill || {}; };
  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'zh';
    var lines = (state.title_lines || []).filter(Boolean);
    var line1 = lines[0] || state.kicker || '干货必看';
    var line2 = lines[1] || '';
    var kicker = (state.kicker && lines[0] && state.kicker !== lines[0]) ? state.kicker : 'HIGHLIGHT';

    var introP = clamp01(t / 0.25);
    var kw = Math.min(860, measureW(kicker, 30) + 44);
    var l1Sz = line1.length > 12 ? 62 : 76;
    var l2Sz = line2.length > 14 ? 54 : 66;

    var parts = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">',
      '<defs><linearGradient id="topg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0.72"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></linearGradient></defs>',
      '<rect x="0" y="0" width="1080" height="440" fill="url(#topg)"/>',
      '<g opacity="' + introP.toFixed(3) + '">',
      '<rect x="' + ((1080 - kw) / 2).toFixed(1) + '" y="142" width="' + kw.toFixed(1) + '" height="48" rx="24" fill="#FFE548"/>',
      '<text x="540" y="176" text-anchor="middle" font-family="' + SANS + '" font-size="28" font-weight="800" fill="#14151A">' + esc(kicker) + '</text>',
      '<text x="540" y="268" text-anchor="middle" font-family="' + SANS + '" font-size="' + l1Sz + '" font-weight="900" fill="#FFFFFF" stroke="#111" stroke-width="12" paint-order="stroke" stroke-linejoin="round">' + esc(line1) + '</text>',
      line2 ? '<text x="540" y="346" text-anchor="middle" font-family="' + SANS + '" font-size="' + l2Sz + '" font-weight="900" fill="#FFE548" stroke="#111" stroke-width="11" paint-order="stroke" stroke-linejoin="round">' + esc(line2) + '</text>' : '',
      '</g>'
    ];

    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var toks = cueChunks(moment, lang);
    var capD = 'IDLE';
    if (toks.length) {
      var mStart = (moment.t0 != null ? moment.t0 : moment.start) || 0;
      var mEnd = (moment.t1 != null ? moment.t1 : moment.end) || (mStart + 2.0);
      var prog = clamp01((t - mStart) / Math.max(0.2, mEnd - mStart));
      var activeIdx = Math.min(toks.length - 1, Math.floor(prog * toks.length));
      var sep = lang === 'en' ? ' ' : '';
      var full = toks.join(sep);
      capD = full + '_' + activeIdx;
      var fz = full.length > 20 ? 44 : 52;
      var totalW = measureW(full, fz);
      var xCur = Math.max(64, (1080 - totalW) / 2);
      parts.push('<g>');
      for (var i = 0; i < toks.length; i++) {
        var w = toks[i];
        var ww = measureW(w, fz);
        var isAct = i === activeIdx;
        if (isAct) {
          parts.push('<rect x="' + (xCur - 8).toFixed(1) + '" y="' + (1462 - fz + 4).toFixed(1) + '" width="' + (ww + 16).toFixed(1) + '" height="' + (fz + 16).toFixed(1) + '" rx="12" fill="#FFE548"/>');
        }
        parts.push('<text x="' + xCur.toFixed(1) + '" y="1468" font-family="' + SANS + '" font-size="' + fz + '" font-weight="900" fill="' + (isAct ? '#14151A' : '#FFFFFF') + '"' + (isAct ? '' : ' stroke="#111" stroke-width="10" paint-order="stroke" stroke-linejoin="round"') + '>' + esc(w) + '</text>');
        xCur += ww + (sep ? measureW(sep, fz) : 0);
      }
      parts.push('</g>');
    }
    parts.push('</svg>');
    root.innerHTML = parts.join('');
    return 'XHS_' + capD;
  };
  window.occupiedRects = function () { return []; };
})();
