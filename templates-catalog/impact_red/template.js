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
    var titleLines = (state.title_lines || []).filter(Boolean);

    var svg = '<defs>'
      + '<radialGradient id="vg" cx="50%" cy="50%" r="65%"><stop offset="0%" stop-color="#000" stop-opacity="0.32"/><stop offset="100%" stop-color="#000" stop-opacity="0.58"/></radialGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000" flood-opacity="0.55"/></filter>'
      + '</defs>';

    var digest = '';
    if (t < 1.55 && titleLines.length) {
      svg += '<rect x="0" y="0" width="1080" height="1920" fill="url(#vg)"/>';
      var words = titleLines.join(' ').trim().split(/\s+/).slice(0, 3);
      var baseY = 820;
      for (var i = 0; i < words.length; i++) {
        var w = words[i].toUpperCase();
        var isRed = (i === 1) || /\d/.test(w);
        var sz = isRed ? 148 : 112;
        var ww = measureW(w, sz, 900, SANS);
        if (ww > 880) sz = Math.max(64, Math.floor((sz * 880) / ww));
        var fill = isRed ? '#B91C1C' : '#FFFFFF';
        var y = baseY + i * 134;
        svg += '<text x="540" y="' + y + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + sz + '" font-weight="900" letter-spacing="-2" fill="' + fill + '" filter="url(#sh)">' + esc(w) + '</text>';
      }
      digest = 'HOOK:' + words.join('|');
    } else if (raw) {
      svg += '<rect x="0" y="0" width="1080" height="1920" fill="url(#vg)" opacity="0.55"/>';
      var tokens = raw.split(/\s+/).filter(Boolean);
      var mid = Math.floor(tokens.length / 2);
      var lines = tokens.length <= 3 ? tokens : [tokens.slice(0, mid).join(' '), tokens[mid], tokens.slice(mid + 1).join(' ')].filter(Boolean);
      var startY = 890 - (lines.length - 1) * 58;
      for (var j = 0; j < lines.length; j++) {
        var ln = lines[j].toUpperCase();
        var accent = (j === 1) || /\d/.test(ln);
        var csz = accent ? 104 : 84;
        var lw = measureW(ln, csz, 900, SANS);
        if (lw > 880) csz = Math.max(48, Math.floor((csz * 880) / lw));
        svg += '<text x="540" y="' + (startY + j * 116) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + csz + '" font-weight="900" letter-spacing="-1" fill="' + (accent ? '#DC2626' : '#FFFFFF') + '" filter="url(#sh)">' + esc(ln) + '</text>';
      }
      digest = 'CAP:' + raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return digest;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 740, w: 900, h: 420 }]; };
})();
