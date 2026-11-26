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
    var kicker = (state.kicker || 'LAST 30 DAYS').trim();

    var svg = '<defs>'
      + '<filter id="cardSh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="14" stdDeviation="20" flood-color="#000" flood-opacity="0.48"/></filter>'
      + '<filter id="txtSh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000" flood-opacity="0.72"/></filter>'
      + '</defs>';

    // Top frosted analytics card
    var cardY = 148;
    var cardW = 860;
    var cardX = 110;
    var cardH = 192;
    var metricMain = titleLines[0] || '184.4K VIEWS · $41.2K';
    var metricSub = titleLines[1] || 'Organic Growth Snapshot';

    svg += '<g filter="url(#cardSh)">'
      + '<rect x="' + cardX + '" y="' + cardY + '" width="' + cardW + '" height="' + cardH + '" rx="24" fill="#111318" fill-opacity="0.86" stroke="#FFFFFF" stroke-opacity="0.16" stroke-width="2"/>'
      + '<circle cx="' + (cardX + 42) + '" cy="' + (cardY + 46) + '" r="7" fill="#22C55E"/>'
      + '<text x="' + (cardX + 62) + '" y="' + (cardY + 54) + '" font-family=' + JSON.stringify(SANS) + ' font-size="24" font-weight="700" letter-spacing="2" fill="#A1A1AA">' + esc(kicker.toUpperCase()) + '</text>'
      + '<text x="' + (cardX + 38) + '" y="' + (cardY + 122) + '" font-family=' + JSON.stringify(SANS) + ' font-size="52" font-weight="800" fill="#F8FAFC">' + esc(metricMain) + '</text>'
      + '<text x="' + (cardX + 38) + '" y="' + (cardY + 162) + '" font-family=' + JSON.stringify(SANS) + ' font-size="26" font-weight="500" fill="#94A3B8">' + esc(metricSub) + '</text>'
      + '</g>';

    var capD = '';
    if (raw) {
      var sz = 48;
      var lines = wrapLines(raw, 860, sz, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1480 : 1445;
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 62) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="' + sz + '" font-weight="700" fill="#F4F1EA" filter="url(#txtSh)">' + esc(lines[i]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return metricMain + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 110, y: 148, w: 860, h: 192 }, { slot: 'caption', x: 90, y: 1400, w: 900, h: 140 }]; };
})();
