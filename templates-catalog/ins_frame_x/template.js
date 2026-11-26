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
    var titleText = ((state.title_lines || []).join(' ').trim() || 'TOO BULKY').toUpperCase();
    var kicker = (state.kicker || 'SKIP THIS').trim().toUpperCase();
    var isGood = /YES|PASS|GOOD|KEEP|WORKS|✓/.test(kicker);

    // Centered square-ish rounded viewport cutout (x=110, y=380, w=860, h=960, rx=34)
    var fx = 110, fy = 380, fw = 860, fh = 960, r = 34;
    var cutout = 'M0,0 H1080 V1920 H0 Z '
      + 'M' + (fx + r) + ',' + fy
      + ' H' + (fx + fw - r) + ' Q' + (fx + fw) + ',' + fy + ' ' + (fx + fw) + ',' + (fy + r)
      + ' V' + (fy + fh - r) + ' Q' + (fx + fw) + ',' + (fy + fh) + ' ' + (fx + fw - r) + ',' + (fy + fh)
      + ' H' + (fx + r) + ' Q' + fx + ',' + (fy + fh) + ' ' + fx + ',' + (fy + fh - r)
      + ' V' + (fy + r) + ' Q' + fx + ',' + fy + ' ' + (fx + r) + ',' + fy + ' Z';

    var badgeColor = isGood ? '#22C55E' : '#EF4444';
    var badgeSym = isGood ? '✓' : '✕';

    var svg = '<path d="' + cutout + '" fill="#0D0E12" fill-rule="evenodd"/>'
      + '<rect x="' + fx + '" y="' + fy + '" width="' + fw + '" height="' + fh + '" rx="' + r + '" fill="none" stroke="#FFFFFF" stroke-opacity="0.14" stroke-width="2"/>'
      + '<circle cx="152" cy="316" r="28" fill="' + badgeColor + '"/>'
      + '<text x="152" y="328" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="34" font-weight="900" fill="#FFFFFF">' + badgeSym + '</text>'
      + '<text x="198" y="328" font-family=' + JSON.stringify(SANS) + ' font-size="30" font-weight="700" letter-spacing="3" fill="#E4E4E7">' + esc(kicker) + '</text>'
      + '<text x="540" y="1430" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="46" font-weight="800" letter-spacing="10" fill="#FFFFFF">' + esc(titleText) + '</text>';

    var capD = '';
    if (raw) {
      var lines = wrapLines(raw, 840, 36, 500, SANS, 2);
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (1520 + i * 50) + '" text-anchor="middle" font-family=' + JSON.stringify(SANS) + ' font-size="36" font-weight="500" fill="#A1A1AA">' + esc(lines[i]) + '</text>';
      }
      capD = raw;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return titleText + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 110, y: 280, w: 860, h: 72 }, { slot: 'caption', x: 110, y: 1380, w: 860, h: 200 }]; };
})();
