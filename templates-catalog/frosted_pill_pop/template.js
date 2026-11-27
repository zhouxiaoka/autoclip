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
    var titleText = (state.title_lines || []).join(' ').trim() || 'the best time to start?';
    var kicker = (state.kicker || 'real talk').trim();
    var hIn = easeOutCubic(t / 0.3);
    var mAge = Math.max(0, t - ((moment && moment.start) || 0));
    var psc = springPop(mAge, 0.22);

    var svg = '<defs>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000" flood-opacity="0.45"/></filter>'
      + '</defs>';

    // Handwritten Caveat kicker + bold stacked question hook
    svg += '<g transform="translate(0,' + ((1 - hIn) * 20).toFixed(1) + ')" opacity="' + hIn.toFixed(2) + '" filter="url(#sh)">';
    if (kicker) {
      svg += '<text x="540" y="196" text-anchor="middle" font-family="' + BRUSH + '" font-size="48" font-weight="700" fill="#FDE047" transform="rotate(-3,540,196)">' + esc(kicker) + '</text>';
    }
    var hLines = wrapLines(titleText, 820, 60, 700, SANS, 2);
    for (var i = 0; i < hLines.length; i++) {
      svg += '<text x="540" y="' + (266 + i * 70) + '" text-anchor="middle" font-family="' + SANS + '" font-size="60" font-weight="700" letter-spacing="-1" fill="#FFFFFF">' + esc(hLines[i]) + '</text>';
    }
    svg += '</g>';

    var capD = '';
    if (raw) {
      var csz = 42;
      var cw = measureW(raw, csz, 600, SANS);
      if (cw > 800) { csz = Math.max(28, Math.floor((csz * 800) / cw)); cw = measureW(raw, csz, 600, SANS); }
      var pw = Math.min(880, Math.round(cw + 56));
      var ph = Math.round(csz * 1.85);
      svg += '<g transform="translate(540,1455) scale(' + psc.toFixed(3) + ')" filter="url(#sh)">'
        + '<rect x="' + (-pw / 2) + '" y="' + (-ph / 2) + '" width="' + pw + '" height="' + ph + '" rx="' + Math.round(ph / 2) + '" fill="#111318" fill-opacity="0.68" stroke="#FFFFFF" stroke-opacity="0.32" stroke-width="2"/>'
        + '<text x="0" y="' + Math.round(csz * 0.34) + '" text-anchor="middle" font-family="' + SANS + '" font-size="' + csz + '" font-weight="600" fill="#FFFFFF">' + esc(raw) + '</text></g>';
      capD = raw + '@' + Math.round(psc * 40);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return titleText + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 110, y: 150, w: 860, h: 210 }, { slot: 'caption', x: 100, y: 1410, w: 880, h: 90 }]; };
})();
