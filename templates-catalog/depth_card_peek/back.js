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
    var lines = (state.title_lines || []).filter(Boolean);
    var metric = lines[0] || '+240% ARR';
    var sub = lines[1] || '90-Day Organic Growth';
    var kicker = (state.kicker || 'LIVE METRIC').toUpperCase();

    // Card peeks smoothly up from behind the speaker's crown/shoulders (0.2s..6.8s) then tucks cleanly back down!
    var inP = spring(Math.max(0, t - 0.15), 0.42);
    var outP = t > 6.8 ? easeOutCubic(Math.max(0, 7.6 - t) / 0.8) : 1.0;
    var vis = Math.min(easeOutCubic(Math.max(0, t - 0.1) / 0.25), outP);
    if (vis <= 0.02) {
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"></svg>';
      return 'CARD_B_IDLE';
    }
    var lineP = easeOutCubic(Math.max(0, t - 0.35) / 1.4);
    var dashOff = Math.round(320 * (1 - lineP));
    var dy = (1 - easeOutQuint(Math.max(0, t - 0.15) / 0.42)) * 90 + (1 - outP) * 70;
    var sc = 0.92 + 0.08 * inP;

    // Positioned at y=360 (top 75% crystal clear above head, lower 25% naturally tucked behind hair/shoulders!)
    var svg = '<defs><filter id="csh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="14" stdDeviation="20" flood-color="#000" flood-opacity="0.58"/></filter></defs>'
      + '<g transform="translate(540,' + (365 + dy).toFixed(1) + ') scale(' + sc.toFixed(3) + ')" opacity="' + vis.toFixed(2) + '" filter="url(#csh)">'
      + '<rect x="-430" y="-130" width="860" height="260" rx="28" fill="#0B0F19" fill-opacity="0.92" stroke="rgba(52,211,153,0.45)" stroke-width="2.5"/>'
      + '<circle cx="-376" cy="-76" r="8" fill="#10B981"/>'
      + '<text x="-356" y="-68" font-family="' + SANS + '" font-size="24" font-weight="700" letter-spacing="2.5" fill="#6EE7B7">' + esc(kicker) + '</text>'
      + '<text x="-382" y="2" font-family="' + SANS + '" font-size="68" font-weight="700" letter-spacing="-1.5" fill="#FFFFFF">' + esc(metric) + '</text>'
      + '<text x="-382" y="48" font-family="' + SANS + '" font-size="26" font-weight="500" fill="#94A3B8">' + esc(sub) + '</text>'
      + '<polyline points="90,56 155,34 215,44 285,-12 375,-68" fill="none" stroke="#10B981" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="320" stroke-dashoffset="' + dashOff + '"/>'
      + '<circle cx="375" cy="-68" r="9" fill="#34D399" opacity="' + (lineP > 0.9 ? '1' : '0') + '"/>'
      + '</g>';
    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return 'CPB:' + Math.round(vis * 25) + ':' + Math.round(lineP * 25) + ':' + Math.round(dy);
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 110, y: 230, w: 860, h: 270 }]; };
})();
