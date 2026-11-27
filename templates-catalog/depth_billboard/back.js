(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";
  var SERIF = "'ACInstrument', Georgia, serif";
  var SERIF_I = "'ACInstrumentItalic', 'ACInstrument', Georgia, serif";

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
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1 };
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
  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lines = (state.title_lines || []).filter(Boolean);
    var hero = (lines[0] || 'FOCUS').toUpperCase();
    var sub = (lines[1] || '').toUpperCase();
    var p = spring(t, 0.42);
    var sc = 0.88 + 0.12 * p;
    var dy = (1 - easeOutQuint(t / 0.40)) * 45;

    var sz = 250;
    var w = measureW(hero, sz, 400, POSTER);
    if (w > 980) sz = Math.max(140, Math.floor((sz * 980) / w));

    var svg = '<defs><filter id="bsh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#000" flood-opacity="0.45"/></filter></defs>';
    // Crown-level depth band (y=340): top 80% of letters stay crisp & readable while hair/head overlaps the lower edge!
    svg += '<g transform="translate(540,' + (340 + dy).toFixed(1) + ') scale(' + sc.toFixed(3) + ')" opacity="' + easeOutCubic(t / 0.25).toFixed(2) + '" filter="url(#bsh)">'
      + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + sz + '" letter-spacing="4" fill="#F8FAFC" fill-opacity="0.96">' + esc(hero) + '</text>';
    if (sub) {
      var ssz = 165;
      var sw = measureW(sub, ssz, 400, POSTER);
      if (sw > 980) ssz = Math.max(100, Math.floor((ssz * 980) / sw));
      svg += '<text x="0" y="' + Math.round(sz * 0.72) + '" text-anchor="middle" font-family="' + POSTER + '" font-size="' + ssz + '" letter-spacing="4" fill="#EF4444" fill-opacity="0.96">' + esc(sub) + '</text>';
    }
    svg += '</g>';
    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return 'BACK:' + hero + ':' + Math.round(sc * 40);
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 30, y: 320, w: 1020, h: 480 }]; };
})();
