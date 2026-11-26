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
    var kicker = (state.kicker || 'EDITORIAL · VOL. 04').trim().toUpperCase();
    var titleLines = (state.title_lines || []).filter(Boolean);

    var svg = '<defs>'
      + '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="12" flood-color="#000" flood-opacity="0.45"/></filter>'
      + '</defs>';

    svg += '<text x="540" y="196" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="22" font-weight="600" letter-spacing="6" fill="#FFFFFF" fill-opacity="0.82" filter="url(#soft)">' + esc(kicker) + '</text>';

    var displayText = (t < 1.5 && titleLines.length) ? titleLines.join(' ') : (raw || titleLines.join(' '));
    var capD = '';
    if (displayText) {
      var up = displayText.toUpperCase();
      var lines = wrapLines(up, 820, 62, 400, SERIF, 2);
      var y0 = lines.length === 1 ? 1140 : 1100;
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 80) + '" text-anchor="middle" font-family=' + JSON.stringify(SERIF) + ' font-size="62" font-weight="400" letter-spacing="6" fill="#FFFFFF" filter="url(#soft)">' + esc(lines[i]) + '</text>';
      }
      capD = up;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return kicker + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 110, y: 1030, w: 860, h: 180 }]; };
})();
