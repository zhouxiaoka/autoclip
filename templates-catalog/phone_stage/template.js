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
    var label = ((state.kicker || (state.title_lines || [])[0] || 'MY SPACE').trim()).toUpperCase();

    // Pure black outer matte with rounded inner phone cutout (x=116, y=280, w=848, h=1240, rx=56)
    var fx = 116, fy = 280, fw = 848, fh = 1240, r = 56;
    var cutout = 'M0,0 H1080 V1920 H0 Z '
      + 'M' + (fx + r) + ',' + fy
      + ' H' + (fx + fw - r) + ' Q' + (fx + fw) + ',' + fy + ' ' + (fx + fw) + ',' + (fy + r)
      + ' V' + (fy + fh - r) + ' Q' + (fx + fw) + ',' + (fy + fh) + ' ' + (fx + fw - r) + ',' + (fy + fh)
      + ' H' + (fx + r) + ' Q' + fx + ',' + (fy + fh) + ' ' + fx + ',' + (fy + fh - r)
      + ' V' + (fy + r) + ' Q' + fx + ',' + fy + ' ' + (fx + r) + ',' + fy + ' Z';

    var svg = '<path d="' + cutout + '" fill="#08080A" fill-rule="evenodd"/>'
      + '<rect x="' + fx + '" y="' + fy + '" width="' + fw + '" height="' + fh + '" rx="' + r + '" fill="none" stroke="#FFFFFF" stroke-opacity="0.18" stroke-width="3"/>';

    // Yellow top tag above bezel
    var lsz = 34;
    var lw = measureW(label, lsz, 900, SANS);
    var lpw = Math.min(720, Math.round(lw + 44));
    svg += '<rect x="' + Math.round(540 - lpw / 2) + '" y="182" width="' + lpw + '" height="60" rx="12" fill="#FACC15"/>'
      + '<text x="540" y="224" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + lsz + '" font-weight="900" letter-spacing="2" fill="#09090B">' + esc(label) + '</text>';

    var capD = '';
    if (raw) {
      var lines = wrapLines(raw, 860, 42, 600, SANS, 2);
      var y0 = lines.length === 1 ? 1645 : 1615;
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 56) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="42" font-weight="600" fill="#F4F4F5">' + esc(lines[i]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return label + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 180, y: 180, w: 720, h: 64 }, { slot: 'caption', x: 90, y: 1580, w: 900, h: 120 }]; };
})();
