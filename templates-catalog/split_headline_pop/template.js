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

    var svg = '<defs><linearGradient id="bs" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.58"/></linearGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="10" flood-color="#000" flood-opacity="0.7"/></filter></defs>';
    svg += '<rect x="0" y="1220" width="1080" height="700" fill="url(#bs)"/>';

    var capD = 'LIME_IDLE';
    if (raw) {
      var mStart = momentStart(moment);
      var mDur = Math.max(0.4, momentEnd(moment) - mStart);
      var mAge = Math.max(0, t - mStart);
      var words = raw.split(/\s+/).filter(Boolean);
      var activeIdx = Math.min(words.length - 1, Math.floor((mAge / mDur) * words.length));

      var fsz = 58;
      var lines = wrapLines(raw, 880, fsz, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1425 : 1380;
      var wCounter = 0;

      for (var i = 0; i < lines.length; i++) {
        var lnWords = lines[i].split(/\s+/);
        var totalW = 0;
        for (var k = 0; k < lnWords.length; k++) totalW += measureW(lnWords[k] + (k < lnWords.length - 1 ? ' ' : ''), fsz, 700, SANS);
        var xCur = Math.round(540 - totalW / 2);
        var yLine = y0 + i * 82;
        for (var j = 0; j < lnWords.length; j++) {
          var w = lnWords[j];
          var ww = measureW(w, fsz, 700, SANS);
          var isAct = (wCounter === activeIdx);
          if (isAct) {
            svg += '<rect x="' + (xCur - 14) + '" y="' + (yLine - 54) + '" width="' + Math.round(ww + 28) + '" height="72" rx="14" fill="#A3E635" filter="url(#sh)"/>'
              + '<text x="' + xCur + '" y="' + yLine + '" font-family="' + SANS + '" font-size="' + fsz + '" font-weight="700" fill="#09090B">' + esc(w) + '</text>';
          } else {
            svg += '<text x="' + xCur + '" y="' + yLine + '" font-family="' + SANS + '" font-size="' + fsz + '" font-weight="700" fill="#FFFFFF" stroke="#09090B" stroke-width="6" paint-order="stroke" filter="url(#sh)">' + esc(w) + '</text>';
          }
          xCur += Math.round(measureW(w + ' ', fsz, 700, SANS));
          wCounter++;
        }
      }
      capD = 'L:' + raw + '@' + activeIdx;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 80, y: 1315, w: 920, h: 190 }]; };
})();
