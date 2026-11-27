(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";
  var PLAYFAIR = "'ACPlayfair', Georgia, serif";
  var PLAYFAIR_I = "'ACPlayfairItalic', 'ACPlayfair', Georgia, serif";

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
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1, this:1, just:1, how:1 };
    for (var i = 0; i < words.length; i++) if (/\d/.test(words[i])) return i;
    var best = Math.max(0, words.length - 1), bestLen = -1;
    for (var j = 0; j < words.length; j++) {
      var clean = words[j].toLowerCase().replace(/[^a-z0-9]/g, '');
      if (clean.length > bestLen && !stops[clean]) { bestLen = clean.length; best = j; }
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
    var list = (window.ACTemplate && window.ACTemplate.moments) ? window.ACTemplate.moments(state) : [];
    var idx = 0;
    for (var i = 0; i < list.length; i++) {
      var a = list[i].t0 != null ? list[i].t0 : list[i].start;
      var b = list[i].t1 != null ? list[i].t1 : list[i].end;
      if (t >= a && t < b) idx = i;
    }
    return idx;
  }
  function momentStart(moment) {
    return (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
  }
  function momentEnd(moment) {
    return (moment && (moment.t1 != null ? moment.t1 : moment.end)) || (momentStart(moment) + 2.0);
  }
  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var mIdx = momentIndex(t);

    var svg = '<defs><filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000" flood-opacity="0.72"/></filter></defs>';

    var capD = 'SHOUT_IDLE';
    if (raw) {
      var mAge = Math.max(0, t - momentStart(moment));
      var words = raw.toUpperCase().split(/\s+/).filter(Boolean);
      var fIdx = pickFocalIndex(words);
      var bigWord = (words[fIdx] || words[0]).replace(/[^A-Z0-9\-\?\!]/g, '') || words[0];

      var scBig = 0.78 + 0.22 * spring(mAge, 0.24);
      var pBar = easeOutQuint(Math.max(0, mAge - 0.05) / 0.22);

      // Dynamic giant pure-white word (strictly face-safe at y=1355!)
      var bsz = 136;
      var bw = measureW(bigWord, bsz, 400, POSTER);
      if (bw > 900) bsz = Math.max(76, Math.floor((bsz * 900) / bw));
      svg += '<g transform="translate(540,1360) scale(' + scBig.toFixed(3) + ')" opacity="' + easeOutCubic(mAge / 0.14).toFixed(2) + '" filter="url(#sh)">'
        + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + bsz + '" letter-spacing="2" fill="#FFFFFF" stroke="#000000" stroke-width="6" paint-order="stroke">' + esc(bigWord) + '</text></g>';

      // Tight black subtitle bar right beneath it (y=1432)
      var fullLine = words.join(' ');
      var ssz = 36;
      var sw = measureW(fullLine, ssz, 700, SANS);
      if (sw > 840) ssz = Math.max(26, Math.floor((ssz * 840) / sw));
      sw = measureW(fullLine, ssz, 700, SANS);
      var pillW = Math.min(920, Math.round(sw + 44));
      svg += '<g transform="translate(540,' + (1436 + (1 - pBar) * 14).toFixed(1) + ')" opacity="' + pBar.toFixed(2) + '" filter="url(#sh)">'
        + '<rect x="' + (-pillW/2) + '" y="-32" width="' + pillW + '" height="64" rx="10" fill="#09090B" fill-opacity="0.92"/>'
        + '<text x="0" y="12" text-anchor="middle" font-family="' + SANS + '" font-size="' + ssz + '" font-weight="700" letter-spacing="1" fill="#FFFFFF">' + esc(fullLine) + '</text></g>';
      capD = 'W' + mIdx + ':' + bigWord + '@' + Math.round(scBig * 30);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 80, y: 1245, w: 920, h: 245 }]; };
})();
