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

  var CINEMA = "'ACBarlowLight', 'Helvetica Neue', Arial, sans-serif";
  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);

    var mStart = (moment && moment.start) || 0;
    var mEnd = (moment && moment.end) || (mStart + 2.0);
    var mDur = Math.max(0.4, mEnd - mStart);
    var mAge = Math.max(0, t - mStart);

    // Pure black cinema letterbox bars (top 0..420, bottom 1500..1920) — zero face occlusion ever!
    var svg = '<rect x="0" y="0" width="1080" height="420" fill="#040406"/>'
      + '<rect x="0" y="1500" width="1080" height="420" fill="#040406"/>';

    var capD = '';
    if (raw) {
      var words = raw.split(/\s+/).filter(Boolean);
      var fsz = 76;
      // Tight poetic editorial stack (2-3 words per line, matching #15 "Doubt / is loud.")
      var lines = wrapLines(raw, 640, fsz, 300, CINEMA, 2);
      var y0 = lines.length === 1 ? 1652 : 1612;
      // Progressive word-by-word reveal timed across 72% of cue duration
      var step = Math.min(0.26, (mDur * 0.72) / Math.max(1, words.length));
      var wIdx = 0;
      var visSig = [];
      for (var i = 0; i < lines.length; i++) {
        var lnWords = lines[i].split(/\s+/);
        var xCur = 92;
        var yLine = y0 + i * 82;
        for (var j = 0; j < lnWords.length; j++) {
          var w = lnWords[j];
          var wAge = mAge - wIdx * step;
          if (wAge > 0) {
            var wp = easeOutQuint(wAge / 0.24);
            var dy = (1 - wp) * 7;
            var op = (0.96 * wp).toFixed(2);
            svg += '<text x="' + xCur + '" y="' + (yLine + dy).toFixed(1) + '" font-family="' + CINEMA + '" font-size="' + fsz + '" font-weight="300" letter-spacing="0.5" fill="#F4F4F5" opacity="' + op + '">' + esc(w) + '</text>';
            visSig.push(wIdx + ':' + Math.round(wp * 10));
          }
          xCur += Math.round(measureW(w + ' ', fsz, 300, CINEMA));
          wIdx++;
        }
      }
      capD = raw + '@' + visSig.join(',');
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 92, y: 1545, w: 720, h: 190 }]; };
})();
