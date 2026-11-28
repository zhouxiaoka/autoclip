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
    var kicker = (state.kicker || 'LAST 30 DAYS').trim();
    var headline = titleLines[0] || '164.4K · $41.2K';
    var subline = titleLines[1] || 'Organic Channel Growth';

    var svg = '<defs>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000" flood-opacity="0.55"/></filter>'
      + '</defs>';

    // Upper face-safe compact dark translucent IG-style KPI metrics pill (y=170..350)
    var cardP = spring(t, 0.34);
    var cardSc = 0.92 + 0.08 * cardP;
    var countP = easeOutCubic(Math.min(1, t / 1.4));
    // Subtle animated trend sparkline progress
    var dashOff = Math.round(160 * (1 - countP));

    var vars = state.vars || {};
    var accent = (typeof vars.accent_color === 'string' && vars.accent_color) ? vars.accent_color : '#22C55E';
    var fScale = ({ S: 0.86, M: 1.0, L: 1.15 })[String(vars.font_scale || 'M').toUpperCase()] || 1.0;

    svg += '<g transform="translate(540,256) scale(' + cardSc.toFixed(3) + ')" opacity="' + easeOutCubic(t / 0.2).toFixed(2) + '" filter="url(#sh)">'
      + '<rect x="-410" y="-88" width="820" height="176" rx="28" fill="#101218" fill-opacity="0.82" stroke="rgba(255,255,255,0.16)" stroke-width="2"/>'
      + '<circle cx="-364" cy="-42" r="7" fill="' + accent + '"/>'
      + '<text x="-346" y="-35" font-family="' + SANS + '" font-size="22" font-weight="600" letter-spacing="2.2" fill="#A1A1AA">' + esc(kicker.toUpperCase()) + '</text>'
      + '<text x="-368" y="24" font-family="' + SANS + '" font-size="52" font-weight="700" letter-spacing="-1" fill="#FFFFFF">' + esc(headline) + '</text>'
      + '<text x="-368" y="62" font-family="' + SANS + '" font-size="24" font-weight="500" fill="#9CA3AF">' + esc(subline) + '</text>'
      + '<polyline points="190,42 232,26 274,34 316,2 368,-34" fill="none" stroke="' + accent + '" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="160" stroke-dashoffset="' + dashOff + '"/>'
      + '<circle cx="368" cy="-34" r="7" fill="' + accent + '" opacity="' + (countP > 0.9 ? '1' : '0') + '"/>'
      + '</g>';

    // Lower face-safe CRISP WHITE WITH BLACK OUTLINE subtitles
    var capD = 'CARD:' + Math.round(countP * 30);
    if (raw) {
      var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
      var mAge = Math.max(0, t - mStart);
      var sp = 0.88 + 0.12 * spring(mAge, 0.22);
      var csz = Math.round(62 * fScale);
      var lines = wrapLines(raw, 880, csz, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1420 : 1385;
      svg += '<g transform="translate(540,' + y0 + ') scale(' + sp.toFixed(3) + ')">';
      for (var i = 0; i < lines.length; i++) {
        var dy = i * Math.round(76 * fScale);
        svg += '<text x="0" y="' + dy + '" text-anchor="middle" font-family="' + SANS + '" font-size="' + csz + '" font-weight="700" letter-spacing="-0.8" fill="#FFFFFF" stroke="#000000" stroke-width="11" paint-order="stroke" stroke-linejoin="round">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD += '|' + raw + '@' + Math.round(sp * 30);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 130, y: 168, w: 820, h: 176 }, { slot: 'caption', x: 90, y: 1330, w: 900, h: 160 }]; };
})();
