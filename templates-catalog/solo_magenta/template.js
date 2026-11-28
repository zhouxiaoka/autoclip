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
    var titleWords = ((state.title_lines || []).join(' ').trim() || 'NOBODY YOURSELF').split(/\s+/).filter(Boolean);

    var svg = '<defs>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="12" flood-color="#000" flood-opacity="0.62"/></filter>'
      + '</defs>';

    // Full-screen magenta beat card (0.0..0.72s) — pure code rhythm cut!
    if (t < 0.72) {
      var word = (titleWords.filter(function (w) { return /[A-Za-z]{3,}/.test(w); })[0] || titleWords[0] || 'NOBODY').toUpperCase();
      var sc = 0.86 + 0.14 * spring(t, 0.24);
      var sz = 136;
      var ww = measureW(word, sz, 700, SANS);
      if (ww > 920) sz = Math.max(72, Math.floor((sz * 920) / ww));
      svg += '<rect x="0" y="0" width="1080" height="1920" fill="#E60099"/>'
        + '<g transform="translate(540,985) scale(' + sc.toFixed(3) + ')">'
        + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + sz + '" font-weight="700" letter-spacing="-2" fill="#FFFFFF">' + esc(word) + '</text></g>';
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
      return 'MAG:' + word + ':' + Math.round(sc * 40);
    }

    // Face-safe lower-third mixed-size kinetic caption (small context phrase above + 1.65x bold focal word below)
    var capD = '';
    if (raw) {
      var mStart = (moment && moment.start) || 0;
      var mAge = Math.max(0, t - mStart);
      var words = raw.split(/\s+/).filter(Boolean);
      var focalIdx = pickFocalIndex(words);
      var focalWord = words[focalIdx] || words[0];
      var contextWords = words.filter(function (_w, idx) { return idx !== focalIdx; }).join(' ');

      var pCtx = easeOutQuint(mAge / 0.26);
      var pFoc = spring(Math.max(0, mAge - 0.05), 0.26);
      var focScale = 0.84 + 0.16 * pFoc;

      // Subtle lower scrim so white text pops cleanly on bright clothes/desks
      svg += '<linearGradient id="ls" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.52"/></linearGradient>'
        + '<rect x="0" y="1220" width="1080" height="700" fill="url(#ls)"/>';

      if (contextWords) {
        svg += '<g transform="translate(0,' + ((1 - pCtx) * 14).toFixed(1) + ')" opacity="' + pCtx.toFixed(2) + '">'
          + '<text x="540" y="1355" text-anchor="middle" font-family="' + SANS + '" font-size="34" font-weight="500" fill="#FFFFFF" fill-opacity="0.88" filter="url(#sh)">' + esc(contextWords) + '</text></g>';
      }
      var fsz = 86;
      var fw = measureW(focalWord, fsz, 700, SANS);
      if (fw > 860) fsz = Math.max(54, Math.floor((fsz * 860) / fw));
      svg += '<g transform="translate(540,1448) scale(' + focScale.toFixed(3) + ')" opacity="' + easeOutCubic(mAge / 0.16).toFixed(2) + '">'
        + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + fsz + '" font-weight="700" letter-spacing="-1.5" fill="#FFFFFF" filter="url(#sh)">' + esc(focalWord) + '</text></g>';
      capD = raw + '@' + Math.round(focScale * 40);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 1310, w: 900, h: 170 }]; };
})();
