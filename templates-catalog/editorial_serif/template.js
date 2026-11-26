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
    var kicker = (state.kicker || '').trim();
    var titleText = (state.title_lines || []).join(' ').trim();

    var svg = '<defs>'
      + '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="10" flood-color="#000" flood-opacity="0.52"/></filter>'
      + '</defs>';

    var headD = '';
    if (kicker || (t < 2.2 && titleText)) {
      var topStr = kicker || titleText;
      svg += '<text x="540" y="196" text-anchor="middle" font-family=' + JSON.stringify(SERIF) + ' font-style="italic" font-size="30" letter-spacing="2" fill="#FFFFFF" fill-opacity="0.82" filter="url(#soft)">' + esc(topStr) + '</text>';
      headD = topStr;
    }

    var capD = '';
    if (raw) {
      var sz = 52;
      var lines = wrapLines(raw, 820, sz, 400, SERIF, 2);
      var y0 = lines.length === 1 ? 1235 : 1205;
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 68) + '" text-anchor="middle" font-family=' + JSON.stringify(SERIF) + ' font-size="' + sz + '" font-weight="400" letter-spacing="0.4" fill="#FFFFFF" fill-opacity="0.96" filter="url(#soft)">' + esc(lines[i]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return headD + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 120, y: 1160, w: 840, h: 150 }]; };
})();
