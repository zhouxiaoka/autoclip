(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";
  var SERIF = "'ACInstrument', Georgia, serif";
  var PLAYFAIR = "'ACPlayfair', Georgia, serif";

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutQuint(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 5); }
  function easeOutCubic(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 3); }
  function spring(age, dur) {
    var p = clamp01(age / (dur || 0.28));
    if (p >= 1) return 1;
    // Critically slightly underdamped silky spring
    return 1 - Math.exp(-7.5 * p) * Math.cos(9.5 * p);
  }
  function measureW(text, sz, weight, family, italic) {
    mctx.font = (italic ? 'italic ' : '') + (weight || 700) + ' ' + sz + 'px ' + (family || SANS);
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
  function pickFocalIndex(words) {
    // Pick the strongest focal word (number first, else longest non-stopword)
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1 };
    for (var i = 0; i < words.length; i++) {
      if (/\d/.test(words[i])) return i;
    }
    var best = Math.max(0, words.length - 1), bestLen = -1;
    for (var j = 0; j < words.length; j++) {
      var clean = words[j].toLowerCase().replace(/[^a-z0-9]/g, '');
      if (clean.length > bestLen && !stops[clean]) {
        bestLen = clean.length;
        best = j;
      }
    }
    return best;
  }
  function wrapLines(text, maxW, sz, weight, family, maxLines) {
    var words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var lines = [], cur = words[0];
    for (var i = 1; i < words.length; i++) {
      var cand = cur + ' ' + words[i];
      if (measureW(cand, sz, weight, family) <= maxW) {
        cur = cand;
      } else {
        lines.push(cur);
        cur = words[i];
        if (maxLines && lines.length >= maxLines - 1) {
          lines.push(words.slice(i).join(' '));
          return lines;
        }
      }
    }
    lines.push(cur);
    return lines;
  }
  function momentIndex(t) {
    var list = (state && (state.timeline || state.moments)) || [];
    for (var i = 0; i < list.length; i++) {
      if (t >= list[i].start && t < list[i].end) return i;
    }
    return 0;
  }
  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var kicker = (state.kicker || '').trim();

    var mStart = (moment && moment.start) || 0;
    var mAge = Math.max(0, t - mStart);
    var p = easeOutQuint(mAge / 0.34);
    var blurVal = Math.max(0, (1 - p) * 6.5);

    var svg = '<defs>'
      + '<filter id="bl" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur in="SourceGraphic" stdDeviation="' + blurVal.toFixed(2) + '"/></filter>'
      + '</defs>';

    // Pure black cinema letterbox bars (top 0..420, bottom 1500..1920) — zero face occlusion ever!
    svg += '<rect x="0" y="0" width="1080" height="420" fill="#050507"/>'
      + '<rect x="0" y="1500" width="1080" height="420" fill="#050507"/>';

    if (kicker) {
      svg += '<text x="86" y="372" font-family="' + SANS + '" font-size="22" font-weight="500" letter-spacing="4" fill="#71717A">' + esc(kicker.toUpperCase()) + '</text>';
    }

    var capD = '';
    if (raw) {
      var words = raw.split(/\s+/).filter(Boolean);
      var focalIdx = pickFocalIndex(words);
      var lines = wrapLines(raw, 880, 48, 500, SANS, 2);
      var y0 = 1625;
      svg += '<g transform="translate(0,' + ((1 - p) * 16).toFixed(1) + ')" opacity="' + (0.94 * p).toFixed(2) + '" filter="url(#bl)">';
      for (var i = 0; i < lines.length; i++) {
        var lnWords = lines[i].split(/\s+/);
        var xCur = 86;
        var yLine = y0 + i * 68;
        for (var j = 0; j < lnWords.length; j++) {
          var w = lnWords[j];
          var isFocal = w.toLowerCase() === (words[focalIdx] || '').toLowerCase();
          var fill = isFocal ? '#FFFFFF' : '#A1A1AA';
          var wt = isFocal ? 700 : 400;
          svg += '<text x="' + xCur + '" y="' + yLine + '" font-family="' + SANS + '" font-size="48" font-weight="' + wt + '" fill="' + fill + '">' + esc(w) + '</text>';
          xCur += Math.round(measureW(w + ' ', 48, wt, SANS));
        }
      }
      svg += '</g>';
      capD = raw + '@' + Math.round(p * 20);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 86, y: 1550, w: 900, h: 160 }]; };
})();
