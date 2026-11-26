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
    var kicker = (state.kicker || (state.title_lines || [])[0] || '').trim();

    var svg = '<defs>'
      + '<linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#000" stop-opacity="0.52"/><stop offset="65%" stop-color="#000" stop-opacity="0"/></linearGradient>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="10" flood-color="#000" flood-opacity="0.55"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="0" width="760" height="1920" fill="url(#lg)"/>';
    if (kicker) {
      svg += '<text x="76" y="210" font-family=' + JSON.stringify(SANS) + ' font-size="28" font-weight="700" letter-spacing="2.5" fill="#FACC15" filter="url(#sh)">' + esc(kicker.toUpperCase()) + '</text>';
    }

    var capD = '';
    if (raw) {
      var words = raw.split(/\s+/).filter(Boolean);
      var lines = [];
      for (var i = 0; i < words.length; i += 2) {
        lines.push(words.slice(i, i + 2).join(' '));
      }
      lines = lines.slice(0, 3);
      var startY = 1220;
      for (var j = 0; j < lines.length; j++) {
        var isHl = (j === lines.length - 1);
        svg += '<text x="76" y="' + (startY + j * 92) + '" font-family=' + JSON.stringify(SANS) + ' font-size="76" font-weight="800" letter-spacing="-1" fill="' + (isHl ? '#FACC15' : '#FFFFFF') + '" filter="url(#sh)">' + esc(lines[j]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return kicker + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 76, y: 1140, w: 680, h: 320 }]; };
})();
