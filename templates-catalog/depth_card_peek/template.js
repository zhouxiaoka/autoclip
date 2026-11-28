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
    var svg = '<defs><linearGradient id="bs" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.65"/></linearGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000" flood-opacity="0.75"/></filter></defs>'
      + '<rect x="0" y="1240" width="1080" height="680" fill="url(#bs)"/>';
    var capD = 'CPF_IDLE';
    if (raw) {
      var vars = state.vars || {};
      var fScale = ({ S: 0.86, M: 1.0, L: 1.15 })[String(vars.font_scale || 'M').toUpperCase()] || 1.0;
      var fsz = Math.round(56 * fScale);
      var mAge = Math.max(0, t - momentStart(moment));
      var p = easeOutQuint(mAge / 0.22);
      var lines = wrapLines(raw, 880, fsz, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1435 : 1395;
      svg += '<g transform="translate(0,' + ((1 - p) * 14).toFixed(1) + ')" opacity="' + p.toFixed(2) + '" filter="url(#sh)">';
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * Math.round(68 * fScale)) + '" text-anchor="middle" font-family="' + SANS + '" font-size="' + fsz + '" font-weight="700" fill="#FFFFFF" stroke="#09090B" stroke-width="8" paint-order="stroke" stroke-linejoin="round">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD = 'CPF:' + raw + '@' + Math.round(p * 20);
    }
    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 1340, w: 900, h: 170 }]; };
})();
