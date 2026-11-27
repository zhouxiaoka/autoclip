(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', 'ACBarlow', Impact, sans-serif";
  var SERIF = "'ACInstrument', 'ACPlayfair', Georgia, serif";
  var PLAYFAIR = "'ACPlayfair', Georgia, serif";
  var BRUSH = "'ACCaveat', Georgia, cursive";

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }

  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutCubic(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 3); }
  function easeOutBack(x) {
    var p = clamp01(x);
    var c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
  }
  function springPop(age, dur) {
    var p = clamp01(age / (dur || 0.24));
    if (p >= 1) return 1;
    return 0.78 + 0.22 * easeOutBack(p);
  }
  function blurReveal(age, dur) {
    var p = easeOutCubic(age / (dur || 0.26));
    return {
      alpha: p,
      blur: Math.max(0, (1 - p) * 7.5),
      dy: (1 - p) * 20,
      step: Math.round(p * 20),
    };
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

  function wrapLines(text, maxW, sz, weight, family, maxLines) {
    var words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var lines = [];
    var cur = words[0];
    for (var i = 1; i < words.length; i++) {
      var cand = cur + ' ' + words[i];
      if (measureW(cand, sz, weight, family) <= maxW) {
        cur = cand;
      } else {
        lines.push(cur);
        cur = words[i];
        if (maxLines && lines.length >= maxLines - 1) {
          var rest = words.slice(i).join(' ');
          lines.push(rest);
          return lines;
        }
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
    var titleLines = (state.title_lines || []).filter(Boolean);

    var svg = '<defs>'
      + '<radialGradient id="vg" cx="50%" cy="50%" r="65%"><stop offset="0%" stop-color="#000" stop-opacity="0.34"/><stop offset="100%" stop-color="#000" stop-opacity="0.62"/></radialGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#000" flood-opacity="0.6"/></filter>'
      + '</defs>';

    var digest = '';
    if (t < 1.55 && titleLines.length) {
      var bgOp = easeOutCubic(t / 0.25).toFixed(2);
      svg += '<rect x="0" y="0" width="1080" height="1920" fill="url(#vg)" opacity="' + bgOp + '"/>';
      var words = titleLines.join(' ').trim().split(/\s+/).slice(0, 3);
      var baseY = 810;
      var steps = [];
      for (var i = 0; i < words.length; i++) {
        var age = t - i * 0.12;
        if (age < 0) continue;
        var sc = springPop(age, 0.26);
        var al = easeOutCubic(age / 0.16);
        var w = words[i].toUpperCase();
        var isRed = (i === 1) || /\d/.test(w);
        var sz = isRed ? 176 : 132;
        var ww = measureW(w, sz, 400, POSTER);
        if (ww > 880) sz = Math.max(72, Math.floor((sz * 880) / ww));
        var y = baseY + i * 148;
        svg += '<g transform="translate(540,' + y + ') scale(' + sc.toFixed(3) + ')" opacity="' + al.toFixed(2) + '">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + sz + '" letter-spacing="2" fill="' + (isRed ? '#C81E1E' : '#FFFFFF') + '" filter="url(#sh)">' + esc(w) + '</text></g>';
        steps.push(Math.round(sc * 40));
      }
      digest = 'H:' + words.join('|') + ':' + steps.join(',');
    } else if (raw) {
      var mStart = (moment && moment.start) || 0;
      var mAge = Math.max(0, t - mStart);
      svg += '<rect x="0" y="0" width="1080" height="1920" fill="url(#vg)" opacity="0.52"/>';
      var tokens = raw.split(/\s+/).filter(Boolean);
      var mid = Math.floor(tokens.length / 2);
      var lines = tokens.length <= 3 ? tokens : [tokens.slice(0, mid).join(' '), tokens[mid], tokens.slice(mid + 1).join(' ')].filter(Boolean);
      var startY = 880 - (lines.length - 1) * 62;
      var csteps = [];
      for (var j = 0; j < lines.length; j++) {
        var lage = Math.max(0, mAge - j * 0.08);
        var lsc = springPop(lage, 0.22);
        var lal = easeOutCubic(lage / 0.14);
        var ln = lines[j].toUpperCase();
        var accent = (j === 1) || /\d/.test(ln);
        var csz = accent ? 124 : 96;
        var lw = measureW(ln, csz, 400, POSTER);
        if (lw > 880) csz = Math.max(54, Math.floor((csz * 880) / lw));
        var cy = startY + j * 124;
        svg += '<g transform="translate(540,' + cy + ') scale(' + lsc.toFixed(3) + ')" opacity="' + lal.toFixed(2) + '">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + csz + '" letter-spacing="1.5" fill="' + (accent ? '#DC2626' : '#FFFFFF') + '" filter="url(#sh)">' + esc(ln) + '</text></g>';
        csteps.push(Math.round(lsc * 40));
      }
      digest = 'C:' + raw + ':' + csteps.join(',');
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return digest;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 720, w: 900, h: 460 }]; };
})();
