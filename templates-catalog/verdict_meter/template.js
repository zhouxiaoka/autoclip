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
    var activeTier = Math.min(2, mIdx % 3);

    var tiers = [
      { label: 'HURTS', col: '#EF4444' },
      { label: 'NO EFFECT', col: '#A1A1AA' },
      { label: 'PROVEN', col: '#22C55E' }
    ];

    var svg = '<defs><filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000" flood-opacity="0.58"/></filter></defs>';

    // Top 3-tier verdict bar (y=175..265) above speaker's head
    var title = ((state.title_lines || [])[0] || 'TESTED VERDICT').toUpperCase();
    svg += '<g transform="translate(540,218)" filter="url(#sh)">'
      + '<rect x="-420" y="-58" width="840" height="116" rx="22" fill="#0F1117" fill-opacity="0.86" stroke="rgba(255,255,255,0.16)" stroke-width="2"/>'
      + '<text x="0" y="-22" text-anchor="middle" font-family="' + SANS + '" font-size="22" font-weight="700" letter-spacing="2.5" fill="#9CA3AF">' + esc(title) + '</text>';
    var xs = [-265, 0, 265];
    for (var ti = 0; ti < 3; ti++) {
      var act = (ti === activeTier);
      var fill = act ? tiers[ti].col : '#1F2430';
      var tCol = act ? '#09090B' : '#71717A';
      var sc = act ? (0.94 + 0.06 * spring(Math.max(0, t - momentStart(moment)), 0.22)) : 1.0;
      svg += '<g transform="translate(' + xs[ti] + ',22) scale(' + sc.toFixed(3) + ')">'
        + '<rect x="-118" y="-24" width="236" height="48" rx="12" fill="' + fill + '"/>'
        + '<text x="0" y="9" text-anchor="middle" font-family="' + SANS + '" font-size="24" font-weight="700" letter-spacing="1.2" fill="' + tCol + '">' + tiers[ti].label + '</text></g>';
    }
    svg += '</g>';

    var capD = 'V:' + activeTier;
    if (raw) {
      var mAge = Math.max(0, t - momentStart(moment));
      var sp = 0.90 + 0.10 * spring(mAge, 0.22);
      var lines = wrapLines(raw, 880, 58, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1420 : 1385;
      svg += '<g transform="translate(540,' + y0 + ') scale(' + sp.toFixed(3) + ')">';
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="0" y="' + (i * 72) + '" text-anchor="middle" font-family="' + SANS + '" font-size="58" font-weight="700" letter-spacing="-0.6" fill="#FFFFFF" stroke="#000000" stroke-width="10" paint-order="stroke" stroke-linejoin="round">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD += '|' + raw + '@' + Math.round(sp * 30);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 120, y: 160, w: 840, h: 116 }, { slot: 'caption', x: 90, y: 1330, w: 900, h: 160 }]; };
})();
