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
    var titleText = (state.title_lines || []).join(' ').trim() || 'Mosaics reflect light.';

    var svg = '<defs>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="10" flood-color="#000" flood-opacity="0.62"/></filter>'
      + '</defs>';

    // Top bold sans thesis with amber highlight on first word
    var tWords = titleText.split(/\s+/).filter(Boolean);
    var firstW = tWords[0] || '';
    var restW = tWords.slice(1).join(' ');
    var tsz = 56;
    var tw = measureW(titleText, tsz, 800, SANS);
    if (tw > 880) tsz = Math.max(36, Math.floor((tsz * 880) / tw));
    svg += '<text x="540" y="250" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + tsz + '" font-weight="800" filter="url(#sh)">'
      + '<tspan fill="#F59E0B">' + esc(firstW) + '</tspan>'
      + (restW ? '<tspan fill="#FFFFFF"> ' + esc(restW) + '</tspan>' : '')
      + '</text>';

    // Lower delicate thin serif subtitle
    var capD = '';
    if (raw) {
      var lines = wrapLines(raw, 820, 44, 400, SERIF, 2);
      var y0 = lines.length === 1 ? 1440 : 1405;
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 58) + '" text-anchor="middle" font-family=' + JSON.stringify(SERIF) + ' font-size="44" font-weight="400" fill="#E5E7EB" fill-opacity="0.92" filter="url(#sh)">' + esc(lines[i]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return titleText + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 90, y: 190, w: 900, h: 90 }, { slot: 'caption', x: 110, y: 1360, w: 860, h: 140 }]; };
})();
