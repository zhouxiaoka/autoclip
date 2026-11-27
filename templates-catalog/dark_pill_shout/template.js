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
    var kicker = (state.kicker || (state.title_lines || [])[0] || 'THIS').trim().toUpperCase();
    var mAge = Math.max(0, t - ((moment && moment.start) || 0));
    var sc = springPop(mAge, 0.2);

    var svg = '<defs>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000" flood-opacity="0.52"/></filter>'
      + '</defs>';

    if (kicker) {
      var ksz = 42;
      var kw = measureW(kicker, ksz, 900, POSTER);
      var kpw = Math.min(760, Math.round(kw + 48));
      var ksc = springPop(t, 0.22);
      svg += '<g transform="translate(540,242) scale(' + ksc.toFixed(3) + ')" filter="url(#sh)">'
        + '<rect x="' + (-kpw / 2) + '" y="-32" width="' + kpw + '" height="64" rx="12" fill="#09090B" stroke="#FFFFFF" stroke-opacity="0.24" stroke-width="2"/>'
        + '<text x="0" y="14" text-anchor="middle" font-family="' + POSTER + '" font-size="' + ksz + '" font-weight="900" letter-spacing="2" fill="#FFFFFF">' + esc(kicker) + '</text></g>';
    }

    var capD = '';
    if (raw) {
      var up = raw.toUpperCase();
      var lines = wrapLines(up, 800, 58, 900, POSTER, 2);
      var y0 = lines.length === 1 ? 1435 : 1395;
      svg += '<g transform="translate(540,' + y0 + ') scale(' + sc.toFixed(3) + ')" filter="url(#sh)">';
      for (var i = 0; i < lines.length; i++) {
        var lw = measureW(lines[i], 58, 900, POSTER);
        var pw = Math.min(900, Math.round(lw + 52));
        var ly = i * 86;
        svg += '<rect x="' + (-pw / 2) + '" y="' + (ly - 38) + '" width="' + pw + '" height="76" rx="12" fill="#09090B" fill-opacity="0.96"/>'
          + '<text x="0" y="' + (ly + 19) + '" text-anchor="middle" font-family="' + POSTER + '" font-size="58" font-weight="900" letter-spacing="1.5" fill="#FFFFFF">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD = up + '@' + Math.round(sc * 40);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return kicker + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 1340, w: 900, h: 180 }]; };
})();
