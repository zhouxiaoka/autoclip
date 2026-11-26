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
    var titleText = (state.title_lines || []).join(' ').trim() || 'BATTERY HABITS TESTED';

    var svg = '<defs>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000" flood-opacity="0.38"/></filter>'
      + '</defs>';

    // 3-column color-coded tier header
    var cols = [
      { label: 'HURTS', bg: '#DC2626', active: t < 1.1 },
      { label: 'NO EFFECT', bg: '#EAB308', active: t >= 1.1 && t < 2.2 },
      { label: 'HELPS', bg: '#16A34A', active: t >= 2.2 },
    ];
    var bx = 72;
    var by = 152;
    var colW = 304;
    var gap = 12;
    svg += '<g filter="url(#sh)">';
    for (var i = 0; i < cols.length; i++) {
      var cx = bx + i * (colW + gap);
      var op = cols[i].active ? '1' : '0.45';
      svg += '<rect x="' + cx + '" y="' + by + '" width="' + colW + '" height="64" rx="14" fill="' + cols[i].bg + '" fill-opacity="' + op + '"/>'
        + '<text x="' + (cx + colW / 2) + '" y="' + (by + 42) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="28" font-weight="800" letter-spacing="1.2" fill="#FFFFFF">' + cols[i].label + '</text>';
    }
    svg += '<rect x="190" y="' + (by + 80) + '" width="700" height="54" rx="27" fill="#0F1115" fill-opacity="0.78"/>'
      + '<text x="540" y="' + (by + 116) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="28" font-weight="700" fill="#FFFFFF">' + esc(titleText) + '</text>'
      + '</g>';

    var activeCol = cols[t < 1.1 ? 0 : (t < 2.2 ? 1 : 2)];
    var capD = '';
    if (raw) {
      var csz = 46;
      var cw = measureW(raw, csz, 800, SANS);
      if (cw > 820) { csz = Math.max(30, Math.floor((csz * 820) / cw)); cw = measureW(raw, csz, 800, SANS); }
      var pw = Math.min(900, Math.round(cw + 56));
      var ph = Math.round(csz * 1.75);
      var px = Math.round(540 - pw / 2);
      var py = 1445;
      svg += '<g filter="url(#sh)">'
        + '<rect x="' + px + '" y="' + py + '" width="' + pw + '" height="' + ph + '" rx="16" fill="#0F1115" fill-opacity="0.88" stroke="' + activeCol.bg + '" stroke-width="3"/>'
        + '<text x="540" y="' + (py + Math.round(ph / 2 + csz * 0.34)) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + csz + '" font-weight="800" fill="' + (activeCol.bg === '#DC2626' ? '#FCA5A5' : (activeCol.bg === '#EAB308' ? '#FDE047' : '#86EFAC')) + '">' + esc(raw) + '</text>'
        + '</g>';
      capD = raw + '@' + activeCol.label;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return titleText + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 72, y: 152, w: 936, h: 140 }, { slot: 'caption', x: 90, y: 1440, w: 900, h: 96 }]; };
})();
