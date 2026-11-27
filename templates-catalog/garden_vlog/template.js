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
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000" flood-opacity="0.45"/></filter>'
      + '</defs>';

    var capD = '';
    if (raw) {
      var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
      var mAge = Math.max(0, t - mStart);
      var words = raw.toLowerCase().split(/\s+/).filter(Boolean);
      var p1 = easeOutQuint(mAge / 0.24);
      var p2 = spring(Math.max(0, mAge - 0.10), 0.28);
      // Gentle organic hand-drawn jitter (deterministic sine, zero Math.random!)
      var jRot = Math.sin(t * 7.5 + mIdx) * 1.4;
      var jDy = Math.cos(t * 6.0 + mIdx) * 2.2;

      // Alternate between (A) solid top + hollow bubbly word below, and (B) full hollow bubbly line — exact #01 rhythm!
      var isAllHollow = (mIdx % 2 === 1);
      if (!isAllHollow && words.length >= 2) {
        var topPhrase = words.slice(0, Math.max(1, words.length - 1)).join(' ');
        var hollowWord = words[words.length - 1];
        var szTop = 82;
        var wtTop = measureW(topPhrase, szTop, 700, SANS);
        if (wtTop > 900) szTop = Math.max(52, Math.floor((szTop * 900) / wtTop));

        svg += '<g transform="translate(540,' + (248 + (1 - p1) * 16).toFixed(1) + ')" opacity="' + p1.toFixed(2) + '" filter="url(#sh)">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + szTop + '" font-weight="700" letter-spacing="-1.5" fill="#FFFFFF">' + esc(topPhrase) + '</text></g>';

        var szH = 104;
        var wh = measureW(hollowWord, szH, 700, SANS);
        if (wh > 840) szH = Math.max(66, Math.floor((szH * 840) / wh));
        var scH = 0.80 + 0.20 * p2;
        svg += '<g transform="translate(540,' + (348 + jDy).toFixed(1) + ') rotate(' + jRot.toFixed(2) + ') scale(' + scH.toFixed(3) + ')" opacity="' + easeOutCubic(Math.max(0, mAge - 0.08) / 0.16).toFixed(2) + '" filter="url(#sh)">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + szH + '" font-weight="700" letter-spacing="2" fill="rgba(255,255,255,0.08)" stroke="#FFFFFF" stroke-width="3.6" stroke-linejoin="round">' + esc(hollowWord) + '</text>'
          + '<path d="M ' + (Math.round(wh/2) + 22) + ' -58 l 8 -14 M ' + (Math.round(wh/2) + 34) + ' -38 l 14 -6 M ' + (-Math.round(wh/2) - 24) + ' -52 l -10 -12" stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round" fill="none"/>'
          + '</g>';
        capD = 'MIX:' + topPhrase + '/' + hollowWord + '@' + Math.round(scH * 30) + ':' + Math.round(jRot * 5);
      } else {
        var line = words.join(' ');
        var szA = 96;
        var wa = measureW(line, szA, 700, SANS);
        if (wa > 900) szA = Math.max(58, Math.floor((szA * 900) / wa));
        var scA = 0.84 + 0.16 * spring(mAge, 0.26);
        svg += '<g transform="translate(540,' + (286 + jDy).toFixed(1) + ') rotate(' + jRot.toFixed(2) + ') scale(' + scA.toFixed(3) + ')" opacity="' + p1.toFixed(2) + '" filter="url(#sh)">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + SANS + '" font-size="' + szA + '" font-weight="700" letter-spacing="2" fill="rgba(255,255,255,0.08)" stroke="#FFFFFF" stroke-width="3.6" stroke-linejoin="round">' + esc(line) + '</text>'
          + '<path d="M ' + (-Math.round(wa/2) - 18) + ' -52 q 6 -12 16 -8 M ' + (Math.round(wa/2) + 18) + ' -48 l 10 -10 M ' + (Math.round(wa/2) + 24) + ' -28 l 12 -2" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" fill="none"/>'
          + '</g>';
        capD = 'HOL:' + line + '@' + Math.round(scA * 30) + ':' + Math.round(jRot * 5);
      }
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 80, y: 170, w: 920, h: 220 }]; };
})();
