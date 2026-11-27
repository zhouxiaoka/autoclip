(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";

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
  function pickFocalIndex(words) {
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1, this:1, just:1 };
    for (var i = 0; i < words.length; i++) if (/\d/.test(words[i])) return i;
    var best = Math.max(0, words.length - 1), bestLen = -1;
    for (var j = 0; j < words.length; j++) {
      var clean = words[j].toLowerCase().replace(/[^a-z0-9]/g, '');
      if (clean.length > bestLen && !stops[clean]) { bestLen = clean.length; best = j; }
    }
    return best;
  }
  function momentIndex(t) {
    var list = (window.ACTemplate && window.ACTemplate.moments) ? window.ACTemplate.moments(state) : [];
    var idx = 0;
    for (var i = 0; i < list.length; i++) {
      var a = list[i].t0 != null ? list[i].t0 : list[i].start;
      var b = list[i].t1 != null ? list[i].t1 : list[i].end;
      if (t >= a && t < b) idx = i;
    }
    return idx;
  }
  function momentStart(m) { return (m && (m.t0 != null ? m.t0 : m.start)) || 0; }
  function momentEnd(m) { return (m && (m.t1 != null ? m.t1 : m.end)) || (momentStart(m) + 2.4); }
  function wrapLines(text, maxW, sz, weight, family, maxLines) {
    var words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var lines = [], cur = words[0];
    for (var i = 1; i < words.length; i++) {
      var cand = cur + ' ' + words[i];
      if (measureW(cand, sz, weight, family) <= maxW) cur = cand;
      else {
        lines.push(cur); cur = words[i];
        if (maxLines && lines.length >= maxLines - 1) { lines.push(words.slice(i).join(' ')); return lines; }
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
    var mIdx = momentIndex(t);
    var col = (mIdx % 2 === 0) ? '#22D3EE' : '#F43F5E';

    // Subtle cyber grid + radial neon halo behind speaker (always breathes gently behind person!)
    var pulse = 0.86 + 0.14 * Math.sin(t * 3.5);
    var svg = '<defs>'
      + '<radialGradient id="ng" cx="50%" cy="32%" r="48%"><stop offset="0%" stop-color="' + col + '" stop-opacity="' + (0.48 * pulse).toFixed(2) + '"/><stop offset="65%" stop-color="' + col + '" stop-opacity="0.10"/><stop offset="100%" stop-color="' + col + '" stop-opacity="0"/></radialGradient>'
      + '<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="12" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
      + '</defs>';

    svg += '<rect x="0" y="0" width="1080" height="1200" fill="url(#ng)"/>';
    // Minimal hairline perspective grid behind crown
    for (var gx = 120; gx <= 960; gx += 120) {
      svg += '<line x1="' + gx + '" y1="140" x2="' + gx + '" y2="760" stroke="' + col + '" stroke-opacity="0.14" stroke-width="1.5"/>';
    }
    for (var gy = 180; gy <= 720; gy += 108) {
      svg += '<line x1="80" y1="' + gy + '" x2="1000" y2="' + gy + '" stroke="' + col + '" stroke-opacity="0.14" stroke-width="1.5"/>';
    }

    var sig = 'NG:' + mIdx + ':' + Math.round(pulse * 10);
    if (raw) {
      var mAge = Math.max(0, t - momentStart(moment));
      var mRem = Math.max(0, momentEnd(moment) - t);
      var inP = spring(mAge, 0.28);
      var outP = mRem < 0.24 ? easeOutCubic(mRem / 0.24) : 1.0;
      var vis = Math.min(easeOutCubic(mAge / 0.14), outP);
      if (vis > 0.02) {
        var words = raw.split(/\s+/).filter(Boolean);
        var fIdx = pickFocalIndex(words);
        var word = (words[fIdx] || words[0]).replace(/[^A-Za-z0-9\-]/g, '').toUpperCase() || 'FUTURE';
        var sz = 240;
        var ww = measureW(word, sz, 400, POSTER);
        if (ww > 960) sz = Math.max(125, Math.floor((sz * 960) / ww));
        var sc = (0.86 + 0.14 * inP) * (0.94 + 0.06 * outP);
        var dy = (1 - easeOutQuint(mAge / 0.28)) * 45 + (1 - outP) * 28;
        svg += '<g transform="translate(540,' + (505 + dy).toFixed(1) + ') scale(' + sc.toFixed(3) + ')" opacity="' + (0.95 * vis).toFixed(2) + '" filter="url(#glow)">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + sz + '" letter-spacing="5" fill="' + col + '">' + esc(word) + '</text></g>';
        sig += ':' + word + ':' + Math.round(vis * 25);
      }
    }
    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return sig;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 40, y: 240, w: 1000, h: 320 }]; };
})();
