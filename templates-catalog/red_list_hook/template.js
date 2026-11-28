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
    var mIdx = momentIndex(t);
    var titleLines = (state.title_lines || []).filter(Boolean);
    if (!titleLines.length) titleLines = ['5 Lessons That', 'Actually Work'];

    var svg = '<defs>'
      + '<linearGradient id="topSc" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0.62"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></linearGradient>'
      + '<linearGradient id="botSc" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.68"/></linearGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="10" flood-color="#000" flood-opacity="0.72"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="0" width="1080" height="380" fill="url(#topSc)"/>'
      + '<rect x="0" y="1180" width="1080" height="740" fill="url(#botSc)"/>';

    // Top persistent crisp 2-line white title above head
    for (var ti = 0; ti < Math.min(2, titleLines.length); ti++) {
      var tsz = ti === 0 ? 58 : 38;
      var tw = measureW(titleLines[ti], tsz, 700, SANS);
      if (tw > 880) tsz = Math.max(28, Math.floor((tsz * 880) / tw));
      svg += '<text x="540" y="' + (195 + ti * 58) + '" text-anchor="middle" font-family="' + SANS + '" font-size="' + tsz + '" font-weight="700" letter-spacing="-0.8" fill="#FFFFFF" filter="url(#sh)">' + esc(titleLines[ti]) + '</text>';
    }

    // Face-safe lower-third: Crimson #1/#2/#3 on left + crisp uppercase stacked text on right
    var capD = '';
    if (raw) {
      var mStart = (moment && moment.start) || 0;
      var mAge = Math.max(0, t - mStart);
      var numSc = 0.78 + 0.22 * spring(mAge, 0.24);
      var txtP = easeOutQuint(mAge / 0.24);
      var numMatch = raw.match(/^\s*#?(\d+)[\.\)\:\-]\s*/);
      var itemNum = '#' + (numMatch ? numMatch[1] : (mIdx + 1));
      var cleanRaw = numMatch ? raw.replace(/^\s*#?(\d+)[\.\)\:\-]\s*/, '') : raw;

      svg += '<g transform="translate(152,1368) scale(' + numSc.toFixed(3) + ')" filter="url(#sh)">'
        + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="112" fill="#DC2626">' + itemNum + '</text></g>';

      var up = cleanRaw.toUpperCase();
      var lines = wrapLines(up, 690, 44, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1352 : 1322;
      svg += '<g transform="translate(' + ((1 - txtP) * 24).toFixed(1) + ',0)" opacity="' + txtP.toFixed(2) + '" filter="url(#sh)">';
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="258" y="' + (y0 + i * 56) + '" font-family="' + SANS + '" font-size="44" font-weight="700" letter-spacing="0.5" fill="#FFFFFF">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD = itemNum + ':' + up + '@' + Math.round(numSc * 40);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 90, y: 140, w: 900, h: 140 }, { slot: 'caption', x: 80, y: 1260, w: 920, h: 170 }]; };
})();
