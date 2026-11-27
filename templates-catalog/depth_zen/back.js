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
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    if (!raw) {
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"></svg>';
      return 'ZEN_B_IDLE';
    }
    var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
    var mEnd = (moment && (moment.t1 != null ? moment.t1 : moment.end)) || (mStart + 2.4);
    var mAge = Math.max(0, t - mStart);
    var mRem = Math.max(0, mEnd - t);
    var inP = easeOutQuint(mAge / 0.36);
    var outP = mRem < 0.28 ? easeOutCubic(mRem / 0.28) : 1.0;
    var op = Math.min(inP, outP);
    if (op <= 0.02) {
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"></svg>';
      return 'ZEN_B_GAP';
    }

    var words = raw.split(/\s+/).filter(Boolean);
    var fIdx = pickFocalIndex(words);
    var hero = (words[fIdx] || words[0] || 'PATIENCE').replace(/[^A-Za-z0-9\-']/g, '').toUpperCase();
    var sz = 195;
    var w = measureW(hero, sz, 400, SERIF);
    if (w > 960) sz = Math.max(110, Math.floor((sz * 960) / w));
    var dy = (1 - inP) * 28 - (1 - outP) * 18;
    var svg = '<g transform="translate(540,' + (520 + dy).toFixed(1) + ')" opacity="' + (0.94 * op).toFixed(2) + '">'
      + '<text x="0" y="0" text-anchor="middle" font-family="' + SERIF + '" font-size="' + sz + '" font-weight="400" letter-spacing="2" fill="#F5F0E6">' + esc(hero) + '</text></g>';
    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return 'ZEN_B:' + hero + ':' + Math.round(op * 25) + ':' + Math.round(dy);
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 50, y: 340, w: 980, h: 240 }]; };
})();
