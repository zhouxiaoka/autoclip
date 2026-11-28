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
    var titleLines = (state.title_lines || []).filter(Boolean);
    var mainTitle = titleLines[0] || 'Strawberries';
    var scriptSub = titleLines[1] || 'dark chocolate';
    var kicker = (state.kicker || 'editorial').trim().toLowerCase();

    var svg = '<defs>'
      + '<linearGradient id="ts" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0.52"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></linearGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="6" flood-color="#000" flood-opacity="0.58"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="0" width="1080" height="420" fill="url(#ts)"/>';

    // Tiny corner editorial meta labels (matching #37 "snack combos" | "food")
    svg += '<text x="64" y="138" font-family="' + SANS + '" font-size="22" font-weight="400" fill="#FFFFFF" fill-opacity="0.72">' + esc(kicker) + '</text>'
      + '<text x="1016" y="138" text-anchor="end" font-family="' + SANS + '" font-size="22" font-weight="400" fill="#FFFFFF" fill-opacity="0.72">guide</text>';

    // Giant condensed Instrument Serif headline + overlapping Pinyon Script cursive below
    var hP = easeOutQuint(t / 0.45);
    var sP = easeOutQuint(Math.max(0, t - 0.35) / 0.50);
    // Mid-clip crimson accent shift (after t=3.8s, matching #37's red highlight beat!)
    var isRedBeat = t >= 3.8;
    var hFill = isRedBeat ? '#EF4444' : '#F8F5F0';
    var hStroke = isRedBeat ? '#FFFFFF' : 'none';

    var hsz = 134;
    var hw = measureW(mainTitle, hsz, 400, SERIF);
    if (hw > 920) hsz = Math.max(76, Math.floor((hsz * 920) / hw));

    svg += '<g transform="translate(540,' + (292 + (1 - hP) * 14).toFixed(1) + ')" opacity="' + hP.toFixed(2) + '" filter="url(#sh)">'
      + '<text x="0" y="0" text-anchor="middle" font-family="' + SERIF + '" font-size="' + hsz + '" font-weight="400" letter-spacing="-1" fill="' + hFill + '" stroke="' + hStroke + '" stroke-width="' + (isRedBeat ? '2.5' : '0') + '" paint-order="stroke">' + esc(mainTitle) + '</text></g>';

    var ssz = 92;
    var sw = measureW(scriptSub, ssz, 400, SCRIPT);
    if (sw > 860) ssz = Math.max(54, Math.floor((ssz * 860) / sw));
    svg += '<g transform="translate(540,' + (366 + (1 - sP) * 10).toFixed(1) + ')" opacity="' + (0.94 * sP).toFixed(2) + '" filter="url(#sh)">'
      + '<text x="0" y="0" text-anchor="middle" font-family="' + SCRIPT + '" font-size="' + ssz + '" font-weight="400" fill="#F3EFEA">' + esc(scriptSub) + '</text></g>';

    // Whisper-clean minimal lowercase subtitle in face-safe lower-third
    var capD = 'HD:' + Math.round(hP * 20) + ':' + (isRedBeat ? 'R' : 'W');
    if (raw) {
      var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
      var mAge = Math.max(0, t - mStart);
      var cp = easeOutQuint(mAge / 0.24);
      var low = raw.toLowerCase();
      var lines = wrapLines(low, 840, 38, 400, SANS, 2);
      var y0 = lines.length === 1 ? 1425 : 1398;
      svg += '<g transform="translate(0,' + ((1 - cp) * 10).toFixed(1) + ')" opacity="' + (0.95 * cp).toFixed(2) + '" filter="url(#sh)">';
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 52) + '" text-anchor="middle" font-family="' + SANS + '" font-size="38" font-weight="400" letter-spacing="0.2" fill="#FFFFFF">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD += '|' + low + '@' + Math.round(cp * 20);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 64, y: 120, w: 952, h: 270 }, { slot: 'caption', x: 110, y: 1350, w: 860, h: 130 }]; };
})();
