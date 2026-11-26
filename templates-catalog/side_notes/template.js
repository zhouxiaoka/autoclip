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
    var kicker = (state.kicker || 'SETUP NOTES').trim().toUpperCase();
    var notes = (state.title_lines || []).filter(Boolean);
    if (!notes.length) notes = ['Macro detail', 'Rim light 45deg', 'f/2.8 · 1/120s'];

    var svg = '<defs>'
      + '<linearGradient id="sideBg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#050814" stop-opacity="0.78"/><stop offset="52%" stop-color="#050814" stop-opacity="0"/></linearGradient>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="8" flood-color="#000" flood-opacity="0.7"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="0" width="640" height="1920" fill="url(#sideBg)"/>';
    svg += '<rect x="64" y="296" width="3" height="' + (90 + notes.length * 76) + '" rx="1.5" fill="#93C5FD" fill-opacity="0.75"/>';
    svg += '<text x="86" y="324" font-family=' + JSON.stringify(SANS) + ' font-size="22" font-weight="700" letter-spacing="3" fill="#93C5FD">' + esc(kicker) + '</text>';

    for (var i = 0; i < Math.min(4, notes.length); i++) {
      var ny = 398 + i * 76;
      svg += '<circle cx="94" cy="' + (ny - 9) + '" r="4" fill="#FFFFFF" fill-opacity="0.85"/>'
        + '<text x="114" y="' + ny + '" font-family=' + JSON.stringify(SANS) + ' font-size="30" font-weight="600" fill="#F8FAFC" fill-opacity="0.92" filter="url(#sh)">' + esc(notes[i]) + '</text>';
    }

    var capD = '';
    if (raw) {
      var lines = wrapLines(raw, 860, 44, 600, SANS, 2);
      var y0 = lines.length === 1 ? 1500 : 1468;
      for (var j = 0; j < lines.length; j++) {
        svg += '<text x="64" y="' + (y0 + j * 58) + '" font-family=' + JSON.stringify(SANS) + ' font-size="44" font-weight="600" fill="#FFFFFF" filter="url(#sh)">' + esc(lines[j]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return notes.join('|') + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 64, y: 296, w: 420, h: 360 }, { slot: 'caption', x: 64, y: 1430, w: 900, h: 140 }]; };
})();
