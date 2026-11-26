(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = '"Inter", "SF Pro Display", "Helvetica Neue", "PingFang SC", "Noto Sans CJK SC", sans-serif';
  var SERIF = '"Georgia", "Times New Roman", "Songti SC", "Noto Serif CJK SC", serif';

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }

  function measureW(text, sz, weight, family) {
    mctx.font = (weight || 700) + ' ' + sz + 'px ' + (family || SANS);
    return Math.max(1, mctx.measureText(text).width);
  }

  function cueText(moment, lang) {
    if (!moment || !moment.zh || !moment.zh.length) return '';
    var parts = [];
    for (var i = 0; i < moment.zh.length; i++) {
      if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
    }
    return parts.join(lang === 'en' ? ' ' : '').trim();
  }

  function wrapLines(text, maxW, sz, weight, family, maxLines) {
    var words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var lines = [];
    var cur = words[0];
    for (var i = 1; i < words.length; i++) {
      var cand = cur + ' ' + words[i];
      if (measureW(cand, sz, weight, family) <= maxW) {
        cur = cand;
      } else {
        lines.push(cur);
        cur = words[i];
        if (maxLines && lines.length >= maxLines - 1) {
          var rest = words.slice(i).join(' ');
          lines.push(rest);
          return lines;
        }
      }
    }
    lines.push(cur);
    return lines;
  }

  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var kicker = (state.kicker || (state.title_lines || [])[0] || 'THIS').trim().toUpperCase();

    var svg = '<defs>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000" flood-opacity="0.48"/></filter>'
      + '</defs>';

    // Punchy top micro pill
    if (kicker) {
      var ksz = 34;
      var kw = measureW(kicker, ksz, 900, SANS);
      var kpw = Math.min(760, Math.round(kw + 44));
      svg += '<g filter="url(#sh)">'
        + '<rect x="' + Math.round(540 - kpw / 2) + '" y="210" width="' + kpw + '" height="62" rx="12" fill="#09090B" stroke="#FFFFFF" stroke-opacity="0.22" stroke-width="2"/>'
        + '<text x="540" y="253" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + ksz + '" font-weight="900" letter-spacing="1.5" fill="#FFFFFF">' + esc(kicker) + '</text>'
        + '</g>';
    }

    var capD = '';
    if (raw) {
      var up = raw.toUpperCase();
      var lines = wrapLines(up, 820, 48, 900, SANS, 2);
      var y0 = lines.length === 1 ? 1400 : 1365;
      for (var i = 0; i < lines.length; i++) {
        var lw = measureW(lines[i], 48, 900, SANS);
        var pw = Math.min(900, Math.round(lw + 48));
        var py = y0 + i * 82;
        svg += '<g filter="url(#sh)">'
          + '<rect x="' + Math.round(540 - pw / 2) + '" y="' + py + '" width="' + pw + '" height="72" rx="12" fill="#09090B" fill-opacity="0.95"/>'
          + '<text x="540" y="' + (py + 52) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="48" font-weight="900" letter-spacing="0.5" fill="#FFFFFF">' + esc(lines[i]) + '</text>'
          + '</g>';
      }
      capD = up;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return kicker + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 1350, w: 900, h: 170 }]; };
})();
