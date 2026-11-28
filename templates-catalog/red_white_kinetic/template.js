(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";
  var SERIF = "'ACInstrument', Georgia, serif";
  var SCRIPT = "'ACPinyon', 'ACInstrument', cursive";
  var HAND = "'ACCaveat', cursive";

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
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1, this:1, just:1 };
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
    var list = (window.ACTemplate && window.ACTemplate.moments) ? window.ACTemplate.moments(state) : ((state && state.moments) || []);
    var idx = 0;
    for (var i = 0; i < list.length; i++) {
      var a = list[i].t0 != null ? list[i].t0 : list[i].start;
      var b = list[i].t1 != null ? list[i].t1 : list[i].end;
      if (t >= a && t < b) idx = i;
    }
    return idx;
  }
  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var mIdx = momentIndex(t);

    var svg = '<defs>'
      + '<linearGradient id="bs" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.62"/></linearGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity="0.78"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="1160" width="1080" height="760" fill="url(#bs)"/>';

    var capD = '';
    if (raw) {
      var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
      var mAge = Math.max(0, t - mStart);
      var words = raw.toUpperCase().split(/\s+/).filter(Boolean);
      var focalIdx = pickFocalIndex(words);
      var focalWord = words[focalIdx] || words[0];
      var beforeWords = words.slice(0, focalIdx).join(' ');
      var afterWords = words.slice(focalIdx + 1).join(' ');

      // Alternate accent/white hero polarity on every cue!
      var vars = state.vars || {};
      var accent = (typeof vars.accent_color === 'string' && vars.accent_color) ? vars.accent_color : '#EF4444';
      var scaleMap = { S: 0.86, M: 1.0, L: 1.15 };
      var fScale = scaleMap[String(vars.font_scale || 'M').toUpperCase()] || 1.0;
      var heroRed = (mIdx % 2 === 0);
      var heroFill = heroRed ? accent : '#FFFFFF';
      var subFill = heroRed ? '#FFFFFF' : accent;

      var pTop = easeOutQuint(mAge / 0.20);
      var pHero = spring(Math.max(0, mAge - 0.05), 0.25);
      var pBot = easeOutQuint(Math.max(0, mAge - 0.12) / 0.22);
      var heroSc = 0.74 + 0.26 * pHero;

      if (beforeWords) {
        var bsz = Math.round(52 * fScale);
        var bw = measureW(beforeWords, bsz, 700, SANS);
        if (bw > 900) bsz = Math.max(36, Math.floor((bsz * 900) / bw));
        svg += '<g transform="translate(540,' + (1316 + (1 - pTop) * 18).toFixed(1) + ')" opacity="' + pTop.toFixed(2) + '" filter="url(#sh)">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + bsz + '" font-weight="700" letter-spacing="1" fill="' + subFill + '" stroke="#000" stroke-width="5" paint-order="stroke">' + esc(beforeWords) + '</text></g>';
      }

      var hsz = Math.round(132 * fScale);
      var hw = measureW(focalWord, hsz, 400, POSTER);
      if (hw > 900) hsz = Math.max(76, Math.floor((hsz * 900) / hw));
      svg += '<g transform="translate(540,1438) scale(' + heroSc.toFixed(3) + ')" opacity="' + easeOutCubic(Math.max(0, mAge - 0.03) / 0.14).toFixed(2) + '" filter="url(#sh)">'
        + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + hsz + '" letter-spacing="2" fill="' + heroFill + '" stroke="#000" stroke-width="8" paint-order="stroke">' + esc(focalWord) + '</text></g>';

      if (afterWords) {
        var asz = Math.round(52 * fScale);
        var aw = measureW(afterWords, asz, 700, SANS);
        if (aw > 900) asz = Math.max(36, Math.floor((asz * 900) / aw));
        svg += '<g transform="translate(540,' + (1516 + (1 - pBot) * 16).toFixed(1) + ')" opacity="' + pBot.toFixed(2) + '" filter="url(#sh)">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + asz + '" font-weight="700" letter-spacing="1" fill="' + subFill + '" stroke="#000" stroke-width="5" paint-order="stroke">' + esc(afterWords) + '</text></g>';
      }

      capD = (heroRed ? 'R:' : 'W:') + raw + '@' + Math.round(heroSc * 35);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 70, y: 1255, w: 940, h: 290 }]; };
})();
