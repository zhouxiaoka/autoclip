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
    var titleText = (state.title_lines || []).join(' ').trim();

    var svg = '<defs>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="18" flood-color="#000" flood-opacity="0.65"/></filter>'
      + '</defs>';

    var activeWord = '';
    if (raw) {
      var words = raw.split(/\s+/).filter(Boolean);
      var dur = Math.max(0.2, ((moment && moment.end) || (t + 1.5)) - ((moment && moment.start) || 0));
      var rel = Math.max(0, t - ((moment && moment.start) || 0));
      var idx = Math.min(words.length - 1, Math.floor((rel / dur) * words.length));
      activeWord = (words[idx] || words[0] || '').toLowerCase();
    } else if (titleText) {
      activeWord = titleText.split(/\s+/)[0].toLowerCase();
    }

    if (activeWord) {
      var sz = 128;
      var ww = measureW(activeWord, sz, 900, SANS);
      if (ww > 880) sz = Math.max(68, Math.floor((sz * 880) / ww));
      svg += '<text x="540" y="990" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + sz + '" font-weight="900" letter-spacing="-2.5" fill="#FFFFFF" filter="url(#sh)">' + esc(activeWord) + '</text>';
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return activeWord;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 860, w: 900, h: 180 }]; };
})();
