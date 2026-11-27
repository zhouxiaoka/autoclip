(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', 'ACBarlow', Impact, sans-serif";
  var SERIF = "'ACInstrument', 'ACPlayfair', Georgia, serif";
  var PLAYFAIR = "'ACPlayfair', Georgia, serif";
  var BRUSH = "'ACCaveat', Georgia, cursive";

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }

  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutCubic(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 3); }
  function easeOutBack(x) {
    var p = clamp01(x);
    var c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
  }
  function springPop(age, dur) {
    var p = clamp01(age / (dur || 0.24));
    if (p >= 1) return 1;
    return 0.78 + 0.22 * easeOutBack(p);
  }
  function blurReveal(age, dur) {
    var p = easeOutCubic(age / (dur || 0.26));
    return {
      alpha: p,
      blur: Math.max(0, (1 - p) * 7.5),
      dy: (1 - p) * 20,
      step: Math.round(p * 20),
    };
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
    var kicker = (state.kicker || 'EDITORIAL · V04').trim().toUpperCase();
    var titleLines = (state.title_lines || []).filter(Boolean);

    var isTitlePhase = (t < 1.5 && titleLines.length);
    var displayText = isTitlePhase ? titleLines.join(' ') : (raw || titleLines.join(' '));
    var age = isTitlePhase ? t : Math.max(0, t - ((moment && moment.start) || 0));
    var p = easeOutCubic(age / 0.34);

    var svg = '<defs>'
      + '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="12" flood-color="#000" flood-opacity="0.58"/></filter>'
      + '<clipPath id="mask0"><rect x="80" y="1020" width="920" height="90"/></clipPath>'
      + '<clipPath id="mask1"><rect x="80" y="1104" width="920" height="90"/></clipPath>'
      + '</defs>';

    svg += '<text x="540" y="196" text-anchor="middle" font-family="' + SANS + '" font-size="22" font-weight="600" letter-spacing="6" fill="#FFFFFF" fill-opacity="0.86" filter="url(#soft)">' + esc(kicker) + '</text>';

    var capD = '';
    if (displayText) {
      var up = displayText.toUpperCase();
      var sz = 54;
      var lines = wrapLines(up, 740, sz, 500, PLAYFAIR, 2);
      for (var i = 0; i < lines.length; i++) {
        var lp = easeOutCubic(Math.max(0, age - i * 0.1) / 0.32);
        var dy = (1 - lp) * 68;
        var baseY = lines.length === 1 ? 1094 : (1092 + i * 84);
        svg += '<g clip-path="url(#mask' + i + ')" opacity="' + lp.toFixed(2) + '">'
          + '<text x="540" y="' + (baseY + dy).toFixed(1) + '" text-anchor="middle" font-family="' + PLAYFAIR + '" font-size="' + sz + '" font-weight="500" letter-spacing="5" fill="#FFFFFF" filter="url(#soft)">' + esc(lines[i]) + '</text></g>';
      }
      capD = up + '@' + Math.round(p * 20);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return kicker + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 110, y: 1020, w: 860, h: 180 }]; };
})();
